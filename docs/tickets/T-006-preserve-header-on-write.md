# T-006: Preserve the original file header verbatim on write; fix the header truncation off-by-one

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Plan:** docs/plans/openfoam-compatibility.md, bugs B3 and B4
- **Depends on:** T-005

## Goal
Writing a case that was read from disk leaves each file's banner and comment header exactly as it was, for any distribution.

## Scope
- The header class in `foamkit/types/__init__.py:355-385` (column slicing `[29:]`, and `'line'+str(i)` at `:383`)
- How the dict-file writer uses the header
- Golden tests

## Out of scope
- The default header for newly created files (T-009)

## Acceptance criteria
- [ ] New failing tests: a boxed-banner file is mangled after read → `toString()` (B3), and an over-long header line is not truncated into the right attribute (B4).
- [ ] After the fix, open, boxed and bannerless headers round-trip byte-identically (LF).
- [ ] Existing golden files are unchanged. If one must change, the diff is reviewed and explained in the PR.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- If an attribute of the header class (`line1`..`line5`) is part of user code, changing how it is stored is an API change. Keep the attributes, and add the verbatim header alongside them.
