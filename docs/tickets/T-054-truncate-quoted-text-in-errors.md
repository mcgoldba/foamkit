# T-054: Error messages quote at most a short excerpt of the offending text

- **Issue:** [#71](https://github.com/mcgoldba/foamkit/issues/71)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-042 (#57, added the tab guard), T-034 (#42, escaping in `userMsg`), T-025 (literal `userMsg` text).
- **Found by:** the T-042 reviewer (PR #66, round 4 note 1). Introduced by T-042; no data is affected.

## Goal
A `FoamKitError` that quotes text from a case file shows a short excerpt (for example the first 80 characters and `…`), so a long line does not produce a message of tens of thousands of characters.

## Reproduction (planner, 2026-10-30, `t-048-glued-parentheses-in-list-items` at 693d945 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| `x` / `(` / 20,000 `1` items separated by tabs, then `<TAB>#includeFunc mag(U)` / `);` | `FoamKitError` of **40,256 characters**: "Line 10 of file … has an include directive after another list item separated by a tab ('1\t1\t…\t#includeFunc'); separate them with a space." |
| `x` / `(` / `<TAB>1<TAB>#includeFunc mag(U)` / `);` | 258 characters; fine |

The message comes from the tab guard in `_parseListValues` (`foamkit/types/__init__.py`, "separated by a tab"), which quotes the whole list word.

## Scope
- The tab-guard message in `_parseListValues`: quote a bounded excerpt, keeping the end next to `#includeFunc` visible (that is the part the user must fix).
- A small helper for the excerpt, used by this message and by any other `FoamKitError` message in `foamkit/types/__init__.py` that quotes raw file text of unbounded length (the tester lists them; for example "has text after the end of an entry ('…')").

## Out of scope
- Escaping control characters (T-034)
- Changing which inputs raise

## Acceptance criteria
- [ ] **Failing test first:** the 20,000-item row raises `FoamKitError` whose message is at most a few hundred characters, still names file and line, and still shows `#includeFunc`.
- [ ] Short quoted text (the second row) is shown in full, unchanged.
- [ ] Truncation is marked (`…`), so the user knows text was cut; the error itself is still raised (errors never pass silently).
- [ ] No golden file changes. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- Tests that match full message text may need the excerpt; match on file, line and the stable part of the message.

## Ranking rationale
Cosmetic: the error is already raised with file and line, and the input has 0 tutorial occurrences. Next to T-034, which also hardens error message text.
