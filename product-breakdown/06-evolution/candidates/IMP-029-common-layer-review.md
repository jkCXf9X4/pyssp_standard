# IMP-029: Common Layer Structural Review — Runtime, Archive, XML, Reference Handling

> **Status:** Proposed
> **Priority:** Medium
> **Layer:** Common (all sub-layers)

## Theme

Structured critical review of `pyssp_standard/common/` — the shared implementation layer for archive I/O, XML document lifecycle, cross-document reference resolution, and runtime context management. Identifies 7 actionable findings spanning cohesion, coupling, abstraction consistency, error handling, and API usability.

---

## Findings

### F-001: `ArchiveRuntime` is a pure delegation shell over `DirectoryRuntime` internals

| Field | Value |
|-------|-------|
| **Area** | Runtime layer |
| **File(s)** | `archive_runtime.py`, `directory_runtime.py` |
| **Severity** | Low |
| **Layer** | Common |
| **Category** | Cohesion, Coupling |

**Evidence:**

`archive_runtime.py` lines 50–71 — all 7 public methods are thin delegates:

```python
@property
def root(self) -> Path:
    return self._directory_runtime.root       # line 51

def resolve(self, path: str | Path) -> Path:
    return self._directory_runtime.resolve(path)   # line 55

def namelist(self) -> list[str]:
    return self._directory_runtime.namelist()      # line 58

def read_text(self, name: str, ...) -> str:
    return self._directory_runtime.read_text(...)  # line 61

def add_file(self, source, target_name=None) -> str:
    return self._directory_runtime.add_file(...)   # line 64

def remove_file(self, target_name) -> None:
    self._directory_runtime.remove_file(target_name)  # line 67

def list_prefix(self, prefix) -> list[str]:
    return self._directory_runtime.list_prefix(prefix) # line 70
```

The only independent logic is `_commit()` (line 72–73) and the context manager orchestration in `__enter__` / `__exit__`.

Additionally, `ArchiveRuntime` directly accesses `self._directory_runtime._root` (line 35) — reaching into a private attribute of another class — breaking encapsulation.

**Current pain/risk:**

1. Every delegation method is pure boilerplate. Adding a new `DirectoryRuntime` method requires a matching delegate in `ArchiveRuntime`.
2. `_root` access violates encapsulation — any refactoring of `DirectoryRuntime._root` would silently break `ArchiveRuntime`.
3. The dual-class design forces `create_runtime()` (lines 76–86) to decide at construction time, which complicates the caller interface.

**Recommendation:**

- Extract a shared `RuntimeProtocol` (or `AbstractRuntime`) interface, making the delegation contract explicit. `ArchiveRuntime` can then delegate through the protocol rather than mirroring every method.
- Alternatively, inline the `DirectoryRuntime` usage via composition with a proper interface, eliminating the private-attribute access.
- At minimum, document the delegation relationship and add a test that verifies `ArchiveRuntime` stays in sync with `DirectoryRuntime`'s public API.

---

### F-002: `XmlDocument` codec/validator wiring has two competing patterns

| Field | Value |
|-------|-------|
| **Area** | XML |
| **File(s)** | `xml_document.py`, `ssd.py`, `ssv.py`, `ls_ref.py` |
| **Severity** | Medium |
| **Layer** | Common |
| **Category** | Consistency, Abstraction |

**Evidence:**

Pattern A — Hardcoded in subclass `__init__` (4 of 6 facades):

- `ssd.py` lines 42–43: `self._codec = Ssp1SsdCodec(); self._validator = Ssp1SsdValidator()`
- `ls_ref.py` line 22: `self._codec = LSRefManifestCodec(); ...`
- `ls_ref.py` line 34: `self._codec = LSRefExperimentsCodec(); ...`
- `srmd.py`, `ssb.py` follow the same pattern

Pattern B — Via `get_codec_and_validator()` (2 of 6 facades):

- `ssv.py` line 25: `self._codec, self._validator = self.get_codec_and_validator("SSP", "SSV")`
- `md.py`: `self._codec, self._validator = self.get_codec_and_validator("FMI", "MD")`

The `get_codec_and_validator()` method itself lives on `XmlDocument` (lines 39–51) and performs version detection from the file — but only when `mode != "w"`. In write mode, version is empty and routing may produce no match.

**Current pain/risk:**

1. **Version routing bypassed**: 4 of 6 facades hardcode codec/validator classes. Adding a new SSP version (e.g. SSP2 SSD) requires editing `ssd.py`, `ls_ref.py`, `srmd.py`, `ssb.py` individually, even though `version_routing.py` already has the registry mechanism.
2. **Write-mode blind spot**: `get_codec_and_validator()` version-detects from file content. For new documents (write mode), no file exists → version is empty string → `get_codec_and_validator()` may return `(None, None)`, forcing the caller to provide a `version` argument manually (as `ssv.py` does at line 23).
3. **Duplicated lifecycle**: `check_compliance()` (line 59) re-serializes for validation. `save_document()` (line 74) re-serializes again. No caching of serialized output.

**Recommendation:**

- Migrate all 6 facades to use `get_codec_and_validator()` through the version routing mechanism (Pattern B everywhere).
- Eliminate the `_codec` / `_validator` as instance attributes set by subclasses. Instead, resolve them lazily — or at a single explicit point — from the routing layer.
- For write mode, add a `version` parameter to `get_codec_and_validator()` so callers can supply it explicitly without subclass hacks.

---

### F-003: `DocumentRuntime._load_external_document` swallows all exceptions silently

| Field | Value |
|-------|-------|
| **Area** | Reference handling / discovery |
| **File(s)** | `document_runtime.py` |
| **Severity** | Medium |
| **Layer** | Orchestration |
| **Category** | Error handling, Debuggability |

**Evidence:**

`document_runtime.py` lines 115–119:

```python
try:
    with spec.facade_type(path, mode="r") as facade:
        resolved = _ResolvedExternalDocument(spec=spec, path=path, document=facade.xml)
except Exception:
    return None
```

This catches every Python exception — `SyntaxError`, `KeyError`, `IOError`, `AttributeError`, `ImportError`, `TypeError` — and converts it to a silent `None` return.

**Current pain/risk:**

1. **Silent failures**: If an external SSV file has XML that parses but is semantically wrong (missing required fields), the facade `__enter__` may raise — and the error is swallowed. The caller sees `parameter_set=None` on the binding with no indication why.
2. **No log or diagnostic**: There is no `logging.warning`, no `logging.debug`, no counter, no health metric. When `discover_external_references` finds a source but `_load_external_document` returns `None`, the only way to diagnose is to add a `breakpoint()`.
3. **Test coverage gap**: No test verifies that a broken external document produces an informative diagnostic. The tests in `pytest/common/test_reference_discovery.py` only test the discovery function, not the load path.

**Recommendation:**

- Replace bare `except Exception` with targeted exception handling (e.g. `except (FileNotFoundError, ParseError, ValueError)`).
- Log non-fatal failures at `logging.warning` level with the path, facade type, and exception message.
- Keep `None` return as the contract for "reference not loadable" but make the *reason* discoverable at `DEBUG` or `WARNING` level.
- Add test coverage for load-failure scenarios (missing file, malformed XML, facade init failure).

---

### F-004: `create_runtime()` uses file-extension heuristics that blur directory vs. archive semantics

| Field | Value |
|-------|-------|
| **Area** | Runtime layer / Archive |
| **File(s)** | `archive_runtime.py` |
| **Severity** | Low |
| **Layer** | Common |
| **Category** | API usability, Consistency |

**Evidence:**

`archive_runtime.py` lines 76–86:

```python
def create_runtime(path, mode="r", fixed_timestamp=None):
    resolved_path = Path(path)
    if resolved_path.is_dir():
        return DirectoryRuntime(resolved_path, mode)
    if resolved_path.exists():
        return ArchiveRuntime(resolved_path, mode, fixed_timestamp=fixed_timestamp)
    if resolved_path.suffix.lower() in {".ssp", ".fmu"}:
        return ArchiveRuntime(resolved_path, mode, fixed_timestamp=fixed_timestamp)
    return DirectoryRuntime(resolved_path, mode)
```

**Current pain/risk:**

1. **Heuristic chain**: The decision logic prioritizes `path.exists()` over suffix. If someone passes a non-existent directory path (common in "w" mode), they get `DirectoryRuntime` — but only because of the fallthrough, not by explicit intent.
2. **Surprise routing**: A non-existent path ending in `.ssp` always creates `ArchiveRuntime`. A non-existent path without a known suffix always creates `DirectoryRuntime`. This asymmetry is undocumented.
3. **`fixed_timestamp` leak**: The `fixed_timestamp` parameter is only meaningful for `ArchiveRuntime` but appears in the API signature for `create_runtime()`. `DirectoryRuntime` ignores it silently.

**Recommendation:**

- Replace the heuristics with an explicit `runtime_type` parameter or separate factory methods: `open_archive(path, mode)` and `open_directory(path, mode)`.
- If the heuristic must stay, document the decision tree clearly and add test coverage for edge cases (non-existent directory, non-existent archive path, path without suffix in "w" mode).
- Consider making `fixed_timestamp` an `ArchiveRuntime`-only parameter via keyword-only dispatch.

---

### F-005: `discover_external_references` traverses entire object graph with no depth limit or type filter

| Field | Value |
|-------|-------|
| **Area** | Reference handling / discovery |
| **File(s)** | `reference_discovery.py` |
| **Severity** | Low |
| **Layer** | Orchestration |
| **Category** | Completeness, Performance |

**Evidence:**

`reference_discovery.py` lines 28–65 — the core walk loop visits every attribute of every dataclass:

```python
stack = [root]
while stack:
    current = stack.pop()
    ...
    if is_dataclass(current):
        stack.extend(
            value for value in vars(current).values()
            if not _is_leaf_value(value)
        )
```

This means it traverses the *entire* `Ssd1SystemStructureDescription` object tree — model variables, connectors, parameter bindings, parameter values, units, experiment settings — looking for instances matching `ExternalReferenceSpec.owner_type`.

**Current pain/risk:**

1. **Unnecessary traversal**: For a typical SSP model with 100+ parameters, the tree may contain thousands of nodes. Most are never reference owners. The walk visits every single one.
2. **No pruning**: There is no mechanism to say "stop walking into this branch". If a large `Ssd1ParameterSet` contains hundreds of entries, the walk still descends into each one looking for `Ssd1ParameterBinding` instances — which will never appear inside a parameter set.
3. **No cycle detection beyond `id()`**: Visited-set uses `id(current)` (line 36), which is safe for identity dedup but consumes memory proportional to total object count, not reference count.

**Recommendation:**

- Add an optional `prune_predicate` parameter — a callable `(obj) -> bool` that skips subtree descent for types known to never contain references.
- At minimum, add a docstring note about worst-case traversal cost and guidance for large models.
- Consider whether the walk could short-circuit once all spec types have been matched and all paths exhausted.

---

### F-006: `ExternalReferenceSpec` is a plain class with no validation or type safety

| Field | Value |
|-------|-------|
| **Area** | Reference handling / discovery |
| **File(s)** | `document_runtime.py`, `reference_specs.py` |
| **Severity** | Low |
| **Layer** | Common |
| **Category** | API usability, Error handling |

**Evidence:**

`document_runtime.py` lines 14–19:

```python
class ExternalReferenceSpec:
    def __init__(self, owner_type, source_attr, document_attr, facade_type):
        self.owner_type = owner_type
        self.source_attr = source_attr
        self.document_attr = document_attr
        self.facade_type = facade_type
```

No validation: `owner_type` could be a string, an int, or a non-dataclass. `source_attr` and `document_attr` could be attribute names that don't exist on `owner_type`. `facade_type` could be any callable.

The catch-all `_get_attr` / `_set_attr` helpers (lines 130–138 of `document_runtime.py`) silently return `None` for missing attributes, masking misconfiguration.

**Current pain/risk:**

1. **Misconfiguration is silent**: If someone adds `ExternalReferenceSpec(owner_type=Ssd1ParameterBinding, source_attr="sorc", ...)` (typo in "source"), `_load_external_document` will always return `None` because `_get_attr` returns `None` for the missing attribute.
2. **No early validation**: Specs are created at module level in `reference_specs.py` and only exercised at runtime when a document enters `DocumentRuntime.__enter__`. A typo is invisible until integration test time.
3. **No type safety for facade_type**: `facade_type` is used as a constructor (`spec.facade_type(path, mode="r")`). If it's not a concrete class or factory, the `except Exception` in `_load_external_document` swallows the error.

**Recommendation:**

- Add `__init_subclass__` or `__init_post_check__` (or a `@dataclass(frozen=True)` conversion) that validates:
  - `owner_type` has `source_attr` as an attribute (or at least as a class annotation).
  - `owner_type` has `document_attr` similarly.
  - `facade_type` is a class (via `inspect.isclass`) or has `__call__`.
- Consider making `ExternalReferenceSpec` a frozen dataclass for immutability and `__repr__`.
- Add a module-level test in `pytest/common/` that instantiates the real `EXTERNAL_REFERENCE_SPECS` and asserts all specs pass validation.

---

### F-007: `XmlSchemaValidator` loads and parses XSD at construction time with no caching

| Field | Value |
|-------|-------|
| **Area** | XML |
| **File(s)** | `xml_schema_validation.py` |
| **Severity** | Low |
| **Layer** | Common |
| **Category** | Performance, API usability |

**Evidence:**

`xml_schema_validation.py` lines 21–24:

```python
class XmlSchemaValidator:
    def __init__(self, schema_path: Path, *, error_prefix: str):
        self.schema_path = schema_path
        self.error_prefix = error_prefix
        self._schema = etree.XMLSchema(etree.parse(str(self.schema_path)))
```

Every validator instance parses its XSD file and builds the schema object. Multiple validator instances for the same schema (e.g., two `Ssp1SsdValidator` instances) each re-parse the same XSD.

**The `FileNotFoundError` in `resolve_schema_path`** (line 14) uses a string that is not a valid POSIX path:

```python
def resolve_schema_path(*parts):
    schema_path = SCHEMA_ROOT.joinpath(*parts)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema does not exist: {schema_path}")
    return schema_path
```

The join with `*parts` on a `Path` object does not produce valid filesystem paths when `parts` contains path separators.

**Current pain/risk:**

1. **Repeated XSD parsing**: Each validation instance re-parses. In a typical test suite that opens multiple SSD documents, this is wasteful.
2. **No schema compilation caching**: `etree.XMLSchema(etree.parse(...))` can be expensive for large FMI/FMU schemas.
3. **`resolve_schema_path` reliability**: The function returns a `Path` but callers use it with `*parts` containing subdirectory components. The `*parts` unpacking against `Path.joinpath` works correctly with path components, but callers may pass things like `"SSP1/SSD/SspSsd.xsd"` as a single `*parts` argument, which would break. This is not currently an issue because callers split components explicitly.

**Recommendation:**

- Add a module-level LRU cache (or `functools.lru_cache`) keyed on `schema_path` so that multiple `XmlSchemaValidator` instances for the same schema share one `etree.XMLSchema` object.
- Document the `resolve_schema_path` contract clearly: `*parts` must be individual path components, not slash-separated strings.
- Consider lazy schema loading — parse only when `validate_xml()` is first called — to defer the I/O cost.

---

## Blast Radius

| Finding | Impact | Affected Consumers |
|---------|--------|--------------------|
| **F-001** `ArchiveRuntime` delegation shell | Low — maintenance friction; new methods require double implementation | `SSP` facade, `FMU` facade, `create_runtime()` callers |
| **F-002** Codec/validator dual wiring | Medium — every new version/format requires editing 4+ facade files; version routing is bypassed | `SSD`, `SSV`, `SSM`, `SSB`, `SRMD`, `LSRefManifest`, `LSRefExperiments` facades |
| **F-003** Silent `except Exception` | Medium — debugging external reference failures is opaque; production failures may go unnoticed | `SSP.system_structure()` callers, `DocumentRuntime` clients, any consumer of cross-file references |
| **F-004** `create_runtime()` heuristics | Low — edge-case surprises in write mode; undocumented decision tree | `SSP.__init__`, `FMU.__init__`, all callers of `create_runtime()` |
| **F-005** Unbounded object graph traversal | Low — performance concern for very large models; no escape hatch | `DocumentRuntime._enter_external_documents()` |
| **F-006** `ExternalReferenceSpec` no validation | Low — silent misconfiguration; typo invisible until integration test | `reference_specs.py` maintainers, new standard integration authors |
| **F-007** XSD parsed per-validator instance | Low — test suite start-up cost; repeated `etree.parse` | All `XmlSchemaValidator` subclasses, test suite performance |

**Cross-cutting summary**: F-002 is the highest-impact finding — it directly undermines the version-routing architecture. F-003 is the highest-risk finding for production debugging. The remaining findings are maintenance hygiene with low immediate risk.

---

## Traceability

| Artifact | Location |
|----------|----------|
| **F-001 evidence** | `archive_runtime.py:51-71` (delegation), `archive_runtime.py:35` (`_root` access) |
| **F-002 evidence** | `xml_document.py:39-51` (routing method), `ssd.py:42-43` (hardcoded pattern), `ssv.py:25` (routed pattern), `ls_ref.py:22,34` (hardcoded pattern) |
| **F-003 evidence** | `document_runtime.py:115-119` (`except Exception`) |
| **F-004 evidence** | `archive_runtime.py:76-86` (heuristic chain) |
| **F-005 evidence** | `reference_discovery.py:28-65` (full graph walk), `reference_discovery.py:36` (`id()`-based visited) |
| **F-006 evidence** | `document_runtime.py:14-19` (`ExternalReferenceSpec`), `document_runtime.py:130-138` (`_get_attr`/`_set_attr` silent None) |
| **F-007 evidence** | `xml_schema_validation.py:21-24` (eager parse), `xml_schema_validation.py:11-15` (`resolve_schema_path`) |
| **Backlog** | `product-breakdown/06-evolution/improvement-backlog.md` — added IMP-029 entry |
| **Existing resolved** | IMP-001/002/003 (DocumentRuntime consolidation, reference extraction, spec unification) — verified not re-reported |

---

## Duplicate Check

| Check | Result |
|-------|--------|
| F-001 vs IMP-001/IMP-008 | No overlap — IMP-001 consolidated DocumentRuntime subclasses; F-001 is about ArchiveRuntime↔DirectoryRuntime delegation, not DocumentRuntime. Distinct concern. |
| F-002 vs IMP-004/IMP-014 | Related but distinct — IMP-004/IMP-014 address facade routing for SSP versioning. F-002 identifies the concrete codec/validator wiring inconsistency across all 6 XML facades. |
| F-003 vs any existing item | No overlap — no backlog item addresses `except Exception` swallowing in `_load_external_document`. |
| F-004 vs any existing item | No overlap — `create_runtime` heuristics are not discussed in any existing candidate. |
| F-005 vs any existing item | No overlap — graph traversal performance is not addressed in the backlog. |
| F-006 vs any existing item | No overlap — `ExternalReferenceSpec` validation is not discussed. |
| F-007 vs any existing item | No overlap — XSD parsing cost is not addressed. |

All 7 findings are new and do not duplicate resolved IMP items.

---

## Notes

- This review was performed in `candidate_capture` mode — no source code was modified.
- Line numbers reflect the source at commit time; verify before implementing.
- F-005 (graph traversal) is a performance concern only for very large models with thousands of dataclass nodes. For typical SSP models with <500 nodes, the cost is negligible.
- F-003 (silent `except Exception`) is the highest-priority fix from a production-readiness perspective. It is also the narrowest-scope change — targeted exception handling in one method.
- F-002 (codec/validator wiring) is the highest-impact architectural improvement but requires changes across 6 facade files plus `xml_document.py` — best approached as a phased migration.