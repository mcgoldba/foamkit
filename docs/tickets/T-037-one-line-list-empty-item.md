# T-037: A one-line list gains an empty item on re-read (`x ( 1 );`)

- **Issue:** [#49](https://github.com/mcgoldba/foamkit/issues/49)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-035. The T-035 tester marked 12 tests `xfail(strict=True)` with this ticket's id and added a characterization test.
- **Found by:** the T-035 implementer (2026-10-26). It is pre-existing on main.

## Goal
A one-line list such as `x ( 1 );` reads back as exactly the items it contains. Each write → read cycle stops adding an empty item.

## Bug
- `x ( 1 );` and `x ( ")" );` are written, and when that output is read back, the list has an **extra empty `ofStr` item**. The data silently changes, and keeps changing with further cycles.
- **Cause:** `_parseList` (`foamkit/types/__init__.py`, the `line.endswith(');')` check, about `:4594` on the T-035 branch) runs on a line that still has its trailing newline. The check fails, so the `;` is parsed as an item.
- One-line lists are very common in OpenFOAM files, for example `libs ("libfoo.so");`, `fields (p U);` and `patches (inlet outlet);`.

## Golden files encode the bug
The one-line fix (`rstrip()` before the check) changes **7 golden/case outputs**: today's goldens record the extra empty item. Regenerating them is part of this ticket and must be **deliberate and reviewed**.

## Scope
- Fix the end-of-line check in `_parseList`, and in any sibling check with the same pattern; the tester greps for `endswith(` on raw lines.
- Regenerate the affected goldens (`FOAMKIT_UPDATE_GOLDEN=1`).
- Remove the strict-xfail markers that reference T-037.

## Out of scope
- Other list re-flow and layout (T-020)

## Acceptance criteria
- [ ] The 12 strict-xfail tests marked with T-037 pass with their markers removed. The T-035 characterization test is updated to the correct output, with a comment referencing T-037.
- [ ] `x ( 1 );`, `x ( ")" );`, `x ( a b c );` and `x ();` each read back with exactly their items after 1, 2 and 3 write → read cycles.
- [ ] **Golden regeneration is reviewed.** The `git diff -- tests/golden` contains only removals of the spurious empty list items, in the 7 known outputs and no others. The reviewer checks this line by line, and the PR body lists the 7 files.
- [ ] All `tests/releases/` files behave as before, or better; any difference is listed in the PR.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Other code may expect the empty item,** for example code indexing list positions. The goldens and the full test suite guard against this.

## Ranking rationale
**Right after T-035, ahead of T-027.**
- It silently changes data in one of the most common constructs, with no error, and the change compounds on every cycle.
- T-027 is a loud load failure that users notice. This bug corrupts files they think FoamKit handled correctly.
- The fix is small, and the tests are already written (strict-xfail).

## Completion notes (implementer, 2026-10-26)
- **Fix** (`_parseList`): the closer check now looks at the text before the first `;`, right-stripped. If it ends with `)`, that `)` is removed. This works with the line ending still attached (LF or CRLF) and with a trailing `// c` or `/* c */` after `);`. It also fixes multi-line lists, whose closing `);` line carried the same newline and so gained `''` on the first read.
- **Trailing `/* c */` after `);`:** the text after the `;` is re-parsed as an extra line. `_parseLine` did not recognise a one-line block comment there and raised `IndexError`. It now returns an `ofComment`, so the comment is kept as its own entry after the list. A trailing `// c` is still dropped, as before.
- **Siblings:** no other `endswith(` on a raw line has the problem. The remaining ones are on stripped text or filenames.
- **Tests:** the 13 `T-037` strict-xfail markers were removed, and nothing else (plus the `wrong_today` variable that became dead). `ruff format` touched those two test files.
- **Goldens:** regenerated with `FOAMKIT_UPDATE_GOLDEN=1`. 6 files changed, 14 lines removed, 0 added; every removed line is a whitespace-only list item before `)` or `);`:
  - `case/controlDict.written.txt` 2
  - `dicts/headers/foam-extend-4.1.controlDict.txt` 1
  - `dicts/headers/foam-extend-5.0.controlDict.txt` 1
  - `dicts/pitzDaily/system/blockMeshDict.txt` 6
  - `dicts/pitzDaily/system/controlDict.txt` 2
  - `dicts/pitzDaily/system/setFieldsDict.txt` 2

  The ticket said 7. The tester's list of 5 dict goldens plus the case-level golden gives 6, and that is all that changed.

### Review round 1 (implementer, 2026-10-27)
- **Trailing text queued once.** The text after the `;` of a list entry was queued twice (by `_parseLineLenGreaterThanTwo` and by `_parseList`), so a trailing `/* c */` came out twice. A new `_queueTrailing` queues it once per line. It joins the pieces with `';'`, so `;` characters in the remainder are kept.
- **End of file.** Extra lines still queued when the loop ends are now handled: a one-line block comment is kept as a comment entry, the rest is dropped.
- **No silent loss.** Only a comment or closing brackets may follow `);` on the same line. Anything else (`x ( 1 ); y 2;`, `x ( 1 ); y ( 2 );`) raises `FoamKitError` naming the file and the line. Those lines were dropped silently on the earlier T-037 commit, and raised `IndexError` for the second form on main.
- **`a 1; /* c */`:** the comment is now kept as a separate entry. Main dropped it.

### Review round 2 (implementer, 2026-10-27)
- **Maintainer decision, option (b):** keep raising `FoamKitError` for a second entry on the same line after ANY entry, not only after a list, until T-041 (#55) parses it properly. The error now reads "Line N of file F has more than one entry ('<remainder>'); only one entry per line is supported (T-041)." `N` is the 1-based physical line. Behaviour is otherwise unchanged.
- **User-visible effect:** real tutorials that loaded on main with silent data loss now raise.
  - Foundation 11-14 `fluid/helmholtzResonance/system/blockMeshDict`, lines 144-145.
  - Per the planner's rescan of the Foundation 11-14 tutorials (code blocks, comments and strings excluded): 3 files per release, 12 file-instances and 48 lines, where a second entry follows a top-level `;` (`helmholtzResonance`, `rotatingCube` and `refineMesh/sector` `blockMeshDict` in 12-14; `helmholtzResonance`, `damBreak` `fvSchemes` and `refineMesh/refineFieldDirs` `blockMeshDict` in 11). The reviewer's looser grep counted 95 lines in 31 files. Several entries inside a one-line `{ … }` are T-040's case.
  - A banner file with a one-line `FoamFile { … }` block: `pf.init` now fails for that case.
- **T-041** will make these load.
