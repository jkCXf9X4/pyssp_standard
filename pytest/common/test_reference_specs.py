"""Tests for ExternalReferenceSpec validation (F-006 from IMP-029)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass
class _ValidOwner:
    source: str | None = None
    document: str | None = None


class _MockContextFacade:
    def __init__(self, path, mode="r"):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class TestExternalReferenceSpecValidation:

    def test_valid_spec_creates(self):
        from pyssp_standard.common.document_runtime import ExternalReferenceSpec

        spec = ExternalReferenceSpec(
            owner_type=_ValidOwner,
            source_attr="source",
            document_attr="document",
            facade_type=_MockContextFacade,
        )
        assert spec.owner_type is _ValidOwner
        assert spec.source_attr == "source"

    def test_invalid_owner_type_raises(self):
        from pyssp_standard.common.document_runtime import ExternalReferenceSpec

        with pytest.raises(TypeError, match="owner_type must be a class"):
            ExternalReferenceSpec(
                owner_type="not_a_class",
                source_attr="source",
                document_attr="document",
                facade_type=_MockContextFacade,
            )

    def test_missing_source_attr_raises(self):
        from pyssp_standard.common.document_runtime import ExternalReferenceSpec

        with pytest.raises(AttributeError, match="source_attr"):
            ExternalReferenceSpec(
                owner_type=_ValidOwner,
                source_attr="nonexistent",
                document_attr="document",
                facade_type=_MockContextFacade,
            )

    def test_missing_document_attr_raises(self):
        from pyssp_standard.common.document_runtime import ExternalReferenceSpec

        with pytest.raises(AttributeError, match="document_attr"):
            ExternalReferenceSpec(
                owner_type=_ValidOwner,
                source_attr="source",
                document_attr="nonexistent",
                facade_type=_MockContextFacade,
            )

    def test_invalid_facade_type_raises(self):
        from pyssp_standard.common.document_runtime import ExternalReferenceSpec

        with pytest.raises(TypeError, match="facade_type"):
            ExternalReferenceSpec(
                owner_type=_ValidOwner,
                source_attr="source",
                document_attr="document",
                facade_type=int,
            )

    def test_all_real_specs_pass_validation(self):
        from pyssp_standard.common.reference_specs import EXTERNAL_REFERENCE_SPECS

        for spec in EXTERNAL_REFERENCE_SPECS:
            assert spec.owner_type is not None
            assert spec.source_attr is not None
            assert spec.document_attr is not None
            assert spec.facade_type is not None