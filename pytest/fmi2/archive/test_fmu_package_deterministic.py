"""Acceptance criteria for deterministic FMU package_as_ssp.

AC-DET-003: Two FMU.package_as_ssp() calls with the same FMU produce identical SHA256 hashes.
"""

from __future__ import annotations

import hashlib
import shutil

import pytest


def test_fmu_package_as_ssp_deterministic(fmu_archive_fixture, tmp_path):
    """AC-DET-003: Two package_as_ssp calls with the same FMU produce identical SHA256.

    Both calls use the same FMU filename and SSP basename so that component_name,
    system_name, and resource names in the generated SSP are identical.
    """
    from pyssp_standard.fmu import FMU

    # Copy the fixture to a consistent filename so the produced SSP is identical
    fmu_path = tmp_path / "controller.fmu"
    shutil.copy(fmu_archive_fixture, fmu_path)

    # Use the same SSP basename for both to keep system_name identical
    ssp_path = tmp_path / "packaged.ssp"
    # Remove any leftover from first run before second
    ssp_path_recreated = tmp_path / "packaged.ssp"

    with FMU(fmu_path) as fmu:
        fmu.package_as_ssp(ssp_path)
    hash1 = hashlib.sha256(ssp_path.read_bytes()).hexdigest()

    ssp_path_recreated.unlink()

    with FMU(fmu_path) as fmu:
        fmu.package_as_ssp(ssp_path_recreated)
    hash2 = hashlib.sha256(ssp_path_recreated.read_bytes()).hexdigest()

    assert hash1 == hash2