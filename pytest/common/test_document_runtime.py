"""Tests for DocumentRuntime error handling (F-003 from IMP-029)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass
class _TestOwner:
    source: str | None = None
    items: str | None = None


class _FailingFacade:
    """Facade that raises ValueError on __enter__."""
    def __init__(self, path, mode="r"):
        pass
    def __enter__(self):
        raise ValueError("simulated parse failure")
    def __exit__(self, *args):
        return False


class _MockFacade:
    def __init__(self, path, mode="r"):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    @property
    def xml(self):
        return None


def test_load_external_document_logs_on_failure(tmp_path, caplog):
    """_load_external_document logs a warning on load failure and returns None."""
    from pyssp_standard.common.document_runtime import (
        DocumentRuntime,
        ExternalReferenceSpec,
    )
    from pyssp_standard.common.archive_runtime import DirectoryRuntime

    # Create a directory runtime pointing at the temp directory
    runtime = DirectoryRuntime(tmp_path)
    runtime.__enter__()

    try:
        doc_runtime = DocumentRuntime(
            runtime=runtime,
            document_path="dummy.xml",
            document_type=_MockFacade,
            mode="r",
        )

        # Create an existing file at the resolved path so we get past
        # the early path.exists() check in _load_external_document
        (tmp_path / "ref.xml").write_text("<root/>", encoding="utf-8")

        spec = ExternalReferenceSpec(
            owner_type=_TestOwner,
            source_attr="source",
            document_attr="items",
            facade_type=_FailingFacade,
        )

        with caplog.at_level(logging.WARNING):
            # _load_external_document resolves source from owner's
            # source_attr, so pass an owner with a source value
            result = doc_runtime._load_external_document(
                _TestOwner(source="ref.xml"), spec
            )

        assert result is None
        assert "Failed to load external reference" in caplog.text
    finally:
        runtime.__exit__(None, None, None)