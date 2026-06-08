"""Tests for Fmi2UnitConverter."""

from __future__ import annotations

import pytest

from pyssp_standard.standard.fmi2.model.model_description import (
    Fmi2ScalarVariable,
    Fmi2Unit,
)
from pyssp_standard.standard.fmi2.operations.unit_converter import (
    Fmi2UnitConverter,
)


@pytest.fixture
def converter() -> Fmi2UnitConverter:
    return Fmi2UnitConverter()


class TestLookup:
    def test_lookup_known_unit(self, converter: Fmi2UnitConverter) -> None:
        unit = converter.lookup("N")
        assert isinstance(unit, Fmi2Unit)
        assert unit.name == "N"
        # Newton decomposes to kg^1 * m^1 * s^-2
        assert unit.base_unit == {"kg": "1", "m": "1", "s": "-2"}

    def test_lookup_unknown_unit(self, converter: Fmi2UnitConverter) -> None:
        with pytest.raises(KeyError, match="nonexistent"):
            converter.lookup("nonexistent")

    def test_lookup_returns_fmi2unit(self, converter: Fmi2UnitConverter) -> None:
        unit = converter.lookup("kg")
        assert isinstance(unit, Fmi2Unit)


class TestRegister:
    def test_register_custom_unit(self, converter: Fmi2UnitConverter) -> None:
        converter.register("myUnit", {"kg": "1"})
        unit = converter.lookup("myUnit")
        assert unit.name == "myUnit"
        assert unit.base_unit == {"kg": "1"}


class TestValidateConsistency:
    def test_validate_consistent_variables(
        self, converter: Fmi2UnitConverter
    ) -> None:
        variables = [
            Fmi2ScalarVariable(name="a", value_reference=0, type_name="Real", unit="kg"),
            Fmi2ScalarVariable(name="b", value_reference=1, type_name="Real", unit="m"),
        ]
        missing = converter.validate_consistency(variables)
        assert missing == []

    def test_validate_inconsistent_variables(
        self, converter: Fmi2UnitConverter
    ) -> None:
        variables = [
            Fmi2ScalarVariable(name="a", value_reference=0, type_name="Real", unit="ghost"),
            Fmi2ScalarVariable(name="b", value_reference=1, type_name="Real", unit="kg"),
        ]
        missing = converter.validate_consistency(variables)
        assert missing == ["ghost"]

    def test_validate_skips_none_unit(
        self, converter: Fmi2UnitConverter
    ) -> None:
        variables = [
            Fmi2ScalarVariable(name="a", value_reference=0, type_name="Real", unit=None),
        ]
        missing = converter.validate_consistency(variables)
        assert missing == []