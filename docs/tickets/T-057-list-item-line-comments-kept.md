# T-057: A `//` comment after an item of a multi-line list (`layerSets // write cellSets`) is kept on write

- **Issue:** [#76](https://github.com/mcgoldba/foamkit/issues/76)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-056 (#75, it adds the comment storage and the writer side for entries; this ticket reuses them for list items) and T-036 (#48, quote-aware `//`).
- **Related:** T-048 (#64, list item parser), T-052 (#69, entry values of several lists), T-036's "Re-check after T-042" rows (a `//` that hides a `)` on a one-line list).
- **Found by:** the planner while reproducing the T-046 review notes (PR #73, note 5). Pre-existing on main.

## Goal
A `//` comment after an item in a multi-line list is written back after that item, so an unedited read → write keeps it.

## Reproduction (planner, 2026-10-31, `t-052-entry-value-of-several-lists` at 0eb75b1 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| `x` / `(` / `    1 // c` / `    2` / `);` | **silently dropped:** loads `[1, 2]`, written without `// c`; write 1 == write 2 |
| Real file: F14 `mesh/snappyHexMesh/flange/system/snappyHexMeshDict:304-306` (`writeFlags ( scalarLevels // write volScalarField … layerSets // … layerFields // … );`) | loads; the 3 item comments are dropped on write |
| `x` / `(` / `    // c` / `    1` / `);` and `x` / `( // c` / … | OK: kept as an `ofComment` item (must not change) |
| `x ( 1 // c` / ` 2 );` (one-line start) | misleading "unbalanced brackets" `FoamKitError`; owned by T-036 |

The same `writeFlags` block with item comments is in the Foundation `motorBikeSteady` and `flange` `snappyHexMeshDict` files (F11-F14).

## Scope
- The multi-line list parser in `foamkit/types/__init__.py` (`_parseList` / `_parseListValues`): keep the text of a `//` comment after an item and attach it to that item, using T-056's mechanism; the list writer puts it back after the item on the same line.

## Out of scope
- One-line lists whose `//` hides the `)` (T-036)
- Comments after `);` (T-056); `/* */` inside lists (T-031)
- Item layout and spacing before `//` (T-020)

## Acceptance criteria
- [ ] **Failing tests first:** the first row at top level and in a sub-dict, for word, number and quoted-string items; a list of sub-lists with a comment after an inner `)`; the real F14 `flange` `snappyHexMeshDict` as a byte-exact fixture (source and commit recorded), unless T-056 already added it.
- [ ] The written text has each comment after its item, on the same line, with the text after `//` unchanged; the re-read gives the same items and comments; write 1 == write 2.
- [ ] Item values are unchanged: `.value` of the list has no comment text in it, and item types are as today.
- [ ] The "must not change" rows behave as before. No golden file changes. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **List equality:** items that carry a comment must still compare equal to plain values where user code relies on it (same decision as T-056).
- Same list code as T-048 and T-052: start after T-052 merges.

## Ranking rationale
Silent loss of annotations in stock `snappyHexMeshDict` files, but no value changes. It follows T-056, which builds the mechanism it reuses.
