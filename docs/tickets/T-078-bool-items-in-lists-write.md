# T-078: lists and list groups with `on`/`off`/`true`/… items are written back instead of crashing with a bare `TypeError`

- **Issue:** [#105](https://github.com/mcgoldba/foamkit/issues/105)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (one writer branch, plus an explicit error for item types that cannot be written)
- **Related:** T-071 (#92, PR #101), T-045 (one-element lists), T-048 (list items).
- **Depends on:** none. Start after T-020 merges, because both change `foamkit/types/__init__.py`.

## Goal
A list or list group that contains a boolean word (`l (on off);`, `box (on 0 0) (1 1 1);`) is written back with the same words. An item that FoamKit cannot write raises `FoamKitError` naming the entry, never a bare `TypeError`.

## Today (planner, reproduced on f8590d8, 2026-11-08; the same on main before T-071, per the T-071 review)
Reading works: each word in `OF_BOOL_VALUES` becomes an `ofBool` item. Writing then fails, because `ofList.toString` (~1543), `ofSplitList.toString` (~1600) and `ofListGroups._groupString` (~1823) call `item.toString(ofRep=False, indent=False)`, and `ofBool.toString(self, ofRep=False)` (~1412) takes no `indent`.

| Input (top level and in a sub-dict) | Loads as | Write |
|---|---|---|
| `l (on off);`, `l (no yes);`, `l (on 1 a);`, `l ( on );`, multi-line `l` / `(` / `on` / `off` / `);` | `ofSplitList` with `ofBool` items | **bare `TypeError: ofBool.toString() got an unexpected keyword argument 'indent'`** |
| `l ((on off) (1 2));`, `l (a (on off));` | `ofSplitList`, inner `ofList` with `ofBool` items | **bare `TypeError`** |
| `box (on 0 0) (1 1 1);`, `c (on 1) (2 3);`, `c (on off) (true false);`, `c (yes 1 2) (3 4 5);` | `ofListGroups` | **bare `TypeError`** |
| `l (true);` | `ofList` holding a plain `str` | write 1 is `( true)`; **re-reading it gives the bare `TypeError`** on write 2 |
| `x on;`, `l ({a on;} {b off;});` | `ofBool` / dicts | written correctly |
| user appends `fkt.ofBool(value='on')`, `fkt.ofBool(value=True)` or `fkt.ofVector(value=[1,2,3])` to a list or a group | | **bare `TypeError`** (`ofVector.toString` has no `indent` either). `ofVar` and `ofWord` items are written correctly |

No file in `tests/releases/` or `tests/fixtures/` has a boolean word inside a list.

## Scope
- `foamkit/types/__init__.py`: `ofList.toString`, `ofSplitList.toString` and `ofListGroups._groupString` write an `ofBool` item as its source word (`_valueStr`: `on`, `off`, `yes`, `true`…; `true`/`false` for `ofBool(value=True/False)`). An item whose `toString` cannot be called this way raises `FoamKitError` naming the entry and the item type, through `userMsg(..., 'ERROR')`. Choosing whether to accept `indent` in `ofBool.toString` is up to the implementer.
- Tests: a new `tests/test_bool_list_items.py`.

## Out of scope
- Writing `ofVector` and other typed items inside lists correctly: they get the `FoamKitError` above, and a later ticket can write them. The one-element `l (true);` type change on re-read (T-045). New boolean spellings beyond `OF_BOOL_VALUES`.

## Acceptance criteria
- [ ] **Failing tests first**: every input row in the table, at top level and inside a sub-dict.
- [ ] Each parsed input is written with the same words and numbers as the source (`on` stays `on`, `yes` stays `yes`). Write 1 == write 2. The re-read types are pinned: `box (on 0 0) (1 1 1);` stays an `ofListGroups`, not an `ofBoundBox`.
- [ ] An `ofBool(value=True)` appended by the user is written `true`. `ofBool(value='on')` is written `on`.
- [ ] An `ofVector` appended to a list or a group raises `FoamKitError` naming the entry (or is written correctly, if that turns out to be just as small). No input above raises a bare `TypeError`.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): write on/off items in lists instead of crashing (T-078)`.

## Risks
- **Behaviour change:** files that crashed on write now write. A user-built list containing an `ofVector` changes from a bare `TypeError` to `FoamKitError`.
- **OpenFOAM versions:** none. Foundation and ESI both accept these words as switch values.
