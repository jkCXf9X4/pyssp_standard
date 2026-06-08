# IMP-023: Add `build_fmu()` convenience function as IMP-022 extension

> **Status:** Proposed
> **Priority:** Critical
> **Layer:** Archive (primary) / Codec (secondary)

## Theme

Convenience function wrapping `package_archive` + `FMI_EPOCH` for building an FMU from modelDescription XML + binary map + resource map, eliminating the boilerplate of creating a temporary directory structure before calling the archive primitives.

## Evidence

### IMP-022 deterministic ZIP foundation is complete

`pyssp_standard/common/archive.py` already provides:

- `FMI_EPOCH = (2000, 1, 1, 0, 0, 0)` (line 32) — constant for deterministic timestamps
- `_write_archive_file(archive, path, arcname, date_time=None)` (lines 35–49) — accepts optional `date_time` override
- `package_archive(source_dir, archive_path, *, recursive, overwrite, fixed_timestamp)` (lines 195–256) — packages a directory into a `.fmu`/`.ssp` archive with deterministic timestamps

### No convenience function exists

The current API requires the caller to:

1. Create a temporary directory with `modelDescription.xml`, `binaries/`, `resources/`
2. Call `package_archive(directory, output_path, fixed_timestamp=FMI_EPOCH)`

There is no `build_fmu()` function that accepts in-memory content (XML string, binary dict, resource dict) and produces a ready `.fmu` archive.

### ALIGN-001 assessment

Section F4 (FMU ZIP assembly with deterministic properties) identified this as a utility gap:

> The missing piece is a high-level convenience like:
> ```python
> def build_fmu(
>     model_description_xml: str,
>     binaries: dict[str, bytes] = None,
>     resources: dict[str, bytes] = None,
>     output_path: str | Path,
>     fixed_timestamp=FMI_EPOCH,
> ) -> Path
> ```

**Recommendation from ALIGN-001:** "Merge into IMP-022 — extend the existing work with a `build_fmu()` convenience function. Reclassify as a Phase 6 of IMP-022 (post-completion enhancement)."

Since IMP-022 is already implemented and marked done, this is filed as a separate candidate (IMP-023) building on IMP-022's foundation.

## Current Pain Or Risk

1. **Boilerplate duplication** — Every tool that needs to produce a `.fmu` archive (cs-fmu-packager, test-FMU utilities, migration scripts) must create a directory, write files, call `package_archive`, then clean up. This pattern discourages in-memory FMU construction.
2. **No single-entry API** — Newcomers to the codebase can't find "how to build an FMU" as a single function. The primitives exist but are not discoverable for this specific use case.
3. **Test friction** — Tests that need custom FMUs currently rely on pre-built `.fmu` fixtures. A `build_fmu()` function would enable programmatic fixture generation.

## Proposed Improvement

### Function signature

```python
def build_fmu(
    model_description_xml: str,
    binaries: dict[str, bytes] | None = None,
    resources: dict[str, bytes] | None = None,
    output_path: str | Path,
    fixed_timestamp: tuple[int, int, int, int, int, int] = FMI_EPOCH,
) -> Path:
    """Build a deterministic FMU archive from in-memory content.

    Args:
        model_description_xml: The modelDescription.xml content as a string.
        binaries: Map of binary paths to content, e.g. {"binaries/linux64/my.so": ...}.
        resources: Map of resource paths to content, e.g. {"resources/icon.png": ...}.
        output_path: Path for the resulting .fmu file.
        fixed_timestamp: ZIP entry timestamp for reproducible builds.

    Returns:
        The resolved output Path.
    """
```

### Semantics

- `model_description_xml` is a complete XML string (the output of `Fmi2ModelDescriptionXmlCodec.serialize()`).
- `binaries` is `dict[str, bytes]` mapping archive-relative paths to binary content. Keys like `"binaries/linux64/my.so"` are written to the corresponding archive path.
- `resources` is `dict[str, bytes]` mapping archive-relative resource paths to content.
- Uses `tempfile.TemporaryDirectory` internally to create a directory structure, write files, and package via `package_archive(output_dir, output_path, fixed_timestamp=fixed_timestamp)`.
- Returns the resolved `output_path`.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Function placement | `common/archive.py` or new `common/fmu_builder.py` | Co-located with existing archive primitives; if module grows, extract to `common/fmu_builder.py` |
| Binary/resource types | `dict[str, bytes]` | Consistent with in-memory construction; bytes avoids encoding issues |
| Fixed timestamp default | `FMI_EPOCH` | Makes deterministic builds the default, consistent with IMP-022 philosophy |
| Directory cleanup | Automatic via `tempfile.TemporaryDirectory` | No temp-file leakage |

## Expected Benefit

- Single-entry API for FMU construction: `build_fmu(xml, binaries, resources, output_path)`
- Enables programmatic test-FMU generation (see IMP-027)
- Eliminates directory boilerplate in tools like cs-fmu-packager
- Deterministic by default

## Risk And Blast Radius

| Risk | Severity | Mitigation |
|------|----------|------------|
| Temp directory for large binaries | Low | Binary content is held in memory until written to temp dir; file size constrained by available disk |
| Path traversal in binary/resource keys | Low | Keys like `"../../etc/passwd"` would be constrained to a temp directory; use `Path(key).name` validation? No — archive paths are intentionally posix-style relative paths |
| No validation of XML content | Low | Caller is responsible for providing valid XML; codec.serialize() output is the expected input |

## Suggested Priority

**Critical** — This is the highest-priority gap from the ALIGN-001 assessment. IMP-022's deterministic ZIP foundation is complete, and the convenience function is the natural next step. Tools like cs-fmu-packager depend on this.

## Task Contract Seed

### Phase 1 — Implementation

1. Add `build_fmu()` function to `common/archive.py` or create `common/fmu_builder.py`:
   - Accept `model_description_xml: str`, `binaries: dict[str, bytes]`, `resources: dict[str, bytes]`, `output_path: str | Path`, `fixed_timestamp=FMI_EPOCH`
   - Create temp directory, write `modelDescription.xml`, binary files, resource files
   - Call `package_archive(output_dir, output_path, fixed_timestamp=fixed_timestamp)`
   - Return `Path(output_path)`

2. Export from `pyssp_standard/__init__.py` or document as importable from `pyssp_standard.common.archive`.

### Phase 2 — Tests

3. Create `pytest/common/test_fmu_builder.py` or extend `pytest/common/test_archive.py`:

   | Test | Purpose |
   |------|---------|
   | `test_build_fmu_minimal` | Build FMU with XML only, no binaries/resources; verify .fmu created |
   | `test_build_fmu_with_binaries` | Build with `{"binaries/linux64/test.so": b"binary"}`; verify binary present in archive |
   | `test_build_fmu_with_resources` | Build with resources dict; verify round-trip |
   | `test_build_fmu_deterministic` | Two identical calls produce identical ZIP content |
   | `test_build_fmu_output_path` | Output path has `.fmu` suffix, file exists |

### Phase 3 — Integration

4. Verify that the produced FMU can be opened with `FMU(path, mode="r")` and its model description parsed back.

## Out Of Scope

- **Non-deterministic builds** — No flag to disable fixed timestamps (use `package_archive` directly if needed).
- **Directory-based output** — Always produces a `.fmu` archive; for directory output, use `package_archive` with a directory as `archive_path` extensionless.
- **SSP integration** — No SSP wrapping; use `SSP.add_fmu()` for that.
- **FMI3 support** — FMI3 model description serialization is not yet implemented; extend when FMI3 codec is ready.
- **Validation of input content** — No XML schema validation; caller provides valid XML.
- **Compression options** — Uses `ZIP_DEFLATED` (the `package_archive` default).

## Traceability

- **Intent:** ALIGN-001 F4 — Provide FMU ZIP assembly convenience function building on IMP-022 deterministic primitives.
- **Product:** `build_fmu()` function in `common/archive.py` (or `common/fmu_builder.py`).
- **Architecture:** Archive layer (primary), Codec layer (secondary — accepts serialized XML).
- **Implementation:** New function in existing or new archive module.
- **Verification:** Tests verifying archive creation, round-trip parsing, and determinism.

## Notes

- The `_write_archive_file` helper already handles executable bits for binary paths, so binary entries in the FMU will automatically get the correct permissions.
- Temp directory approach mirrors the pattern used internally by `package_archive_directories` and recursive `package_archive`.