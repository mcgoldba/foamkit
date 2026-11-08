# T-081: dimension sets and dimensioned values keep every token instead of silently shifting or dropping them

- **Issue:** [#108](https://github.com/mcgoldba/foamkit/issues/108)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (two parser functions; a shape that is not exactly understood is kept as text, as several already are)
- **Related:** T-014 (#21; `nu nu [dims] value` loses its value: the real-file case, not in this ticket), T-013 (#20; named units `[m^2/s]`, `[velocity]`, `0 [deg]`, `uniform 3 [bar]`: not in this ticket), T-082 (#109; tensor classes; dimensioned tensor values here stay text and do not need it), T-032 (number text), T-075 (`1_0`), T-056 (comments).
- **Depends on:** T-014 (#21, ranked #3, ahead of this ticket; maintainer, 2026-11-08). Both change `_parseDimensionValue` and `_parseDimensionedType`; T-014 also makes spaces inside the brackets work, for the named and the unnamed form.
- **Maintainer decision to confirm at approval:** what happens to a shape FoamKit does not type. (A, recommended) It is kept verbatim as `ofStr`, as `nu [0 2 -1 0 0] 1e-05;` and `U [0 1 -1 0 0 0 0] (1 0 0);` already are; `FoamKitError` with file and line only where the text cannot be kept. (B) Raise `FoamKitError` for shapes OpenFOAM rejects. That needs per-release rules (5 exponents, fractional exponents) that are not checked against an OpenFOAM build, so it is not S.

## Goal
An entry with a dimension set (`[0 2 -1 0 0 0 0]`) is read and written back with every token it had, in order, or raises `FoamKitError` naming the file and line; FoamKit never moves a value into the exponents, drops a word or drops the value.

## Today (planner, reproduced on f8590d8 + 9ccebff, `foamkit/` unchanged, 2026-11-08)
Every row behaves the same at the top level and inside a sub-dict unless noted; write 1 == write 2 in all loading rows, so the change is permanent after one write.

| Input | Loads as | Write 1 |
|---|---|---|
| `nu [0 2 a 0 0 0 0] 1;` | `ofNamedDimension` | **`nu [0 2 0 0 0 0 1];`** (`a` dropped, the value becomes the 7th exponent) |
| `nu [a 2 -1 0 0 0 0] 1;`, `nu [0 2 -1 0 0 0 a] 1;` | `ofNamedDimension` | **`[2 -1 0 0 0 0 1]`**, **`[0 2 -1 0 0 0 1]`** |
| `nu [0 2 -1.5 0 0 0 0] 1;` | `ofNamedDimension` | **`[0 2 0 0 0 0 1]`** |
| `nu [0 2 -1 0 0 0] 1;` (6 exponents) | `ofNamedDimension` | **`[0 2 -1 0 0 0 1]`** |
| `U [0 1 -1 0 0 0] (1 0 0);` | `ofNamedDimension` | **`U [0 1 -1 0 0 0 0];`** (vector lost, a `0` exponent added) |
| `v [0 1 -1 0 0 0] uniform 1;` | `ofNamedDimension` | **`[0 1 -1 0 0 0 1]`** (`uniform` dropped) |
| `nu [0 2 -1 0 0 0 0] abc;`, `… $x;`, `… on;` | `ofNamedDimension` | **`nu [0 2 -1 0 0 0 0];`** (value lost) |
| `nu [ 0 2 -1 0 0 0 0 ] 1e-05;` (spaces inside the brackets; fixed by T-014, pinned here) | `ofNamedDimension` | **`nu [0 2 -1 0 0 0 0];`** (value lost) |
| `nu 1e-05 [0 2 -1 0 0 0 0];` | `ofNamedDimension` | **`nu [0 2 -1 0 0 0 0];`** (value lost) |
| `x 1 2 [3] 4 5 6 7;` | `ofNamedDimension` | **`x [1 2 3 4 5 6 7];`** |
| `nu [0 2 -1 0 0 0 0 0] 1;` (8 or 9 exponents) | top level: **bare `ValueError`** (a 7-line help text, no file or line); sub-dict: `FoamKitError` with file and line | |
| `s [0 2 -2 0 0 0 0] (1 0 0 0 0);` | **bare `Exception: 'ofSymmTensor' values must be a numeric list of length 6.`** (top level and sub-dict) | |
| `s [0 2 -2 0 0 0 0] (1);` | top level: **bare `AttributeError`**; sub-dict: loads, write gives a **bare `TypeError`** | |

Already lossless (pin them): `nu [0 2 -1 0 0 0 0] 1e-05;` (`ofDimensionedScalar`; also with tabs, two spaces, ` ;`, the value on the next line, `-1`); `dimensions [0 1 -1 0 0 0 0];`; `nu [0 2 -1 0 0 0 0];`. Kept as `ofStr` text: `nu [0 2 -1 0 0] 1e-05;` (5 exponents), `nu [0 2 -1 0 0 0 0]1e-05;`, `nu [0 2 -1 0 0 0 0] 1 2;`, `nu [] 1;`, `dimensions [0 1 a 0 0 0 0];`, `dimensions [0 1 -1 0 0];`, `U [0 1 -1 0 0 0 0] (1 0 0);`, `T [0 2 -2 0 0 0 0] (9 numbers);`, `s [dims] (6 numbers);`, `v [0 1 -1 0 0 0 0] uniform (1 0 0);`, and the T-013 forms `nu [m^2/s] 1e-05;`, `nu [m^2 s^-1] 1e-05;`, `nu [velocity] 1;`, `dimensions [velocity];`, `dimensions [m/s];`.

**Cause.** `_parseDimensionValue` (~7127) keeps every token after the key that `int()` accepts once `[`, `]` and `;` are stripped, drops the others, and returns an `ofNamedDimension` if exactly 7 are left. `_parseDimensionedType` (~6894) needs a number glued to `[` (`[0`), so `[ 0 …` falls through to `_parseDimensionValue`. Its list branch maps 5 numbers to `ofDimensionedSymmTensor` (a symmetric tensor has 6) and 1 number to `ofDimensionedSphericalTensor`, whose constructors fail (the T-082 cause).

## Real tutorials
Method: `git grep` for `[…]` lines under `tutorials/` (Foundation clones at 9cbf94f3 and 31554318; ESI v2606 tarball read with `git grep --no-index`), `polyMesh` and scripts excluded. Each distinct one-line entry ending in `;` was loaded and written by FoamKit at f8590d8, and the written tokens compared with the source tokens (numbers by value).

| Release | Entries checked | Changed on write | T-014 shape (`key key [dims] value`) | Shapes in this ticket |
|---|---|---|---|---|
| Foundation 11 | 1953 | 16 lines, 10 files | 16 | 0 |
| Foundation 14 | 2232 | 0 (7 files raise a bare `ValueError` on `uniform 3 [bar]`: T-013) | 0 | 0 |
| ESI v2606 | 3670 | 64 lines, 29 files | 64 | 0 |

So no shipped tutorial hits this ticket's shapes on one line; they come from hand-edited or generated files. The real-file loss is T-014's shape: for example ESI `heatTransfer/buoyantSimpleFoam/hotRadiationRoom/constant/radiationProperties` (`absorptivity absorptivity [0 -1 0 0 0 0 0] 0.5;` written without `0.5`) and Foundation 11 `XiFluid/kivaTest/constant/combustionProperties`. A looser regex count finds 80 such ESI lines in 38 files with a non-integer value, 43 of them with spaces inside the brackets (`nu nu [ 0 2 -1 0 0 0 0 ] 1.e-05;`), so T-014 handles spaces inside the brackets (see Overlap). Named entries with an integer value (`Su Su [0 1 -1 0 0 0 0] 0;`) survive only because 8 integers fail the count. The 5-exponent form is real and must stay lossless: Foundation 11 `compressibleVoF/throttle/constant/thermodynamicProperties` (`psiv [0 -2 2 0 0] 2.5e-06;`), ESI `StefanProblem` `TSat TSat [0 0 0 1 0] 373.15;`.

## Overlap with T-013 and T-014
- **T-013** owns named units and unit annotations (`[velocity]`, `[m^2/s]`, `0 [deg]`, `uniform 3 [bar]`) and the `.units` attribute. Here they must stay exactly as today (text, lossless). This ticket does not type them.
- **T-014** (lands first) owns the name in `key name [dims] value`, its lost value, and spaces inside the brackets for both forms. This ticket owns the rest of the bracket contents (count, non-integer tokens), values that are not numbers, a value before the brackets, and the bare exceptions, and pins T-014's spaced rows.

## Scope
- `foamkit/types/__init__.py`: `_parseDimensionValue` returns an `ofNamedDimension` only for a value that is exactly one `[ … ]` of 7 integers (any spacing inside, as read since T-014) and nothing else. In `_parseDimensionedType`, the 5-number and 1-number branches go, so dimensioned tensor values stay text like the 3- and 9-number ones. Every other shape follows the option chosen above.
- Tests: a new `tests/test_dimension_set_tokens.py`.

## Out of scope
- `nu nu [dims] value` and spaces inside the brackets (T-014), named units and unit annotations (T-013).
- Typing dimensioned vectors and tensors (they stay text). Editing `.dimensions`.
- Number text (`1.50` → `1.5`, `2` → `2.0`; T-032), `1_0` (T-075), a `// c` after the entry (T-056), `nu` / `[…] 1e-05;` with the key on its own line (already a `FoamKitError`).

## Acceptance criteria
- [ ] **Failing tests first**: every bold row above, at the top level and in a sub-dict.
- [ ] Each of those rows writes back the same tokens in the same order (numbers compared by value) and write 1 == write 2, or raises `FoamKitError` naming the file and line. No row raises a bare exception.
- [ ] `nu [ 0 2 -1 0 0 0 0 ] 1e-05;` still loads as `ofDimensionedScalar` with `.value == 1e-05` (fixed by T-014; pinned).
- [ ] Every "already lossless" input above keeps its type and output (pinned), including the T-013 forms and the 5-exponent form.
- [ ] A byte-exact copy of Foundation 11 `compressibleVoF/throttle/constant/thermodynamicProperties` (commit 9cbf94f3, blob in the docstring, as in `tests/test_bound_box.py`) round-trips its 5-exponent entries; the existing `tests/releases/foundation-1[34].aerofoilNACA0012Steady.U` fixtures keep their output.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): keep every token of dimension sets and dimensioned values (T-081)`.

## Risks
- **Type change:** malformed entries that loaded as `ofNamedDimension` (with wrong exponents) load as `ofStr`, so `.dimensions` is gone for them. Say so in the commit body.
- **Golden files:** none should change; any golden change is a regression.
- **OpenFOAM versions:** whether OpenFOAM accepts 5 exponents or fractional exponents is not checked against a build; option A keeps them as text, so the answer does not change what FoamKit writes.
