# T-005: Recognise header-less `FoamFile` dictionaries; pin real banner recognition

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Plan:** docs/plans/openfoam-compatibility.md, bug B2 (corrected 2026-10-19)

## Goal
`pf.init` loads dictionary files that start directly with a `FoamFile` block and have no banner; today they are silently left out. The real banner styles (Foundation open, ESI boxed and foam-extend boxed), which are recognised today, are pinned by tests so they stay recognised.

## Correction (2026-10-19)
The earlier claim that boxed ESI files are dropped was **wrong**. It came from a probe file written from memory that had single backslashes (`| \      /  F ield`), whereas real files have `\\`. Real files fetched on 2026-10-19 are all recognised today by `_isDictFile`, and `DictFileParser` reads every entry:
- ESI v2606 pitzDaily `system/controlDict`;
- foam-extend 4.1 and 5.0 pitzDaily `system/controlDict`.

URLs are in the plan's References section.

## Scope
**Bug part.** Header-less dictionaries, in `foamkit/types/_isDictFile.py` (and `foamkit/functions/isDictFile.py` if it duplicates the logic). A file is a header-less dictionary when all of the following hold:
- its first non-blank line is `FoamFile`;
- `{` follows on the same line or the next non-blank line;
- that block contains a `class` or `format` entry.

**Characterization part.** Real-header fixtures under `tests/fixtures/headers/`:
- `esi-v2606.controlDict`, `foam-extend-4.1.controlDict`, `foam-extend-5.0.controlDict`, copied byte-for-byte from the real files (trim the body after the header if you want, but leave the header unchanged);
- the existing Foundation open header from `tests/fixtures/pitzDaily`.

Tests in `tests/test_isdictfile.py`, plus one `pf.init` case test with a header-less `system/fvSchemes`.

## Out of scope
- Header preservation on write (T-006) and other writer formatting (T-019, T-020)
- Release detection (T-008)
- Warnings for skipped files. Skipped files stay silent (maintainer decision).

## Acceptance criteria
- [ ] Characterization tests (passing before and after): the ESI v2606, foam-extend 4.1, foam-extend 5.0 and Foundation open headers are recognised, and every entry is read.
- [ ] **Replace** any test fixture holding a from-memory foam-extend banner (for example one with a plain-dash first line) with the real header text. Record the source URL in a comment.
- [ ] A new failing test shows that a header-less `FoamFile { class dictionary; ... }` file is rejected and missing from `pf.init(...)`. After the fix it is recognised and loaded.
- [ ] These existing rejections stay unchanged:
  - `no_banner`, a repeated empty `FoamFile\n{\n}\n` with no `class`/`format`;
  - `indented_banner`;
  - the BOM case;
  - binary files;
  - files over `dict_filesize_limit`.

  All existing parametrized cases in `tests/test_isdictfile.py` pass unmodified.
- [ ] A text file whose first non-blank line is `FoamFile` but which has no `class`/`format` in the block is rejected.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- Loosening detection may pull in non-dictionary files. The `class`/`format` requirement and the negative tests guard against that.
- **Fixture text must come from real files**, fetched with `curl -sfL` so the bytes are exact, never retyped.
