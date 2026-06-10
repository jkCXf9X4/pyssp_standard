# IMP-028: Formalize Reproducibility as a Non-Functional Requirement (NFR-001 / QA-001)

> **Status:** Implemented
> **Priority:** Medium
> **Layer:** Archive (core), Quality Attributes (cross-cutting)

## Theme

Formalize "reproducibility" as a concrete, testable non-functional requirement for the pyssp_standard project: given the same specification files and tool version, running the build process twice produces byte-identical FMU/SSP archives.

## Motivation

IMP-022 ("Deterministic ZIP timestamps for reproducible archive builds") resolved ZIP entry timestamps — the dominant source of non-determinism — by introducing `FMI_EPOCH` as the default timestamp on all archive creation paths. However, `FMI_EPOCH` is only one defense. Without a formal NFR that enumerates every known source of non-determinism and its status, future changes risk silently reintroducing byte-level variation.

This candidate formalizes the emerging QA-001 / NFR-001 reproducibility requirement that the project already partially satisfies, making its scope explicit and verifiable.

## Evidence

### 1. Resolved: ZIP entry timestamps (`FMI_EPOCH`)

**Implementation:**
- `pyssp_standard/common/archive.py` — `FMI_EPOCH = (2000, 1, 1, 0, 0, 0)` (line 32)
- `_write_archive_file()` accepts `date_time` parameter (line 35–49); when set, overrides `ZipInfo.from_file()` mtime
- `package_archive()`, `package_archive_directories()`, and `_pack_directory_as_archive()` all thread `fixed_timestamp` through
- `pyssp_standard/common/archive_runtime.py` — `ArchiveRuntime.__init__` accepts `fixed_timestamp`, passes to `package_archive()` in `_commit()` (line 72–73)
- `pyssp_standard/fmu.py` — `FMU.__init__` and `FMU.create()` default to `fixed_timestamp=FMI_EPOCH` (lines 13–17, 47–62)
- `pyssp_standard/ssp.py` — `SSP.__init__` defaults to `fixed_timestamp=FMI_EPOCH` (line 35–45)
- `FMU.package_as_ssp()` uses `FMI_EPOCH` when creating the destination SSP (line 109)

**Test:** `pytest/fmi2/archive/test_fmu.py::test_fmu_create_deterministic` (lines 303–335) — creates two FMUs with identical inputs and `FMI_EPOCH`, asserts identical SHA256 hashes.

**Status:** ✅ RESOLVED — all archive creation paths default to `FMI_EPOCH`.

### 2. Resolved: File ordering within archives

**Implementation:**
- `_pack_directory_as_archive()` iterates with `sorted(source_dir.rglob("*"))` (archive.py line 143)
- `package_archive()` iterates with `sorted(archive_root.rglob("*"))` (archive.py line 244)
- `package_archive_directories()` sorts candidates by path depth descending (archive.py lines 189–192)

`sorted()` produces a deterministic, platform-independent iteration order on any filesystem that lists files in directory-order. This ensures entries are always written in the same sequence.

**Status:** ✅ RESOLVED — all archive iteration uses `sorted()` for platform-independent ordering.

### 3. Resolved: ZIP compression level

**Implementation:**
- All archives use `compression=zipfile.ZIP_DEFLATED` (archive.py lines 44, 141, 242)

`zipfile.ZIP_DEFLATED` uses a deterministic compression implementation in CPython's `zlib` module. The same input bytes at the same compression level always produce the same compressed output.

**Status:** ✅ RESOLVED — uniform `ZIP_DEFLATED` level (default zlib level 6).

### 4. Resolved: External file attributes (executable bits)

**Implementation:**
- `_write_archive_file()` sets `info.external_attr` only for paths under `binaries/` (archive.py lines 45–46)
- The executable-bits logic (`_with_executable_bits`, `UNIX_PERMISSION_SHIFT`) is derived from `path.stat().st_mode` and is deterministic for the same input files

**Status:** ✅ RESOLVED — attribute computation is deterministic; binary-path check is stable.

### 5. Open: Generation date/time in XML metadata

**Context:**
- `ModelDescription`, `SSD`, `SSV`, `SSM`, `SRMD`, `SSB`, and `SSP` all expose `set_generation_date_and_time(dt)` with a default of `"2000-01-01T00:00:00Z"` when `dt=None`.
- `pyssp_standard/common/datetime_utils.py::format_generation_datetime(dt=None)` returns `"2000-01-01T00:00:00Z"` (line 17).

**Risk:**
The helper exists with a reasonable default, **but none of the archive creation paths (FMU.create, SSP.__init__ in "w" mode, FMU.package_as_ssp) call `set_generation_date_and_time()` automatically**. The metadata `generationDateAndTime` attribute in the XML documents is set to the current time by the codec only when the document is first parsed from a tool that wrote it, and is absent for newly-created documents via `_create_document()`.

For example:
- `Fmi2ModelDescriptionDocument.__init__` (model_description.py line 86) sets `generation_date_and_time: str | None = None` — no value by default
- `Ssc1MetaData.__init__` (ssc_model.py line 22) has `generation_date_and_time: str | None = None`

When `generationDateAndTime` is absent from a newly-written document, it does not appear in the XML output. This means the attribute is **not** a source of non-determinism for new archives (it's absent in both runs). However, if a consumer of the library reads an FMU with an existing `generationDateAndTime` and re-serializes without resetting it, the timestamp persists deterministically.

**Status:** ⚠️ LOW-RISK OPEN — no automatic `generationDateAndTime` injection happens on archive creation, so it is not currently a source of non-determinism. If future changes add auto-timestamping with `datetime.now()`, this would reintroduce non-determinism. Mitigation: document the constraint and gate any future auto-timestamping behind `fixed_timestamp`-style control.

### 6. Open: Namespace prefix spelling in XML serialization

**Context:**
- `04-verification/acceptance-criteria.md` lines 76–78 explicitly exclude namespace prefix spelling from round-trip guarantees.
- CPython's `ElementTree` writes namespace prefixes deterministically for a given parse-serialize cycle, but the choice of prefix for the same namespace can vary if the parser encounters different prefix-to-URI mappings in the input.

**Risk:**
If two runs process XML input files with different namespace prefix conventions (e.g., `ssp:` vs `default:` for the same URI), the serialized XML may differ in prefix spelling even though all content is logically identical. This would produce different archive SHA256 hashes.

**Status:** ⚠️ LOW OPEN — applies only when input documents have non-canonical prefix spellings. Mitigation: normalize namespace prefixes during parse (existing behavior in codecs) and document the constraint as an acceptance-criteria item.

### 7. Not applicable: ZIP metadata fields (comment, extra)

- `zipfile.ZipFile` with `mode="w"` creates archives without global comments or per-file extra fields unless explicitly set.
- The codebase never sets `ZipInfo.comment` or `ZipInfo.extra`.
- Result: these fields are always empty string/b'\x00\x00' and do not vary between runs.

**Status:** ✅ NOT APPLICABLE — no non-deterministic ZIP metadata.

### 8. Not applicable: Input file content

- Reproducibility is defined as "same specification files" → "same output". The input is assumed constant. Variation in input file content is outside scope.

**Status:** ✅ NOT APPLICABLE — input invariance is a precondition.

## Non-Functional Requirement Specification

### NFR-001: Reproducible Archive Build

**Statement:** Given the same set of specification files (modelDescription.xml, binaries, resources, parameter files) and the same tool version, any two invocations of `FMU.create()`, `SSP.__init__(mode="w")`, or `FMU.package_as_ssp()` SHALL produce byte-identical archive files (as verified by SHA256 hash comparison).

**Scope:**
- `FMU.create()` — FMU archive from model description + binaries + resources
- `SSP` in write mode — SSP archive from scratch
- `FMU.package_as_ssp()` — SSP archive wrapping an existing FMU
- `SSP.add_fmu()` — adding an FMU resource to an existing SSP (when committed)

**Out of scope:**
- Archive unpacking (`unpack_archive()`) — reading timestamps is inherently not byte-identical
- Directory-mode SSP/FMU access (no archive produced)
- Archives produced by third-party tools (input invariance precondition)
- Cross-version tool reproducibility (same tool version required)

### QA-001: Reproducibility Quality Attribute

**Attribute:** Reproducibility
**Target:** Byte-identical archives from identical inputs and tool version
**Evidence:** SHA256 hash comparison across repeated invocations
**Layer:** Archive (core), cross-cutting verification requirement

## Non-Determinism Source Register

| ID | Source | Status | Mitigation | Verification |
|----|--------|--------|------------|-------------|
| ND-001 | ZIP entry timestamps | ✅ RESOLVED | `FMI_EPOCH` default on all archive creation paths | `test_fmu_create_deterministic` |
| ND-002 | ZIP entry ordering | ✅ RESOLVED | `sorted()` iteration in all archive packaging | Implicit (no test) |
| ND-003 | ZIP compression level | ✅ RESOLVED | Uniform `ZIP_DEFLATED` | Implicit (no test) |
| ND-004 | External file attributes | ✅ RESOLVED | Deterministic executable-bit computation | Implicit (no test) |
| ND-005 | XML `generationDateAndTime` | ⚠️ LOW OPEN | No auto-injection on archive creation; `set_generation_date_and_time(None)` defaults to epoch | No explicit guardrail test |
| ND-006 | XML namespace prefix spelling | ⚠️ LOW OPEN | Existing codec normalization; documented exclusion from round-trip guarantee | Covered by AC-008 scope note |
| ND-007 | ZIP extra fields / comments | ✅ N/A | Never set by library | N/A |
| ND-008 | Input file content variation | ✅ N/A | Precondition: same input files | N/A |

## Acceptance Criteria (New / Extended)

### AC-DET-001: FMU deterministic archive (existing)
Two `FMU.create()` calls with identical model description, binaries, and resources, using `fixed_timestamp=FMI_EPOCH`, produce identical SHA256 hashes.
- **Verification:** `pytest/fmi2/archive/test_fmu.py::test_fmu_create_deterministic` ✅ Existing
- **Traceability:** NFR-001 → AC-DET-001 → ND-001

### AC-DET-002: SSP deterministic archive (new — recommended)
Two `SSP.__init__(path, mode="w")` contexts with identical FMU additions produce identical SHA256 hashes.
- **Verification:** Proposed test `pytest/ssp1/archive/test_ssp_deterministic.py`
- **Traceability:** NFR-001 → AC-DET-002 → ND-001, ND-002, ND-003, ND-004

### AC-DET-003: FMU.package_as_ssp deterministic (new — recommended)
Two `FMU.package_as_ssp()` calls with the same FMU produce identical SHA256 hashes.
- **Verification:** Proposed test in existing `pytest/fmi2/archive/test_fmu.py` or `pytest/ssp1/archive/`
- **Traceability:** NFR-001 → AC-DET-003 → ND-001, ND-002, ND-003, ND-004

### AC-DET-004: Deterministic archive after resource modification (new — recommended)
Adding the same resource file twice across separate SSP sessions produces the same archive hash for the added resource entries. (Verifies that `add_resource()` → `add_file()` preserves deterministic timestamps.)
- **Verification:** Proposed test
- **Traceability:** NFR-001 → AC-DET-004 → ND-001

### AC-DET-005: XML generationDateAndTime stability (new — recommended)
A document created without calling `set_generation_date_and_time()` must not include a `generationDateAndTime` attribute that varies between runs. Conversely, calling `set_generation_date_and_time(None)` must always serialize `"2000-01-01T00:00:00Z"`.
- **Verification:** Proposed test per facade (MD, SSD, SSV, SSM, SRMD, SSB)
- **Traceability:** NFR-001 → AC-DET-005 → ND-005

## Relation to Existing Artifacts

| Artifact | Relationship |
|----------|-------------|
| IMP-022 (Deterministic ZIP timestamps) | **Precursor.** IMP-022 implemented the timestamp fix; this NFR formalizes the broader reproducibility requirement |
| `FMI_EPOCH` constant (`archive.py:32`) | **Direct dependency.** The default timestamp value used by all archive paths |
| `datetime_utils.format_generation_datetime(None)` | **Related.** Provides `"2000-01-01T00:00:00Z"` default matching `FMI_EPOCH` convention |
| `04-verification/acceptance-criteria.md` AC-008 | **Extends.** AC-008 covers element order preservation; AC-DET-001–005 extend into byte-level determinism |
| `02-architecture/quality-attributes.md` | **Extends.** Adds "Reproducibility" to the quality attributes table |
| `06-evolution/improvement-backlog.md` G25 | **Resolved by.** G25 (non-deterministic ZIP timestamps) is marked done via IMP-022 |
| `traceability-map.md` | **Extends.** Adds NFR-001 / QA-001 traceability chain |

## Expected Benefit

- **Explicit contract:** Consumers and CI pipelines can rely on archive hash stability as a documented behavior, not an accident of the current implementation.
- **Regression guard:** The sources-of-non-determinism table and acceptance criteria prevent future changes from silently reintroducing byte-level variation.
- **Traceability:** NFR-001 connects the existing IMP-022 work to the broader quality-attribute layer, closing the gap between implementation and requirement.
- **CI enablement:** Formal reproducibility enables content-addressed caching, FMU fingerprinting, and git-tracked generated archives with stable diffs.

## Risk And Blast Radius

| Risk | Severity | Mitigation |
|------|----------|------------|
| Adding tests that fail on platforms with different `zlib` output | Low | CPython's `zlib` is deterministic per version; variant would indicate a fundamental platform issue, not a library bug |
| Over-constraining serializer behavior | Low | AC-DET-005 is scoped to absence of variable `generationDateAndTime`, not to specific XML formatting |
| New contributors unaware of NFR break it silently | Medium | Explicit NFR documentation + CI deterministic build check (future) would catch regression at PR time |
| Third-party FMU archives with non-standard compression | None | NFR applies only to archives *created* by this library; third-party archives are input |

## Suggested Priority

**Medium** — Formalizes an existing emergent behavior (archives already produce deterministic output). The main value is in documentation, traceability, and regression prevention rather than new functionality. Comparable to compliance/best-practice work.

## Task Contract Seed

### Phase 1 — NFR artifact creation (this candidate)
1. ✅ Create this candidate document with NFR-001 / QA-001 specification, source register, and acceptance criteria.

### Phase 2 — Acceptance criteria tests (recommended)
2. Add `pytest/ssp1/archive/test_ssp_deterministic.py`:
   - `test_ssp_create_deterministic`: Two SSPs with identical FMU → identical SHA256
   - `test_ssp_add_resource_deterministic`: Two SSPs adding same resource → identical hash for resource entries
3. Add `pytest/fmi2/archive/test_fmu_package_deterministic.py`:
   - `test_fmu_package_as_ssp_deterministic`: Two `package_as_ssp()` calls → identical SHA256
4. Add facade-level `generationDateAndTime` stability tests:
   - One test per facade (MD, SSD, SSV, SSM, SRMD, SSB) verifying no auto-injection and `set_generation_date_and_time(None)` produces `2000-01-01T00:00:00Z`

### Phase 3 — Documentation updates (recommended)
5. Update `02-architecture/quality-attributes.md`:
   - Add row to the quality attributes table:
     | **Reproducibility** | Generated FMU/SSP artifacts are byte-identical from same specification and tool version | `04-verification/acceptance-criteria.md` — AC-DET-001–005 |
6. Update `04-verification/acceptance-criteria.md`:
   - Add AC-DET-001 through AC-DET-005 under a new "Deterministic Builds" section
7. Update `traceability-map.md`:
   - Add NFR-001 / QA-001 traceability chain

### Phase 4 — Decision record (recommended)
8. Create `product-breakdown/06-evolution/decisions/DEC-IMP028-R1-001.md`:
   - Documents the choice of `FMI_EPOCH` as the canonical zero-timestamp default
   - Documents the reproducibility scope boundaries
   - Documents the acceptance criteria design

### Phase 5 — CI / Workflow guard (optional, future)
9. Add a CI step that runs the deterministic-build test suite and asserts archive hash stability across Python versions / platforms.

## Out Of Scope

- **Compression level tuning** — keeping `ZIP_DEFLATED` default level 6. Adding `compresslevel` control would be a separate feature.
- **Cross-tool reproducibility** — archives from this library vs. archives from Dymola/OpenModelica. NFR-001 is scoped to single-tool-version invariance.
- **Archive digital signatures** — signed/checksummed archives are outside scope.
- **Non-ZIP output formats** — the library creates `.fmu`/`.ssp` archives only.
- **SSP2 skeleton reproducibility** — SSP2 archive creation is not implemented yet; NFR-001 applies when SSP2 becomes active.

## Traceability

- **Intent:** INT-002 (Reliable inspection / extraction of FMU archives), extended to creation
- **Product:** FMU archive creation, SSP archive creation, FMU→SSP packaging
- **Architecture:** Archive Layer (`common/archive.py`, `common/archive_runtime.py`), cross-cutting Quality Attributes
- **Implementation:** Existing (`archive.py`, `fmu.py`, `ssp.py`, `datetime_utils.py`), proposed test files
- **Verification:** AC-DET-001 (existing), AC-DET-002–005 (proposed)
- **Backlog:** G25 → IMP-022 → NFR-001 (this candidate)
- **External spec:** Gap 9 (no deterministic timestamps) from pyssp_standard Fork Improvement Specification, now broadened to full NFR

## Notes

- The existing `test_fmu_create_deterministic` test only covers `FMU.create()` with explicit `fixed_timestamp=FMI_EPOCH`. It does not verify that the default `FMI_EPOCH` is applied (the default test path trusts the constructor default). An explicit default-verification assertion would strengthen coverage.
- SSP-level deterministic tests (AC-DET-002, AC-DET-003) are the highest-value additions because SSP archives exercise the full stack: `ArchiveRuntime._commit()` → `package_archive()` → recursive directory packaging → sorted iteration → timestamp override.
- The `generationDateAndTime` risk (ND-005) is low in practice because no code path currently auto-injects it on archive creation. However, it is the most likely source of accidental non-determinism in future changes because every model/facade has a `set_generation_date_and_time()` method that could be called with `datetime.now()`.
- The namespace prefix risk (ND-006) is architecture-level. It is shared across all XML facades and would require a central serializer normalization strategy to resolve.
