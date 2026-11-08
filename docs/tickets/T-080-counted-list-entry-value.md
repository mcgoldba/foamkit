# T-080: an entry whose value is a counted list (`inGroups 2(wall viewFactorWall);`) loads instead of failing

- **Issue:** [#107](https://github.com/mcgoldba/foamkit/issues/107)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (one branch in `_parseValue` and the entry parser, plus tests)
- **Related:** T-048 (counted lists as list items, `x ( 4(0 1 2 3) );`), T-052/T-071 (counted list groups `2(1 2) 2(3 4)` raise `FoamKitError`), T-068 (`nonuniform List<T> N(…)` field values), T-045 (one-element lists), T-078 (`on`/`off` items).
- **Depends on:** none. Start after T-020 merges, because both change `foamkit/types/__init__.py`.
- **Merged:** the planned separate ticket for `t 2(on off);` (counted list of words or booleans) is folded in here: it fails at the same line for the same reason as counted lists of numbers and of lists.

## Goal
An entry whose value is a count glued to a list, such as ESI's `inGroups 2(wall viewFactorWall);` or `faces 2((0 1 2) (3 4 5));`, loads and is written back as read; a count that cannot be handled raises `FoamKitError` naming the file and the line of the entry, never a bare `ValueError`.

## Cause
`_parseValue` (~6131) returns a one-element tuple for a value matching `[0-9]+\(.+`: `return ofSplitList,`. Its caller `_parseSingleLineEntry` (~5174) unpacks two values, so every glued counted value fails whatever it holds. Inside a sub-dict, the error is caught and re-raised as `FoamKitError`, but it names the line of the enclosing sub-dict, not the entry.

## Today (planner, reproduced on f8590d8, 2026-11-08)
| Input | Top level | In a sub-dict |
|---|---|---|
| `t 2((0 1) (1 2));`, `faces 2((0 1 2) (3 4 5));`, `t 2(0 1);`, `t 3(0 1 2);`, `t 1(a);`, `t 2(a b);`, `t 2(on off);`, `t 2(on 1);`, `t 0();`, `t 2((0 1) (1 2)); // c`, `t 2(0 1)` / `;` | **bare `ValueError: not enough values to unpack (expected 2, got 1)`** | `FoamKitError` "cannot read the entry 'sub'", naming the `sub` line |
| `t 2 ((0 1) (1 2));`, `t 2 (0 1);`, `t 2 (a b);` (space before `(`) | `ofStr`, written as read | same |
| `t List<vector> 2((0 0 0) (1 1 1));`, `internalField nonuniform List<vector> 2((0 0 0) (1 1 1));`, `… List<scalar> 2(0 1);` | `ofStr`, written as read | same |
| `jumpTable polynomial 1((100 0));`, `diffusivity inverseDistance 1(floatingObjectBottom);` (count after a word) | `ofStr`, written as read | same |
| `t` / `2` / `(` / `(0 1)` / `(1 2)` / `);` (count on its own line) | `ofSplitList`, **written without the `2`** | same |
| `t ( 2(0 1) 2(1 2) );` (counted items) | `ofSplitList`, written as `2` / `(0 1)` / … (T-048) | same |

Real tutorials (`git grep` over `tutorials/`, `polyMesh` excluded; ESI v2606 read with `grep -r`):
- Foundation 11 and 14: **0** entries with a glued counted value (the only `N(` hits are after a word, `polynomial 1((100 0))` and `inverseDistance 1(…)`, which load as `ofStr`).
- ESI v2606: **6 dictionary files, 30 lines**, all `inGroups N(…);` inside a sub-dict, all failing to load with the `FoamKitError` above: `heatTransfer/chtMultiRegionFoam/externalSolarLoad/system/air/changeDictionaryDict` (2), `heatTransfer/chtMultiRegionSimpleFoam/multiRegionHeaterRadiation/system/{bottomAir,topAir}/changeDictionaryDict` (3, 1), `incompressible/pimpleFoam/RAS/axialTurbine_rotating_oneBlade/system/changeDictionaryDict_cyclicAMI` (20), `incompressible/pimpleFoam/RAS/oscillatingInletPeriodicAMI2D/system/blockMeshDict` (2), `combustion/XiDyMFoam/annularCombustorTurbine/system/createPatchDict.ami` (2). One more top-level hit, `elements 5(O H C N Ar);` in `SandiaD_LTS/constant/reactionsGRI`, is in a file without a `FoamFile` header, which FoamKit refuses anyway.

## Scope
- `foamkit/types/__init__.py`: `_parseValue` and `_parseSingleLineEntry` handle a value of the form `N(…)` (with or without a trailing comment, `;` on the same or the next line). The simplest lossless choice is the one the spaced form `t 2 (0 1);` already gets: the value loads as an `ofStr` and is written as read. A typed list that keeps the count is also acceptable, if it is written back as read. A count that does not match the number of items (`t 3(0 1);`) raises `FoamKitError` naming the file and the line of the entry.
- The sub-dict error path: a failure inside a sub-dict names the line of the entry, not only the sub-dict (only for this shape, if a general change is larger).
- Tests: a new `tests/test_counted_list_value.py`, plus a byte-exact copy of one ESI file (for example `externalSolarLoad/system/air/changeDictionaryDict`) in `tests/releases/`, with its source in the docstring, if it loads once this is fixed.

## Out of scope
- The count on its own line being dropped on write (`t` / `2` / `(`): no data is lost to OpenFOAM, but the token is; recorded here, left to T-020's layout work or a follow-up ticket.
- `nonuniform List<T> N(…)` field values (T-068), counted list groups `2(1 2) 2(3 4)` (still `FoamKitError`, T-052), `N{…}` items (T-049), `on`/`off` writing inside typed lists (T-078).

## Acceptance criteria
- [ ] **Failing tests first**: every row of the first line of the table, at top level and inside a sub-dict, alone and between other entries.
- [ ] Each loads (as `ofStr` or a typed list; the tests record which) and is written with the same tokens as the source, count and parentheses included. Write 1 == write 2.
- [ ] `t 3(0 1);` raises `FoamKitError` naming the file and the entry line, at top level and in a sub-dict (or, if the value loads as `ofStr`, is written as read; the tests record which).
- [ ] The other rows keep their current behaviour (pinned).
- [ ] No input raises a bare exception.
- [ ] The ESI `externalSolarLoad` `air/changeDictionaryDict` loads, or its test names the next blocker.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): load entries whose value is a counted list (T-080)`.

## Risks
- **Behaviour change:** files that failed now load. If a typed list is chosen, `t 2(0 1);` and `t 2 (0 1);` load as different types; prefer the same type for both.
- **OpenFOAM versions:** ESI writes `inGroups` with a count in its tutorials; Foundation tutorials use none. Both read the glued and spaced forms the same way.
