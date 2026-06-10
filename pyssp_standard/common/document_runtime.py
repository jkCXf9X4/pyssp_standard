from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, is_dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar
from xml.etree.ElementTree import ParseError

from pyssp_standard.common.archive_runtime import DirectoryRuntime
from pyssp_standard.common.reference_discovery import discover_external_references


logger = logging.getLogger(__name__)


FacadeT = TypeVar("FacadeT")


@dataclass(frozen=True)
class ExternalReferenceSpec:
    """Specification for resolving an external document reference.

    Validates that *owner_type* has both *source_attr* and *document_attr*,
    and that *facade_type* is a context-managed class.
    """
    owner_type: type
    source_attr: str
    document_attr: str
    facade_type: type

    def __post_init__(self) -> None:
        if not inspect.isclass(self.owner_type):
            raise TypeError(f"owner_type must be a class, got {type(self.owner_type).__name__}")
        if not hasattr(self.owner_type, self.source_attr):
            raise AttributeError(
                f"{self.owner_type.__name__} has no attribute '{self.source_attr}' (source_attr)"
            )
        if not hasattr(self.owner_type, self.document_attr):
            raise AttributeError(
                f"{self.owner_type.__name__} has no attribute '{self.document_attr}' (document_attr)"
            )
        if not hasattr(self.facade_type, '__enter__'):
            raise TypeError(
                f"facade_type must be a context-managed class, got {self.facade_type}"
            )


class _ResolvedExternalDocument:
    def __init__(self, spec: ExternalReferenceSpec, path: Path, document: Any):
        self.spec = spec
        self.path = path
        self.document = document


class _ResolvedPlacement:
    def __init__(self, owner: Any, resolved: _ResolvedExternalDocument):
        self.owner = owner
        self.resolved = resolved


class DocumentRuntime(Generic[FacadeT]):
    """
    When you load a document in the context of an ssp or an archive the runtime will populate any external references in the xml and return the populated xml for use
    """
    def __init__(
        self,
        runtime: DirectoryRuntime,
        *,
        document_path: str,
        document_type: type[FacadeT],
        external_reference_specs: tuple[ExternalReferenceSpec, ...] = (),
        mode: str = "r",
    ):
        self._runtime = runtime
        self._document_path = runtime.resolve(document_path)
        self._mode = mode
        self._document = document_type(self._document_path, mode=mode)
        self._external_reference_specs = external_reference_specs
        self._resolved_documents: dict[tuple[type[Any], Path], _ResolvedExternalDocument] = {}
        self._resolved_placements: list[_ResolvedPlacement] = []

    def __enter__(self) -> FacadeT:
        self._document.__enter__()
        self._enter_external_documents()
        return self._document

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._leave_external_documents(persist=self._mode in {"w", "a"})
            else:
                self._leave_external_documents(persist=False)
        finally:
            self._resolved_documents.clear()
            self._resolved_placements.clear()
        return self._document.__exit__(exc_type, exc, tb)

    @property
    def path(self) -> Path:
        return self._document_path

    def _enter_external_documents(self) -> None:
        for owner, spec in self._iter_external_reference_targets(self._document.xml):
            resolved = self._load_external_document(owner, spec)
            if resolved is None:
                self._set_attr(owner, spec.document_attr, None)
                continue
            self._set_attr(owner, spec.document_attr, resolved.document)
            self._resolved_placements.append(_ResolvedPlacement(owner=owner, resolved=resolved))

    def _leave_external_documents(self, *, persist: bool) -> None:
        persisted_paths: set[tuple[type[Any], Path]] = set()
        for placement in self._resolved_placements:
            owner = placement.owner
            spec = placement.resolved.spec
            document = self._get_attr(owner, spec.document_attr)
            cache_key = (spec.facade_type, placement.resolved.path)

            if persist and document is not None and cache_key not in persisted_paths:
                self._save_external_document(placement.resolved.path, spec.facade_type, document)
                persisted_paths.add(cache_key)

            self._set_attr(owner, spec.document_attr, None)


    def _iter_external_reference_targets(self, root: Any):
        return discover_external_references(root, self._external_reference_specs)

    def _load_external_document(self, owner: Any, spec: ExternalReferenceSpec) -> _ResolvedExternalDocument | None:
        source = self._get_attr(owner, spec.source_attr)
        if not source:
            return None

        path = self._runtime.resolve(source)
        cache_key = (spec.facade_type, path)
        if cache_key in self._resolved_documents:
            return self._resolved_documents[cache_key]
        if not path.exists():
            return None

        try:
            with spec.facade_type(path, mode="r") as facade:
                resolved = _ResolvedExternalDocument(spec=spec, path=path, document=facade.xml)
        except (ValueError, OSError, ParseError, AttributeError, TypeError) as exc:
            logger.warning("Failed to load external reference %s with %s: %s", path, spec.facade_type.__name__, exc)
            return None

        self._resolved_documents[cache_key] = resolved
        return resolved

    @staticmethod
    def _save_external_document(path: Path, facade_type: type[Any], document: Any) -> None:
        with facade_type(path, mode="w") as facade:
            facade._document = document

    @staticmethod
    def _get_attr(owner: Any, attr_name: str) -> Any:
        if hasattr(owner, attr_name):
            return getattr(owner, attr_name)
        return None

    @staticmethod
    def _set_attr(owner: Any, attr_name: str, value: Any) -> None:
        if hasattr(owner, attr_name):
            setattr(owner, attr_name, value)

    @staticmethod
    def _is_leaf_value(value: Any) -> bool:
        return isinstance(value, (str, bytes, int, float, bool, Path))
