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
