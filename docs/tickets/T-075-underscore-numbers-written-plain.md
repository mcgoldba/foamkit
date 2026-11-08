# T-075: numbers spelled with `_` (`1_0`) are read as numbers and written without the `_`

- **Issue:** [#102](https://github.com/mcgoldba/foamkit/issues/102)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (one rule for the number text of list groups, plus tests that pin every other number path)
- **Related:** T-071 (#92, PR #101, list groups keep their number text), T-032 (number spelling elsewhere).
- **Depends on:** none. Start after T-020 merges, because both change `foamkit/types/__init__.py`.
- **Maintainer decision to confirm at approval:** PR #101, 2026-11-08: "valid python float and int types with '_' should be read and interpreted as the corresponding float and int value without the '_' that is valid for OpenFOAM." Coordinator's reading: a token that Python's `int()`/`float()` accept and that contains `_` (`1_0`, `1_000.5`, `-2_5e1_0`) loads as the plain number and is **written back without the `_`**, so the written file is valid OpenFOAM.

## Goal
A number token such as `1_0` loads as the number 10 everywhere FoamKit reads numbers, and FoamKit never writes a `_` inside a number, so the written file is valid OpenFOAM.

## Today (planner, reproduced on f8590d8, 2026-11-08)
Every path reads `1_0` as 10, because it uses Python `int()`/`float()` (`_parseValue`, ~6101-6170; `_numberReprs`, ~1772-1781). Only list groups write the `_` back. That started with T-071, which keeps their source text; main before T-071 wrote `10`.

| Input | Loads as | Written as |
|---|---|---|
| `x 1_0;`, `x +1_0;` | `ofInt` 10 | `10` |
| `x 1_000.5;`, `x 1.5_0;` | `ofFloat` 1000.5, 1.5 | `1000.5`, `1.5` |
| `x -2_5e1_0;`, `x 1_0e5;` | `ofFloat` | `-250000000000.0`, `1000000.0` (spelling is T-032) |
| `l (1_0 2 3_0.5);` (top level and sub-dict) | `ofSplitList` 10, 2, 30.5 | `10`, `2`, `30.5` |
| `v uniform 1_0;`, `v uniform (1_0 0 0);` | `ofUniformField` | `uniform 10;`, `uniform (10.0 0.0 0.0);` |
| `nu [0 2 -1 0 0 0 0] 1_0;` | `ofDimensionedScalar` 10.0 | `10.0` |
| `box (1_0 0 0) (1 1 1);` (top level and sub-dict) | `ofBoundBox`, `.value[0][0] == 10.0` | **`(1_0 0 0) (1 1 1)`**, which OpenFOAM does not read as 10 (T-071 review; not checked against an OpenFOAM build) |
| `c (1_0 2) (3 4);`, `c (1_0 2) (3 4) (5 6);` | `ofListGroups`, `ofInt` 10 | **`(1_0 2) …`** |
| `x 1__0;`, `x _10;`, `x 10_;`, `x 1_e5;`, `x 0x10;` | `ofStr` (not valid Python literals) | as read |
| `x nan;`, `x inf;`, `x -Infinity;`, `l (nan inf 1);`, `box (-inf 0 0) (inf 1 1);` | `ofFloat` | `nan`, `inf`, `-inf`; boxes keep `-inf`/`inf`. Consistent across paths, so unchanged here |

Values that FoamKit does not read as numbers stay text: `nu nu [0 2 -1 0 0 0 0] 1_0;` is an `ofStr`, and `internalField nonuniform List<scalar> 3(1_0 2 3);` is an `ofStr`. Both are written as read.

## Scope
- `foamkit/types/__init__.py`: `_parseListGroups` and `ofListGroups._groupString` (source text with `_` is written without the `_`, e.g. `1_0` → `10`, `-2_5e1_0` → `-25e10`). Equivalent: the source text of such a token is not kept, and the number is written from its value.
- The `.params` cache: a cached group whose source text holds `_` is written without it.
- Tests: a new `tests/test_underscore_numbers.py` that pins every row above, at top level and inside a sub-dict.

## Out of scope
- Rejecting `_` (the maintainer chose to read it). Changing `nan`/`inf` handling. Number spelling of other paths (`1000000.0`, T-032). Values that are not read as numbers (`ofStr`, nonuniform fields: T-068).

## Acceptance criteria
- [ ] **Failing tests first**: every row of the table, at top level and inside a sub-dict. Each records the loaded type and value, and checks that write 1 has no `_` inside a number token and that write 1 == write 2.
- [ ] `box (1_0 0 0) (1 1 1);` loads as an `ofBoundBox` and is written `(10 0 0) (1 1 1)`. `c (1_0 2) (3 4);` is written `(10 2) (3 4)`. `box (1_000.5 0 0) (1 1 1);` is written with `1000.5`. Other groups in the same file keep their source text (`8e-3` stays `8e-3`).
- [ ] The `ofStr` rows (`1__0`, `_10`, `10_`, `1_e5`, `0x10`) stay words and are written as read.
- [ ] The scalar, list, `uniform` and dimensioned rows keep their current output (pinned).
- [ ] `nan`/`inf` rows unchanged.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): write list-group numbers spelled with _ without the _ (T-075)`.

## Risks
- **Behaviour change:** a group written as `1_0` since T-071 is now written `10`. No real tutorial file is known to contain `_` in a number.
- **Maintainer reading:** if approval chooses a different reading (for example, raising `FoamKitError`), only the list-group rows and their expected output change.
- **OpenFOAM versions:** none expected. The claim that OpenFOAM reads `1_0` as a word comes from the T-071 review. It does not affect the fix, because the written output contains only plain numbers.
