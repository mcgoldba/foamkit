# T-006: Preserve the file header byte-for-byte on write (Foundation, ESI, foam-extend)

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Plan:** docs/plans/openfoam-compatibility.md, bugs B3 (confirmed on a real file, 2026-10-19) and B4
- **Depends on:** T-005 (it reuses the `tests/fixtures/headers/` real-file fixtures)

## Goal
Writing a case read from disk leaves each file's banner and leading comment block exactly as it was. That covers the Foundation open banner, the ESI boxed banner and the foam-extend boxed banner.

## Evidence
Writing the real ESI v2606 pitzDaily `controlDict` strips the `|` borders from the boxed banner (B3). The header class in `foamkit/types/__init__.py:355-385` rebuilds the lines by column slicing (`[29:]`). Separately, header truncation sets `'line'+str(i)` with `i` starting at 0 (`:383`), an off-by-one (B4).

## Scope
- The header class (`foamkit/types/__init__.py:355-385`) and how the dict-file writer uses it. Keep the original header text verbatim, and keep the existing `line1`..`line5` attributes for compatibility.
- Tests over `tests/fixtures/headers/{esi-v2606,foam-extend-4.1,foam-extend-5.0}.controlDict` and the Foundation pitzDaily fixture.

## Out of scope
- The `FoamFile` block and body formatting (trailing spaces, padding, blank lines): T-019 and T-020
- The default header for newly created files: T-009

## Acceptance criteria
- [ ] New failing test: for the real ESI v2606 file, the written header (every line up to and including the closing `\*---...---*/`) differs from the source because the `|` borders are lost.
- [ ] After the fix, the header bytes from the start of the file up to and including the closing banner line are identical between source and written output for all four header fixtures (Foundation open, ESI v2606, foam-extend 4.1, foam-extend 5.0).
- [ ] The B4 off-by-one has a regression test (an over-long line truncates the intended attribute), or B4 is removed if verbatim preservation makes that code path unreachable for read files. Say which one.
- [ ] Existing golden files are unchanged. The Foundation open header already round-trips; if one changes, the diff is explained in the PR.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- `line1`..`line5` may be used by callers, so keep them populated. Verbatim text is the source of truth for writing.
- Fixture bytes must come from the real files (see the plan's References), not from memory.
