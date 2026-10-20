# T-006: Preserve the file header byte-for-byte on write (Foundation, ESI, foam-extend)

- **Issue:** [#13](https://github.com/mcgoldba/foamkit/issues/13)
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
- The one-line `FoamFile { ... }` form: T-021
- The default header for newly created files: T-009

## Acceptance criteria
- [ ] New failing test: for the real ESI v2606 file, the written header (every line up to and including the closing `\*---...---*/`) differs from the source because the `|` borders are lost.
- [ ] After the fix, the header bytes from the start of the file up to and including the closing banner line are identical between source and written output for all four header fixtures (Foundation open, ESI v2606, foam-extend 4.1, foam-extend 5.0).
- [ ] The B4 off-by-one has a regression test (an over-long line truncates the intended attribute), or B4 is removed if verbatim preservation makes that code path unreachable for read files. Say which one.
- [ ] The three goldens `tests/golden/dicts/headers/{esi-v2606,foam-extend-4.1,foam-extend-5.0}.controlDict.txt` (added by T-005) currently record the stripped `|` borders, which is bug B3. They **are expected to change** in this ticket. Regenerate them deliberately (`FOAMKIT_UPDATE_GOLDEN=1`), and include the diff in the PR. The reviewer checks that the header lines now equal the fixture source and that no non-header line changed.
- [ ] **Same-line `FoamFile {`:** when the block opens on the same line as the keyword, `_foamFile` stays `None` and `FoamFile` is stored as an ordinary entry, so the first two writes differ by one blank line before settling (review finding on T-005). After the fix:
  - the same-line form is parsed into `_foamFile`, like the next-line form;
  - a regression test asserts that write 1 == write 2;
  - a test asserts that `_foamFile` is set.
- [ ] All other golden files are unchanged. The Foundation open header already round-trips; if any other golden changes, the diff is explained in the PR.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- `line1`..`line5` may be used by callers, so keep them populated. Verbatim text is the source of truth for writing.
- Fixture bytes must come from the real files (see the plan's References), not from memory.

## Completion notes (implementer)
- `ofHeader` now keeps the source header text (`_text`, lines up to and including the `*/` line) and `toString()` returns it verbatim. `line1`..`line5` are still populated (column-sliced, as before) but are no longer used for writing. Default header (`ofHeader()` with no argument, T-009) is unchanged.
- B4: removed. The truncation only affected written output, which is now verbatim, so it was unreachable for read files; it also set a stray `line0`.
- Same-line `FoamFile {`: `readDictFile` now accepts it (`re.fullmatch(r'FoamFile\s*\{', ...)`) and parses it into `_foamFile`; write 1 == write 2 == next-line form.
- Regenerated only the 3 `tests/golden/dicts/headers/*.txt`; diff is the 5 banner lines each (`|` borders restored). Removed the T-006 strict xfail marker in `tests/test_banner_variants.py`.
- Review round 1: the 3 `.format` failures were a test bug; the coordinator fixed the assertions to compare `.value`.
- Results after round 2: pytest 532 passed, 1 skipped, 9 xfailed (conda env and py39); ruff 195, format 55, mypy 127 (all at baseline).

### Round 2 (review: REQUEST CHANGES)
- `FoamFile{` (no whitespace): `_hasHeaderlessFoamFile` now requires whitespace (or end of text) right after `FoamFile`, and the same-line regex in `readDictFile` is `r'FoamFile\s+\{'`. Such a file is no longer accepted header-less; banner + `FoamFile{` still raises FoamKitError as on HEAD.
- Short header: `ofHeader.__init__` pads the line list to 6 entries for `lineN` only; the stored `_text` is the real lines, so `note */` is written back verbatim.
- `ofHeader.__init__` docstring documents `_text` vs `lineN` and the pre-T-006 JSON cache (no `_text`, so `toString` falls back, via `getattr`, to the rebuilt header until `fk init`).
