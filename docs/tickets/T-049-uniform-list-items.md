# T-049: Uniform lists as list items (`x ( 2{0} 3{1} );`) load instead of raising "not supported yet"

- **Issue:** [#65](https://github.com/mcgoldba/foamkit/issues/65)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-040 (#54, merged; added today's `FoamKitError`, before which these lists loaded **empty**), T-048 (glued `N(…)` items, same item tokenizer), T-020 (layout).
- **Found by:** the T-040 reviewer (PR #60, round 3, "Checks the coordinator asked for"). Pre-existing on main as a silent empty list; loud since T-040.

## Goal
A list whose items are uniform lists, `N{value}`, as in OpenFOAM's `List<List<T>>`, loads and is written back unchanged. Shapes that are not valid OpenFOAM keep raising `FoamKitError` with file and line.

## Reproduction (planner, 2026-10-30, `t-042-include-inside-a-list` at a9a9447 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| `x ( 2{0} 3{1} );`, multi-line `x` / `(` / `2{0}` / `3{1}` / `);` | `FoamKitError: Line N of file … has a uniform list ('N{...}') or a numbered block inside a list: not supported yet.` |
| `x 2 ( 3{0} 2{1} );`, `x List<scalarList> 2 ( 3{0} 2{1} );` | same `FoamKitError` |
| `x ( 1 2{0} );`, `x ( a 3 { v 1; } );` | same `FoamKitError`. Not valid OpenFOAM for any one list type; **keep the error** |
| `x 3{(1 0 0)};`, `x List<word> 2{wall};`, `searchBoxDivisions 3{(64 64 1)};` (value position) | load and round-trip (T-040) |
| `x ( 0 { v 1; } 1 { v 2; } );` (numbered dicts) | load and round-trip (T-040) |

On main before T-040, each input that now raises this error either loaded as an empty list, written `x ( );`, or failed (T-040 reviewer, round 3).

## OpenFOAM semantics
`List<T>` reading accepts `N{value}` for a uniform list, and a number ends at `{`. So in a `List<List<scalar>>` (e.g. a `labelListList`) each item may be `3{0}`. FoamKit cannot know the element type; it only has to keep the text.

## Real tutorial occurrences (planner scan, 2026-10-30; every `FoamFile` file under `tutorials/`, including `0/` fields, with comments, strings and `#{ #}` masked; ESI from git `HEAD`)
- `N{` whose innermost bracket is `(`: **0** in Foundation 11-14 and ESI v2412-v2606.
- `N{` anywhere outside code: 2 ESI files per release, both value position (`overPimpleDyMFoam/twoSimpleRotors/system/fvSchemes:59`, `overInterDyMFoam/twoSquaresOutDomain/system/fvSchemes:65`, `searchBoxDivisions 3{(64 64 1)};`). Both load today.
- So no stock file hits the error. It matters for user files and for files written by OpenFOAM utilities.

## Scope
- The list item tokenizer in `foamkit/types/__init__.py` (where T-040 raises the "uniform list … inside a list" error): an item `N{value}` (with or without a space before `{`) whose value has no `;` becomes one verbatim item, in one-line and multi-line lists.
- Keep the `FoamKitError` for a list that mixes plain items with `N{…}` items, and for a numbered block after a plain item (`x ( a 3 { v 1; } )`).

## Out of scope
- Interpreting the uniform value or expanding the list
- Glued `N(…)` items (T-048)
- Numbered dict items (already load)

## Acceptance criteria
- [ ] **Failing tests first:** the first two rows of the table, at top level and inside a sub-dict, one-line and multi-line, with nested values (`2{(1 0 0)}`).
- [ ] Each loads with one item per `N{…}`, keeps the item text exactly, and write 1 == write 2 == write 3 with the same tree on every re-read.
- [ ] `x ( 1 2{0} );` and `x ( a 3 { v 1; } );` still raise `FoamKitError` naming file and line; no input loads as an empty list.
- [ ] The existing T-040 tests for value-position uniform lists and numbered dict items pass unchanged.
- [ ] No golden file changes. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Mixed lists:** deciding which mixes are valid needs care; when unsure, keep the error. A loud error is the safe default.
- The same tokenizer is changed by T-042 and T-048; land after both.

## Ranking rationale
**Near the end of the backlog, after T-028.** The syntax is valid OpenFOAM, but no tutorial file uses it inside a list, and today it fails loudly with file and line, which is the correct interim behaviour.
