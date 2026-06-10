"""Tests for the runtime layer (F-001, F-004 from IMP-029)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# F-001: ArchiveRuntime delegates match DirectoryRuntime public API
# ---------------------------------------------------------------------------


def test_archive_runtime_delegates_match_directory_runtime():
    """All DirectoryRuntime public methods have matching ArchiveRuntime delegates."""
    from pyssp_standard.common.archive_runtime import ArchiveRuntime
    from pyssp_standard.common.directory_runtime import DirectoryRuntime

    dir_methods = {
        name
        for name, _ in inspect.getmembers(DirectoryRuntime, inspect.isfunction)
        if not name.startswith("_")
    }
    archive_methods = {
        name
        for name, _ in inspect.getmembers(ArchiveRuntime, inspect.isfunction)
        if not name.startswith("_")
    }

    # Exclude methods with different semantics
    excluded = {"path", "mode"}

    for method in dir_methods - excluded:
        assert method in archive_methods, (
            f"DirectoryRuntime.{method} has no matching delegate in ArchiveRuntime"
        )


# ---------------------------------------------------------------------------
# F-004: create_runtime() with explicit runtime_type parameter
# ---------------------------------------------------------------------------


def test_create_runtime_explicit_directory(tmp_path):
    """runtime_type='directory' always returns DirectoryRuntime."""
    from pyssp_standard.common.archive_runtime import (
        ArchiveRuntime,
        DirectoryRuntime,
        create_runtime,
    )

    ssppath = tmp_path / "test.ssp"
    rt = create_runtime(ssppath, mode="r", runtime_type="directory")
    assert isinstance(rt, DirectoryRuntime)


def test_create_runtime_explicit_archive(tmp_path):
    """runtime_type='archive' always returns ArchiveRuntime."""
    from pyssp_standard.common.archive_runtime import (
        ArchiveRuntime,
        DirectoryRuntime,
        create_runtime,
    )

    rt = create_runtime(tmp_path / "plain_dir", mode="r", runtime_type="archive")
    assert isinstance(rt, ArchiveRuntime)


def test_create_runtime_auto_directory_existing(tmp_path):
    """Auto heuristic: existing directory → DirectoryRuntime."""
    from pyssp_standard.common.archive_runtime import (
        ArchiveRuntime,
        DirectoryRuntime,
        create_runtime,
    )

    d = tmp_path / "existing_dir"
    d.mkdir()
    rt = create_runtime(d, mode="r")
    assert isinstance(rt, DirectoryRuntime)


def test_create_runtime_auto_archive_non_existent_ssp(tmp_path):
    """Auto heuristic: non-existent .fmu path → ArchiveRuntime."""
    from pyssp_standard.common.archive_runtime import (
        ArchiveRuntime,
        DirectoryRuntime,
        create_runtime,
    )

    rt = create_runtime(tmp_path / "model.fmu", mode="r")
    assert isinstance(rt, ArchiveRuntime)


def test_create_runtime_auto_non_existent_no_suffix(tmp_path):
    """Auto heuristic: non-existent path without known suffix → DirectoryRuntime."""
    from pyssp_standard.common.archive_runtime import (
        ArchiveRuntime,
        DirectoryRuntime,
        create_runtime,
    )

    rt = create_runtime(tmp_path / "unknown", mode="r")
    assert isinstance(rt, DirectoryRuntime)