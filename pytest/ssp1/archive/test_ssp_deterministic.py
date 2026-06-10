"""Acceptance criteria for deterministic SSP archive builds.

AC-DET-002: Two SSP.__init__(path, mode="w") contexts with identical FMU additions
            produce identical SHA256 hashes.
AC-DET-004: Two SSP archives adding the same resource file produce identical SHA256 hashes.
"""

from __future__ import annotations

import hashlib

import pytest


def test_ssp_create_deterministic(fmu_archive_fixture, tmp_path):
    """AC-DET-002: Two SSP contexts with identical FMU additions produce identical SHA256."""
    from pyssp_standard.ssp import SSP

    ssp_path1 = tmp_path / "det_1.ssp"
    ssp_path2 = tmp_path / "det_2.ssp"

    with SSP(ssp_path1, mode="w") as ssp:
        ssp.add_fmu("controller", fmu_archive_fixture, expose_system_connectors=True)
    with SSP(ssp_path2, mode="w") as ssp:
        ssp.add_fmu("controller", fmu_archive_fixture, expose_system_connectors=True)

    hash1 = hashlib.sha256(ssp_path1.read_bytes()).hexdigest()
    hash2 = hashlib.sha256(ssp_path2.read_bytes()).hexdigest()
    assert hash1 == hash2


def test_ssp_add_resource_deterministic(tmp_path):
    """AC-DET-004: Two SSP archives adding the same resource produce identical SHA256."""
    import hashlib
    from pyssp_standard.ssp import SSP

    resource_file = tmp_path / "data.txt"
    resource_file.write_text("deterministic content\n")

    ssp_path1 = tmp_path / "res_1.ssp"
    ssp_path2 = tmp_path / "res_2.ssp"

    with SSP(ssp_path1, mode="w") as ssp:
        ssp.add_resource(resource_file)
    with SSP(ssp_path2, mode="w") as ssp:
        ssp.add_resource(resource_file)

    hash1 = hashlib.sha256(ssp_path1.read_bytes()).hexdigest()
    hash2 = hashlib.sha256(ssp_path2.read_bytes()).hexdigest()
    assert hash1 == hash2