# T-076: `ofBoundBox.value` raises `FoamKitError` when the groups are no longer two groups of three numbers

- **Issue:** [#103](https://github.com/mcgoldba/foamkit/issues/103)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (one getter check and one write check)
- **Related:** T-071 (#92, PR #101, deprecated float view of `ofBoundBox.value`).
- **Depends on:** none. Start after T-020 merges, because both change `foamkit/types/__init__.py`.

## Goal
After an edit through `.groups` leaves a box with anything other than 2 groups of 3 numbers, the deprecated `ofBoundBox.value` raises `FoamKitError` naming the entry and the shape it found, instead of returning a list of the wrong shape.

## Today (planner, reproduced on f8590d8, 2026-11-08)
`box (0 0 0) (1 1 1);` loaded, then edited. The object stays an `ofBoundBox` after every edit.

| Edit | `box.value` | Written as | Re-read as |
|---|---|---|---|
| `box.groups[1] = fkt.ofList(value=[1, 2])` | `[[0.0,0.0,0.0],[1.0,2.0]]`, **no error** | `(0 0 0) (1 2)` | `ofListGroups` |
| `box.groups.append(fkt.ofList(value=[4, 5, 6]))` | 3 float lists, **no error** | `(0 0 0) (1 1 1) (4 5 6)` | `ofListGroups` |
| `box.groups[0].value.append(fkt.ofInt(value=7))` | `[[0.0,0.0,0.0,7.0],[1.0,1.0,1.0]]`, **no error** | `(0 0 0 7) (1 1 1)` | `ofListGroups` |
| `box.groups.pop()` | `[[0.0,0.0,0.0]]`, **no error** | `box (0 0 0);` | `ofSplitList` |
| `box.groups.clear()` | `[]`, **no error** | **`box ;`** (the same for a plain `ofListGroups`) | **bare `AttributeError: 'ofWord' object has no attribute '_name'`** |
| `box.groups[0] = fkt.ofList(value=['a','b','c'])` | `FoamKitError` ("not 2 groups of 3 real numbers"; it does not say what was found) | `(a b c) (1 1 1)` | `ofListGroups` |

## Scope
- `foamkit/types/__init__.py`: the `ofBoundBox.value` getter checks the shape (2 groups, 3 items each) as well as the item types. It raises through `userMsg(..., 'ERROR')`, with a message naming the entry and the shape found (e.g. "2 groups of 3 and 2 items").
- `ofListGroups.toString`: an entry with no groups raises `FoamKitError` naming the entry, instead of writing `key ;`.
- Tests: additions to `tests/test_bound_box.py`.

## Out of scope
- Changing the class of the object after an edit, or validating `.groups` edits as they happen. Writing keeps what the user set, so no data is lost.
- Reading `box ;` from a file (a bare `AttributeError` on load today; not ticketed yet).
- Removing the deprecated view.

## Acceptance criteria
- [ ] **Failing tests first**: each edit in the table, on a box at top level and inside a sub-dict.
- [ ] For every shape other than 2×3 numbers, `box.value` raises `FoamKitError` (no bare exception, no traceback) whose message names `box` and the group sizes found. The `DeprecationWarning` is still emitted once.
- [ ] Written output is unchanged from the table, except for the no-groups row. Each re-read type is pinned (`ofListGroups`, `ofSplitList`). Write 1 == write 2 for each.
- [ ] No groups (`ofBoundBox` and plain `ofListGroups`): `toString()`/write raises `FoamKitError` naming the entry, and no file is written.
- [ ] A valid 2×3 edit through `.groups` still returns floats with no error.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): ofBoundBox.value raises when the groups are not two of three (T-076)`.

## Risks
- **Behaviour change:** code that read a wrong-shape `.value` without error now gets `FoamKitError`. This affects only a deprecated API, after an edit that already made the entry stop being a box.
- **OpenFOAM versions:** none.
