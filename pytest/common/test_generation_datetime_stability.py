"""Guardrail tests ensuring no XML facade auto-injects varying generationDateAndTime.

AC-DET-005: XML documents created without calling set_generation_date_and_time()
do not include a varying generationDateAndTime attribute.

Covers all 6 XML facades: ModelDescription (FMI2), SSD, SSV, SSM, SRMD, SSB.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_minimal_md(path: Path) -> None:
    """Write a minimal FMI2 modelDescription that passes schema validation."""
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<fmiModelDescription\n'
        '  fmiVersion="2.0"\n'
        '  modelName="Test"\n'
        '  guid="{test-guid}">\n'
        '  <CoSimulation modelIdentifier="Test" />\n'
        '  <ModelVariables>\n'
        '    <ScalarVariable name="x" valueReference="1"><Real /></ScalarVariable>\n'
        '  </ModelVariables>\n'
        '  <ModelStructure />\n'
        '</fmiModelDescription>\n',
    )


# ---------------------------------------------------------------------------
# ModelDescription (FMI2) — uses self.xml.generation_date_and_time
#
# FMI2 ModelDescription in "w" mode creates a minimal document that fails
# schema validation (empty ModelVariables). So we pre-write a valid minimal
# XML and use "a" (append) mode instead.
# ---------------------------------------------------------------------------


class TestModelDescriptionGenerationDatetimeStability:
    """FMI2 ModelDescription facade."""

    def test_no_auto_injection_in_append_mode(self, tmp_path):
        """A pre-existing MD doc opened in append mode must NOT auto-inject generationDateAndTime."""
        path = tmp_path / "md.xml"
        _write_minimal_md(path)
        from pyssp_standard.md import ModelDescription

        with ModelDescription(path, mode="a", version="2.0") as md:
            pass
        text = path.read_text(encoding="utf-8")
        # The initial XML has generationDateAndTime absent; append mode should not add it
        assert "generationDateAndTime" not in text, (
            "generationDateAndTime was auto-injected during append-mode"
        )

    def test_stable_across_two_append_cycles(self, tmp_path):
        """Two identical append cycles produce identical content."""
        path1 = tmp_path / "md1.xml"
        path2 = tmp_path / "md2.xml"
        _write_minimal_md(path1)
        _write_minimal_md(path2)
        from pyssp_standard.md import ModelDescription

        with ModelDescription(path1, mode="a", version="2.0"):
            pass
        with ModelDescription(path2, mode="a", version="2.0"):
            pass
        assert _sha256(path1) == _sha256(path2)

    def test_stable_across_two_append_cycles_after_set_none(self, tmp_path):
        """Calling set_generation_date_and_time(None) produces identical output."""
        path1 = tmp_path / "md1.xml"
        path2 = tmp_path / "md2.xml"
        _write_minimal_md(path1)
        _write_minimal_md(path2)
        from pyssp_standard.md import ModelDescription

        with ModelDescription(path1, mode="a", version="2.0") as md:
            md.set_generation_date_and_time()
        with ModelDescription(path2, mode="a", version="2.0") as md:
            md.set_generation_date_and_time()
        assert _sha256(path1) == _sha256(path2)


# ---------------------------------------------------------------------------
# SSD, SSV, SSM, SRMD, SSB — all use self.xml.metadata.generation_date_and_time
#
# Their _create_document() uses self.path.stem as a content identifier, so
# to get identical content we must create documents with the same filename
# in different directories.
# ---------------------------------------------------------------------------


def _same_filename_facade_pair(tmp_path, facade_cls):
    """Return (path1, path2) with identical filenames in different dirs."""
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    return d1 / f"test.{facade_cls.__name__.lower()}", d2 / f"test.{facade_cls.__name__.lower()}"


class BaseGenerationDatetimeStability:
    """Base for SSD/SSV/SSM/SRMD/SSB facade stability tests."""

    FACADE_CLASS = None  # subclass must set

    def _create_facade(self, path, mode="w"):
        return self.FACADE_CLASS(path, mode=mode)

    def test_no_auto_injection_in_write_mode(self, tmp_path):
        """A freshly created document must NOT contain generationDateAndTime."""
        path = tmp_path / f"test.{self.FACADE_CLASS.__name__.lower()}"
        with self._create_facade(path, mode="w"):
            pass
        text = path.read_text(encoding="utf-8")
        assert "generationDateAndTime" not in text, (
            f"{self.FACADE_CLASS.__name__}: generationDateAndTime was auto-injected"
        )

    def test_stable_across_two_creations(self, tmp_path):
        """Two identical documents (same filename) produce identical content."""
        p1, p2 = _same_filename_facade_pair(tmp_path, self.FACADE_CLASS)
        with self._create_facade(p1, mode="w"):
            pass
        with self._create_facade(p2, mode="w"):
            pass
        assert _sha256(p1) == _sha256(p2)

    def test_stable_across_two_creations_after_set_none(self, tmp_path):
        """Calling set_generation_date_and_time(None) produces identical output."""
        p1, p2 = _same_filename_facade_pair(tmp_path, self.FACADE_CLASS)
        with self._create_facade(p1, mode="w") as doc:
            doc.set_generation_date_and_time()
        with self._create_facade(p2, mode="w") as doc:
            doc.set_generation_date_and_time()
        assert _sha256(p1) == _sha256(p2)


class TestSSDGenerationDatetimeStability(BaseGenerationDatetimeStability):
    from pyssp_standard.ssd import SSD

    FACADE_CLASS = SSD


class TestSSVGenerationDatetimeStability(BaseGenerationDatetimeStability):
    from pyssp_standard.ssv import SSV

    FACADE_CLASS = SSV


class TestSSMGenerationDatetimeStability(BaseGenerationDatetimeStability):
    from pyssp_standard.ssm import SSM

    FACADE_CLASS = SSM


class TestSRMDGenerationDatetimeStability(BaseGenerationDatetimeStability):
    from pyssp_standard.srmd import SRMD

    FACADE_CLASS = SRMD


class TestSSBGenerationDatetimeStability(BaseGenerationDatetimeStability):
    from pyssp_standard.ssb import SSB

    FACADE_CLASS = SSB