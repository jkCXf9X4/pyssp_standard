# IMP-025: Add stepSize field to Fmi2DefaultExperiment

> **Status:** Proposed
> **Priority:** High
> **Layer:** Domain Model (primary) / Codec (secondary)

## Theme

One-field addition to `Fmi2DefaultExperiment` dataclass + codec parser/serializer changes to support the FMI 2.0 `stepSize` attribute on `<DefaultExperiment>`.

## Evidence

### Current state

`pyssp_standard/standard/fmi2/model/model_description.py`, lines 26–29:

```python
@dataclass
class Fmi2DefaultExperiment:
    start_time: float | None = None
    stop_time: float | None = None
    tolerance: float | None = None
```

The FMI 2.0 standard defines `stepSize` as an optional attribute of `<DefaultExperiment>` (primarily used by CoSimulation). This field is **absent**.

### Codec parser (lines 229–236)

```python
def _parse_default_experiment(self, element: ET.Element | None) -> Fmi2DefaultExperiment | None:
    if element is None:
        return None
    return Fmi2DefaultExperiment(
        start_time=self._parse_float(element.attrib.get("startTime")),
        stop_time=self._parse_float(element.attrib.get("stopTime")),
        tolerance=self._parse_float(element.attrib.get("tolerance")),
    )
```

Reads `startTime`, `stopTime`, `tolerance` — but not `stepSize`.

### Codec serializer (lines 98–102)

```python
if document.default_experiment is not None:
    default_experiment = ET.SubElement(root, "DefaultExperiment")
    self._set_optional(default_experiment.attrib, "startTime", self._format_float(document.default_experiment.start_time))
    self._set_optional(default_experiment.attrib, "stopTime", self._format_float(document.default_experiment.stop_time))
    self._set_optional(default_experiment.attrib, "tolerance", self._format_float(document.default_experiment.tolerance))
```

Writes `startTime`, `stopTime`, `tolerance` — but not `stepSize`.

### FMI3 precedent

`Fmi3DefaultExperiment` (in `standard/fmi3/model/model_description.py`) already has `step_size: float | None = None`, confirming the naming convention.

### ALIGN-001 assessment

Section F7 identified the gap as:

> Missing `stepSize` attribute. One field addition to the dataclass, two lines in the codec parser, one line in the serializer.

**Recommendation:** Proceed as a narrow new candidate — "Add stepSize to Fmi2DefaultExperiment". Small, well-scoped addition.

## Current Pain Or Risk

1. **Data loss on round-trip** — If a `modelDescription.xml` contains `<DefaultExperiment stepSize="0.001" ...>`, the `stepSize` attribute is silently lost during parse → serialize.
2. **FMI 2.0 non-compliance** — The `DefaultExperiment` dataclass is incomplete relative to FMI 2.0, which defines `stepSize` as valid.
3. **CoSimulation workflow gap** — `stepSize` is essential for CoSimulation stepping behavior; its absence means the library cannot faithfully represent FMUs that declare a step size.

## Proposed Improvement

### Field addition

```python
@dataclass
class Fmi2DefaultExperiment:
    start_time: float | None = None
    stop_time: float | None = None
    tolerance: float | None = None
    step_size: float | None = None  # NEW: FMI 2.0 stepSize attribute
```

### Codec changes

**Parser** — Add `stepSize` to `_parse_default_experiment`:

```python
return Fmi2DefaultExperiment(
    start_time=self._parse_float(element.attrib.get("startTime")),
    stop_time=self._parse_float(element.attrib.get("stopTime")),
    tolerance=self._parse_float(element.attrib.get("tolerance")),
    step_size=self._parse_float(element.attrib.get("stepSize")),  # NEW
)
```

**Serializer** — Add `stepSize` to `_serialize_default_experiment`:

```python
self._set_optional(default_experiment.attrib, "stepSize", self._format_float(document.default_experiment.step_size))
```

### Naming convention

- Python field: `step_size` (snake_case, matching FMI3 convention)
- XML attribute: `stepSize` (camelCase, per FMI 2.0 standard)

## Expected Benefit

- **Complete round-trip** — `stepSize` is preserved through parse → modify → serialize
- **FMI 2.0 compliance** — `DefaultExperiment` now supports all standard attributes
- **Zero regression** — Existing `start_time`/`stop_time`/`tolerance` behavior unchanged; new field defaults to `None`

## Risk And Blast Radius

| Risk | Severity | Mitigation |
|------|----------|------------|
| Existing code unaware of new field | None | `None` default means existing callers see no change; new field is purely additive |
| Name collision | None | `step_size` is unique within `Fmi2DefaultExperiment` |
| Codec backward compatibility | None | Parser handles missing `stepSize` (returns `None`); serializer omits it when `None` |

## Suggested Priority

**High** — Small, well-scoped, high-value addition. One of the few missing fields in an otherwise complete FMI 2.0 model layer.

## Task Contract Seed

### Phase 1 — Domain model

1. Add `step_size: float | None = None` to `Fmi2DefaultExperiment` in `pyssp_standard/standard/fmi2/model/model_description.py`.

### Phase 2 — Codec

2. Add `step_size=self._parse_float(element.attrib.get("stepSize"))` to `_parse_default_experiment` in `pyssp_standard/standard/fmi2/codec/model_description_xml_codec.py`.

3. Add `self._set_optional(default_experiment.attrib, "stepSize", self._format_float(document.default_experiment.step_size))` to the serializer in the same file.

### Phase 3 — Tests

4. Create or extend `pytest/fmi2/codec/test_default_experiment_stepsize.py`:

   | Test | Purpose |
   |------|---------|
   | `test_parse_step_size` | Parse XML with `stepSize="0.001"`; verify `step_size == 0.001` |
   | `test_parse_missing_step_size` | Parse XML without `stepSize`; verify `step_size is None` |
   | `test_serialize_step_size` | Serialize with `step_size=0.001`; verify XML contains `stepSize="0.001"` |
   | `test_serialize_missing_step_size` | Serialize with `step_size=None`; verify no `stepSize` attribute |
   | `test_roundtrip_step_size` | Parse → serialize → re-parse; verify `step_size` preserved |

## Out Of Scope

- **Other missing DefaultExperiment attributes** — FMI 2.0 defines only `startTime`, `stopTime`, `tolerance`, `stepSize` for `DefaultExperiment`. No other attributes are missing.
- **FMI3 backport** — FMI3's `Fmi3DefaultExperiment` already has `step_size`. This change brings FMI2 in line with FMI3 convention.
- **DefaultExperiment validation** — No semantics checking (e.g., "stepSize must be positive"). Pure data preservation.

## Traceability

- **Intent:** ALIGN-001 F7 — Add `stepSize` support to `Fmi2DefaultExperiment`.
- **Product:** Field addition to `Fmi2DefaultExperiment` dataclass + two codec changes.
- **Architecture:** Domain Model (primary), Codec (secondary).
- **Implementation:** 3 lines added (1 model + 1 parser + 1 serializer).
- **Verification:** Round-trip tests.

## Notes

- The FMI 2.0 standard specifies `stepSize` as a `xs:double` attribute on `<DefaultExperiment>`. The `_parse_float` / `_format_float` helpers already handle `float | None` correctly.
- No changes needed to the `Fmi3DefaultExperiment` (it already has `step_size`).