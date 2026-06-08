# IMP-024: Add Fmi2UnitConverter for display-unit to base-unit mapping

> **Status:** Proposed
> **Priority:** High
> **Layer:** Domain Model (primary) / Operations (secondary)

## Theme

Standalone converter that maps a display-unit name to its base-unit decomposition, providing `lookup(name) -> Fmi2Unit` and optionally validating unit consistency across variables.

## Evidence

### Existing unit infrastructure

`pyssp_standard/standard/unit_conversion.py` (19 lines) provides:

```python
_BASE_UNITS: dict[str, dict[str, float | int]] = {
    "kg": {"kg": 1},
    "m": {"m": 1},
    "s": {"s": 1},
    "A": {"a": 1},
    "K": {"k": 1},
    "mol": {"mol": 1},
    "cd": {"cd": 1},
    "rad": {"rad": 1},
    "N": {"kg": 1, "m": 1, "s": -2},
}

def generate_base_unit(name: str) -> dict[str, float | int]:
    return dict(_BASE_UNITS.get(name, {}))
```

This covers only **9 well-known units** and returns flat dicts — not `Fmi2Unit` objects. There is no structured converter.

### Fmi2Unit / Fmi2TypeDefinition dataclasses

`pyssp_standard/standard/fmi2/model/model_description.py`, lines 32–43:

```python
@dataclass
class Fmi2Unit:
    name: str
    base_unit: dict[str, str] = field(default_factory=dict)

@dataclass
class Fmi2TypeDefinition:
    name: str
    type_name: str
    attributes: dict[str, str] = field(default_factory=dict)
    enumeration_items: list[dict[str, str]] = field(default_factory=list)
```

Note: `Fmi2Unit.base_unit` is typed as `dict[str, str]` (not `dict[str, float|int]`), reflecting XML serialization. The `unit_conversion.py` base units use `dict[str, float | int]`.

### Codec round-trips but has no converter

- Codec parse: `_parse_units` (lines 197–209) and `_parse_type_definitions` (lines 211–227) correctly read these sections.
- Codec serialize: writes UnitDefinitions (lines 75–83) and TypeDefinitions (lines 85–96) correctly.
- `get_units()` and `get_type_definitions()` methods on `Fmi2ModelDescriptionDocument` provide lookup by name/type_name.

### ALIGN-001 assessment

Section F6 identified a gap: no **standalone converter** exists that can receive a variable with a unit like `"N"` and propagate the corresponding `base_unit` to a `Fmi2Unit` in the `UnitDefinitions`. The existing `generate_base_unit()` covers only 9 well-known units and uses flat dicts.

**Recommendation:** Proceed as a new candidate for a standalone `Fmi2UnitConverter` that:
- Maps a unit name to its base-unit decomposition (building on `unit_conversion.py`)
- Provides `lookup(name) -> Fmi2Unit` with `base_unit` properly populated
- Optionally validates unit consistency across variables

## Current Pain Or Risk

1. **No unit resolution** — If code parses a variable with `unit="N"`, there is no programmatic way to resolve that to "Newtons = kg·m·s⁻²" without manually calling the 9-entry lookup in `unit_conversion.py`.
2. **Inconsistent types** — `unit_conversion.py` uses `dict[str, float|int]` while `Fmi2Unit.base_unit` uses `dict[str, str]` (XML string form). A converter must bridge these.
3. **No unit validation** — If variables reference unit names that don't exist in `UnitDefinitions`, there is no built-in way to detect or report this inconsistency.
4. **Limited coverage** — Only 9 units are known. Adding a new unit requires editing a Python dict rather than extending a converter.

## Proposed Improvement

### Fmi2UnitConverter class

```python
class Fmi2UnitConverter:
    """Maps display-unit names to Fmi2Unit with base-unit decomposition."""

    def lookup(self, name: str) -> Fmi2Unit:
        """Return an Fmi2Unit for *name*, with base_unit populated.

        Raises KeyError if the unit is unknown.
        """
        ...

    def validate_consistency(self, variables: list[Fmi2ScalarVariable]) -> list[str]:
        """Check that every variable's unit is defined in the converter.

        Returns a list of missing unit names (empty if all consistent).
        """
        ...

    def register(self, name: str, base_unit: dict[str, str]) -> None:
        """Add a custom unit definition."""
        ...
```

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Class vs function | Class with state | Converter holds a registry of known units; `register()` allows extension |
| Placement | `standard/fmi2/operations/unit_converter.py` vs extending `unit_conversion.py` | FMI2-specific converter in FMI2 operations layer; `unit_conversion.py` is a cross-standard minimal helper |
| base_unit type | `dict[str, str]` (same as `Fmi2Unit.base_unit`) | Consistent with serialization format; conversion between `float|int` and `str` is handled internally |
| Built-in units | Seed with existing 9 from `unit_conversion.py` plus common SI prefixes | Immediate utility without manual registration |

### Relationship to existing code

The existing `unit_conversion.py` should remain as-is — it is a cross-standard minimal helper. The `Fmi2UnitConverter` in the FMI2 operations layer would import `generate_base_unit` as the initial seed and wrap results in `Fmi2Unit` objects.

## Expected Benefit

- `Fmi2UnitConverter().lookup("N")` returns `Fmi2Unit(name="N", base_unit={"kg": "1", "m": "1", "s": "-2"})`
- `validate_consistency(variables)` flags variables referencing undefined units
- Custom units can be registered for project-specific needs
- Bridge between `unit_conversion.py` flat dicts and `Fmi2Unit` dataclass

## Risk And Blast Radius

| Risk | Severity | Mitigation |
|------|----------|------------|
| Duplication with `unit_conversion.py` | Low | The converter wraps `generate_base_unit`, doesn't replace it; `unit_conversion.py` remains for cross-standard use |
| SI prefix explosion | Medium | Scope explicitly excludes full SI prefix resolution; the converter handles known units only |
| Float precision in base units | Low | base_unit values are stored as strings to match serialization; numerical conversion is a future extension |

## Suggested Priority

**High** — F6 was identified as High priority in ALIGN-001. Unit resolution is a missing capability that affects any workflow that reads units from variables and needs to produce corresponding `UnitDefinitions`.

## Task Contract Seed

### Phase 1 — Core converter

1. Create `pyssp_standard/standard/fmi2/operations/unit_converter.py`:
   - `Fmi2UnitConverter` class with:
     - `__init__`: Seed built-in units by importing `generate_base_unit` from `unit_conversion.py`
     - `lookup(name) -> Fmi2Unit`: Return `Fmi2Unit` with `base_unit` as `dict[str, str]`
     - `register(name, base_unit)`: Add custom unit
     - `validate_consistency(variables) -> list[str]`: Check variable unit references

### Phase 2 — Tests

2. Create `pytest/fmi2/operations/test_unit_converter.py`:

   | Test | Purpose |
   |------|---------|
   | `test_lookup_known_unit` | `lookup("N")` returns correct base_unit |
   | `test_lookup_unknown_unit` | `lookup("nonexistent")` raises `KeyError` |
   | `test_register_custom_unit` | Registered unit is found by lookup |
   | `test_validate_consistent_variables` | All variable units known → empty list |
   | `test_validate_inconsistent_variables` | Variable with unknown unit → reported |
   | `test_lookup_returns_fmi2unit` | Return type is `Fmi2Unit` |

### Phase 3 — Integration

3. Verify converter works with parsed `Fmi2ModelDescriptionDocument`: build converter, call `lookup()` for each variable's unit, populate `document.unit_definitions`.

## Out Of Scope

- **Full physical-unit algebra** (SI prefix resolution, compound unit parsing, dimensional analysis) — Limited to known unit names and their published base-unit decompositions.
- **Automatic unit inference** — No "derive unit from variable name" logic.
- **FMI3 support** — FMI3 may have different unit model; extend separately.
- **`unit_conversion.py` rewrite** — The existing file is intentionally minimal and cross-standard.

## Traceability

- **Intent:** ALIGN-001 F6 — Provide standalone unit converter for display-unit to base-unit mapping.
- **Product:** `Fmi2UnitConverter` class in `standard/fmi2/operations/unit_converter.py`.
- **Architecture:** Domain Model (primary — produces `Fmi2Unit`), Operations (secondary — conversion logic).
- **Implementation:** New file in FMI2 operations layer.
- **Verification:** Tests for lookup, registration, and consistency validation.

## Notes

- The `Fmi2Unit.base_unit` dict uses string values (e.g., `"kg": "1"`) because the codec keys are XML attributes (strings). The converter stores values as strings to match this convention.
- The 9 built-in units (`kg`, `m`, `s`, `A`, `K`, `mol`, `cd`, `rad`, `N`) are the seed; future improvements can add more.