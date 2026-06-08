"""FMI2 unit converter: maps display-unit names to Fmi2Unit objects."""

from __future__ import annotations

from pyssp_standard.standard.fmi2.model.model_description import (
    Fmi2ScalarVariable,
    Fmi2Unit,
)
from pyssp_standard.standard.unit_conversion import generate_base_unit


class Fmi2UnitConverter:
    """Maps display-unit names to Fmi2Unit with base-unit decomposition."""

    def __init__(self) -> None:
        """Seed built-in units from unit_conversion.generate_base_unit."""
        self._units: dict[str, dict[str, str]] = {}
        # Seed with known units from unit_conversion
        for name in ("kg", "m", "s", "A", "K", "mol", "cd", "rad", "N"):
            raw = generate_base_unit(name)
            if raw:  # should always be true for these 9 names
                self._units[name] = {k: str(v) for k, v in raw.items()}

    def lookup(self, name: str) -> Fmi2Unit:
        """Return an Fmi2Unit for *name*, with base_unit populated.

        Raises KeyError if the unit is unknown.
        """
        if name not in self._units:
            raise KeyError(f"Unknown unit: {name}")
        return Fmi2Unit(name=name, base_unit=dict(self._units[name]))

    def register(self, name: str, base_unit: dict[str, str]) -> None:
        """Add a custom unit definition."""
        self._units[name] = dict(base_unit)

    def validate_consistency(
        self, variables: list[Fmi2ScalarVariable]
    ) -> list[str]:
        """Check that every variable's unit is defined in the converter.

        Returns a list of missing unit names (empty if all consistent).
        Variables with ``unit=None`` are skipped.
        """
        missing: list[str] = []
        seen: set[str] = set()
        for var in variables:
            if var.unit is None:
                continue
            if var.unit in self._units:
                continue
            if var.unit not in seen:
                seen.add(var.unit)
                missing.append(var.unit)
        return missing