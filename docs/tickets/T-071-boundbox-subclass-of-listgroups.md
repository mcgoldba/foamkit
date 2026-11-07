# T-071: `box (…) (…)` entries keep their number text and get one type, whatever the number spelling (`ofBoundBox` becomes a subclass of `ofListGroups`)

- **Issue:** [#92](https://github.com/mcgoldba/foamkit/issues/92)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M (one parser removed and one class re-based, but it also adds a deprecation path for `ofBoundBox.value` and keeps the number text of list groups (`8e-3`, `1e6`), which `ofListGroups` loses today; that is more than an S, and still one parser and one class pair)
- **Approved in principle:** maintainer, 2026-11-07 (PR #78 discussion; design below)
- **Related:** T-052 (#69, `ofListGroups`), T-019 (#26) and T-020 (#27, whitespace and layout of unedited entries), T-032 (number formatting elsewhere), T-014 (type chosen by shape).
- **Depends on:** T-019 (lands first in the ranked order). Start after T-055 merges, because both change `foamkit/types/__init__.py`.

## Goal
A two-vector entry such as `box (0 0 -1) (1 8e-3 1);` loads as the same type however its numbers are spelled, and is written back with its original number text. Write 1 equals write 2. Existing `ofBoundBox` users keep working for one release, with a `DeprecationWarning`.

## Today (planner, checked on main 647cb84 and the T-055 branch)
| Input | Loads as | Written as |
|---|---|---|
| `box (0 0 0) (1 2 3);` | `ofBoundBox`, `.value == [[0.0,0.0,0.0],[1.0,2.0,3.0]]` | `box (0.0 0.0 0.0) (1.0 2.0 3.0);` (text changes on every stock box) |
| `p1 (0 0 0) (1 1 1);` | `ofBoundBox` (any key with this shape) | `p1 (0.0 0.0 0.0) (1.0 1.0 1.0);` |
| `box (0 0 -1) (1 8e-3 1);` (Foundation 11 `incompressibleVoF/capillaryRise/system/setFieldsDict:26`) | `ofListGroups` (the `_parseBoundBoxValue` regex `(?<=\()[\s\d.-]+(?=\))` rejects exponents) | `(1 0.008 1)`. Write 2 reads this back as `ofBoundBox` and writes `0.0`/`1.0`, so **write 1 != write 2, and the type changes between reads** |
| `box (-1e6 -1e6 -1e6)(1e6 -0.15 0.3);` (Foundation 11 `incompressibleFluid/pipeCyclic/system/topoSetDict:24`) | `ofListGroups` | `1e6` becomes `1000000.0`; same type flip on write 2 |
| two 3-vectors across lines | `ofListGroups` (`_parseListGroups` defers to `_parseBoundBoxValue` only for one-line entries, ~7220) | type differs from the one-line form |
| `box.value = [[1, 2], [3, 4]]` or `box.value = [[0,0,0],[1,"a",1]]` | `ofBoundBox.value` setter calls `userMsg(...)` at the default `INFO` level, then **stores the bad value anyway**. The inner length is never checked, so `[[1, 2], [3, 4]]` is accepted with no message at all | written as given |

Users: `tests/test_regressions.py::test_bound_box_still_detected` and `tests/test_several_lists_value.py::test_box_of_two_vectors_stays_a_bound_box` (T-052 guard, all containers) assert `isinstance(…, ofBoundBox)` and the float `.value`. Nothing in `foamkit/functions` uses `ofBoundBox`. `ofListGroups` is not released yet (not in CHANGELOG v0.1.0), so its internals can change without a deprecation path.

## Design (agreed)
1. `_parseListGroups` is the only parser for `key (g1) (g2) …;`. `_parseBoundBoxValue` and its call in the single-line entry path (~6160) are deleted, so number rules (signs, exponents, and `inf`/`nan` if the shared list-value rule accepts them) live in one place.
2. `ofBoundBox` becomes a subclass of `ofListGroups`. `_parseListGroups` returns an `ofBoundBox` when the value is exactly two groups of exactly three items, every one a number by that shared rule, on one line or across lines, at any depth. Any other shape returns an `ofListGroups`. As today, the type is chosen by shape, not by key (`p1` stays a box; typing by meaning is out of scope).
3. **Number text is kept:** each group keeps the source text of its items. An unedited group is written with that text (`8e-3`, `1e6`, `0`, `-0.15`). An edited group is written from its new values. This applies to every `ofListGroups`, so `transform (…) (…)` gains it too. Whitespace between the key, the groups and the `;` follows the writer's standard layout (T-019/T-020). Glued `)(` may be written as `) (`; that is layout, and the tokens are the same.
4. **Deprecated float view:** for one release, `ofBoundBox.value` keeps its contract.
   - Reading it returns a new `[[float]*3, [float]*3]` built from the groups.
   - Assigning it requires an iterable of 2 iterables of 3 real numbers (`bool` and strings are rejected) and replaces both groups.
   - Both reading and assigning emit `DeprecationWarning`: "`ofBoundBox.value` returns floats for one more release; use `.groups` (a list of `ofList`, as for `ofListGroups`)".
   - New, not deprecated: `ofListGroups.groups`, a read-only property returning the stored list of `ofList` (for `ofListGroups` it is the same list as `.value`).
   - Internal code (parser, `toString`, `__str__`, `attrDict`/`toDict`, repr, equality) uses the stored groups, never `.value`, so loading, writing and `case.save()` emit no warning.
5. **Errors never pass silently:** a bad assignment raises `FoamKitError` naming the entry and the expected shape, and stores nothing (the old value stays). It goes through `userMsg(..., 'ERROR')` so there is no traceback for the user. It never prints and stores.

## Scope
- `foamkit/types/__init__.py`: `ofBoundBox`, `ofListGroups` (`groups`, source text per group, `toString`), `_parseListGroups`, the deleted `_parseBoundBoxValue` and its call site.
- Tests: a new `tests/test_bound_box.py`. Small edits to the two existing `ofBoundBox` tests, to add `pytest.warns(DeprecationWarning)` around `.value`; their expected values stay the same. New fixtures in `tests/releases/` with their source recorded.
- Goldens: only the two box lines listed in the acceptance criteria.

## Out of scope
- Removing `ofBoundBox` or the float view (a later maintainer decision after one release).
- Choosing types by key or meaning (`boundBox` only for `box`). Number spelling outside list groups (T-032). Layout or padding of unedited entries (T-019, T-020). Multi-line boxes are written on one line, as `ofListGroups` does today.
- Counted groups (`2(1 2) 2(3 4)`) and comments inside the value: they keep their T-052 `FoamKitError`.

## Acceptance criteria
- [ ] **Failing tests first**, each at top level and inside a sub-dict (the T-052 `CONTAINERS`):
  - `box (0 0 0) (1 2 3);`, `box (0 0 -1) (1 8e-3 1);`, `box (-1e6 -40 -1e6) (1300 40 1e6);`, `box (-1e6 -1e6 -1e6)(1e6 -0.15 0.3);`, `p1 (0 0 0) (1 1 1);`, `box (-1.5E+2 0 0) (1 1 1);`;
  - the same box across lines (`box` / `(0 0 0)` / `(1 2 3);`, and `box (0 0 0)` / `(1 2 3);`);
  - non-boxes: `c (1 2) (3 4);`, `c (1 2 3) (4 5 6) (7 8 9);`, `c (a b c) (1 2 3);`, `c (1 2 3) (4 5 6 7);`, `transform (1 0 0 0 1 0 0 0 1) (0.5 0.45 0.1);`;
  - `box (-inf 0 0) (inf 1 1);`: whatever type the shared rule gives, the test records it, and the text round-trips.
- [ ] Every two-groups-of-three-numbers input above is an `ofBoundBox` on first read and on re-read, and `isinstance(x, fkt.ofListGroups)` holds. The non-box inputs are plain `ofListGroups`. The type never depends on number spelling or line breaks.
- [ ] Unedited: the written entry has the same tokens and the same number text as the source (`8e-3`, `1e6`, `0`; no `0.0`, `0.008`, `1000000.0`). Write 1 == write 2.
- [ ] Edit, then write: `box.value = [[0, 0, 0], [2, 2, 2]]` and reading `box.value` each emit one `DeprecationWarning`. The float view returns `[[0.0,0.0,0.0],[2.0,2.0,2.0]]`. The written line has the new numbers, re-reads as an `ofBoundBox` and is stable on write 2. Editing `box.groups[1]` also works, with no warning.
- [ ] Bad assignments raise `FoamKitError` and leave the old value: `[[1, 2], [3, 4]]`, `[[0,0,0]]`, `[[0,0,0],[1,"a",1]]`, `[[0,0,0],[1,True,1]]`, `"0 0 0 1 1 1"`, `5`. No bare `TypeError`/`ValueError`.
- [ ] Load, `toString`, `case.save()`/`toJSON` and write of a file with boxes emit no `DeprecationWarning` (checked with `warnings.simplefilter("error", DeprecationWarning)`).
- [ ] `_parseBoundBoxValue` no longer exists (a test asserts `not hasattr(...)` on the parser class, or a grep in the PR body shows it). No other parser builds `ofBoundBox`.
- [ ] Real fixtures copied byte-exact into `tests/releases/`, with their source recorded: Foundation 11 `incompressibleVoF/capillaryRise/system/setFieldsDict` and Foundation 11 `incompressibleFluid/pipeCyclic/system/topoSetDict`. Both load, write 1 == write 2, and their `box` lines keep `8e-3` and `1e6`. If `pipeCyclic` fails earlier on another open ticket, use another real `topoSetDict` with `1e6` and record which.
- [ ] `test_bound_box_still_detected` and `test_box_of_two_vectors_stays_a_bound_box` pass with the same expected values, plus a `pytest.warns(DeprecationWarning)` around `.value`. All other T-052 tests pass unchanged.
- [ ] Goldens: only these lines change, and only toward the source text: `tests/golden/dicts/pitzDaily/system/setFieldsDict.txt:29` (`(0.0 0.0 -1.0) (0.1461 0.292 1.0)` → `(0 0 -1) (0.1461 0.292 1)`, as in `tests/fixtures/pitzDaily/system/setFieldsDict:26`) and `tests/golden/dicts/dicts/tableDict.txt:30` (`(0.0 0.0 0.0) (1.0 2.0 3.0)` → `(0 0 0) (1 2 3)`, as in `tests/fixtures/dicts/tableDict:31`). The padding before `(` may change by one space (`ofBoundBox.toString` adds one after `printNameStr`, `ofListGroups` does not). Any other golden change is a failure. A grep of `tests/golden` for `(0.0` found only these two box lines plus three `uniform (…)` lines, which must not change.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): keep the number text of box entries and read them as one type (T-071)`. The commit body says: box entries keep their number text; `ofBoundBox` is now an `ofListGroups`; `.value` floats are deprecated in favour of `.groups`; bad assignments now raise.

## Risks
- **Public API:** `ofBoundBox.value` returns floats only through the deprecated view. Code that mutates it in place (`box.value[0][0] = 5`) silently does nothing, because the view is a new list each time. Document this in the warning text and the commit body. Do not return a live float list, because that would bring back two sources of truth.
- **Behaviour change:** written boxes change from `0.0` back to the source text. Users who diff output see this once. `repr`, `==` and `attrDict` of an `ofBoundBox` change to the `ofListGroups` form (groups, not floats). Equality against a plain float list no longer holds.
- **`.params` cache:** `case.save()`/`write()` store a box in `.params/_case.json` in the `ofListGroups` form instead of 2×3 floats. Check at implementation time that nothing reads the cache back into types (the `fromDict` path looks commented out); if something does, it must load both forms.
- **Source text in `ofListGroups`:** the edit check must not write stale text after an edit through `.groups` or `.value`. Tests cover editing one group and then the other.
- **OpenFOAM versions:** none. Both spellings are valid in every tested Foundation and ESI release; OpenFOAM decides `boundBox` from the reading code, not the text.
