# T-082: symmetric and full tensor values (`uniform (1 0 0 0 0 0)`) are written back instead of crashing with a bare `AttributeError`

- **Issue:** [#109](https://github.com/mcgoldba/foamkit/issues/109)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (the three tensor classes and their writer; the wrong-count error at the top level)
- **Related:** T-045 (#61; its `value uniform (1);` row is the same bug for `ofSphericalTensor` and is fixed here; its `x (10);` load `TypeError` stays there), T-081 (#108; dimensioned tensor values `s [dims] (…)`, kept as text there), T-032 (number text), T-056 (comments), T-068 (reading field values).
- **Depends on:** none. Start after T-020 merges (same file).
- **Maintainer decision (2026-11-08): option A.** Components are written as floats, the same as `ofVector` today (`(1 0 0 0 0 0)` → `(1.0 0.0 0.0 0.0 0.0 0.0)`); T-032 later keeps the number text for all of them.

## Goal
A field or dictionary holding a symmetric tensor (6 components), a tensor (9) or a spherical tensor (1), such as Foundation 14's `0/R` with `internalField uniform (0.00497 0 0 0.00497 0 0.00497);`, is written back with all its components; anything still unsupported raises `FoamKitError` naming the file and line, never a bare exception.

## Today (planner, reproduced on f8590d8 + 9ccebff, `foamkit/` unchanged, 2026-11-08)
Rows behave the same at the top level, inside a sub-dict and in a `boundaryField` patch unless noted.

| Input | Loads as | Write |
|---|---|---|
| `v uniform (1 0 0 0 0 0);` (also `( 1 0 0 0 0 0 )`, `1e-16` components, `) ;`, a trailing `// c`) | `ofUniformField(ofSymmTensor)` | **bare `AttributeError: 'ofSymmTensor' object has no attribute '_name'`** |
| `v uniform (1 0 0 0 1 0 0 0 1);` | `ofUniformField(ofTensor)` | **bare `AttributeError`** (`ofTensor`) |
| `v uniform (1);` (T-045 row) | `ofUniformField(ofSphericalTensor)` | **bare `AttributeError`** (`ofSphericalTensor`) |
| multi-line `internalField nonuniform List<symmTensor>` / `2` / `(` / `(1 0 0 1 0 1)` … / `)` / `;` | `ofMultilineStatement`, items `ofSymmTensor` holding text (`'1.0'`) | **bare `AttributeError`** |
| `volSymmTensorField` / `volTensorField` files with the rows above in `internalField` and in a patch `value` | load | **bare `AttributeError`**: the whole file cannot be written |
| `v uniform (1 0 0 0 0);`, `(… 7 numbers)`, `(a 0 0 0 0 0)` | top level: **bare `ValueError`** (a list of 12 class names, no file or line); sub-dict: `FoamKitError` with file and line | |
| `v nonuniform List<symmTensor> 2((1 0 0 0 0 0) (2 0 0 0 0 0));`, `… List<tensor> 1((…));` (one line) | `ofStr` | written back as read |
| `v uniform (1 0 0);` | `ofUniformField(ofVector)` | `uniform (1.0 0.0 0.0);`, write 1 == write 2 (number text: T-032) |
| `s (1 0 0 0 0 0);`, `s (1 0 0 0 1 0 0 0 1);` (plain entry) | `ofSplitList` of `ofInt` | multi-line list, stable (layout: T-020). A plain entry is a list: OpenFOAM decides the type from the code that reads it, so FoamKit keeps it as a list |

Real files, loaded and written at f8590d8: Foundation 14 `incompressibleFluid/ductSecondaryFlow/0/R` (commit 31554318, blob 6c48891b), `incompressibleFluid/planarContraction/0/sigma` (blob cce31349), ESI v2606 `verificationAndValidation/turbulenceModels/planeChannel/setups.orig/EBRSM/0.orig/R`, ESI `combustion/PDRFoam/flamePropagationWithObstacles/system/changeDictionaryDict` and Foundation 11 `legacy/combustion/PDRFoam/flamePropagationWithObstacles/0/CR.orig` all load and then fail on write with the bare `AttributeError`.

**Cause.** `ofSphericalTensor`, `ofSymmTensor` and `ofTensor` (~2667-2720) are `@dataclass` subclasses of `ofVector` with no `__init__` of their own, so the generated one never runs `_ofNamedTypeBase.__init__` and `_name` is never set (the T-045 `TypeError: ofSphericalTensor.__init__() got multiple values for argument '_comment'` has the same root). **Second, hidden behind the crash:** `ofVector.valueStr` (~2627) writes exactly three components. With `_name` set by hand, a 6-component `ofSymmTensor` and a 9-component `ofTensor` both write `(1.0 2.0 3.0)`, and `ofSphericalTensor` raises `IndexError`. Fixing only the constructor would turn a loud crash into silent truncation, so the tests must pin the component count.

## Real tutorials
`git grep` under `tutorials/` (Foundation clones at 9cbf94f3 and 31554318; ESI v2606 tarball with `git grep --no-index`), `polyMesh` excluded.

| Release | `uniform (` 6 numbers `)`: files (lines) | 9 numbers | 1 number | `List<symmTensor\|tensor\|sphericalTensor>` | `vol*TensorField` files |
|---|---|---|---|---|---|
| Foundation 11 | 9 (16) | 0 | 0 | 3 (legacy PDRFoam `CR.orig`, `CT.orig`, `nsv.orig`) | 9 |
| Foundation 14 | 6 (6) | 0 | 0 (2 hits are C++ in `floatingBeam` `dynamicMeshDict`) | 0 | 6 |
| ESI v2606 | 7 (16) | 0 | 0 | 0 | 6 |

The 6-number files are the viscoelastic `sigma` fields (`planarContraction`, `planarCouette`, `planarPoiseuille`, `climbingRod` `sigma.liquid`), Reynolds-stress `R` fields (`ductSecondaryFlow`, ESI `planeChannel` `EBRSM`) and the PDRFoam files. None of them can be written today.

## Scope
- `foamkit/types/__init__.py`: the three tensor classes get a working constructor (name, value, comment), and their writer writes every component (6, 9 or 1). The multi-line `nonuniform List<symmTensor>` path stores numbers, not text. `uniform` with a component count that matches no type raises `FoamKitError` with file and line at the top level too, as it already does in a sub-dict.
- Tests: a new `tests/test_tensor_values.py`, using byte-exact copies of Foundation 14 `ductSecondaryFlow/0/R` and `planarContraction/0/sigma` in `tests/releases/` (source commit and blob in the docstring, as in `tests/test_bound_box.py`).

## Out of scope
- Dimensioned tensor values `s [dims] (…)` (T-081). The plain-entry `x (10);` load `TypeError` and one-item lists (T-045).
- Number text (T-032), the `// 2*k/3` comment after the ESI `R` value (T-056), layout (T-020).
- Typing one-line `nonuniform List<…>` values (they stay text; T-068 reads field values).

## Acceptance criteria
- [ ] **Failing tests first**: every bold row above, at the top level, in a sub-dict and in a `boundaryField` patch, plus the two real fixtures.
- [ ] Symmetric tensor, tensor and spherical tensor values load with all their components as numbers and are written with the same number of components and the same values; write 1 == write 2, and the re-read tree equals the first.
- [ ] A test pins that a 6- and a 9-component value is never written with 3 components.
- [ ] Both real fixtures load and are written; write 1 == write 2.
- [ ] Wrong-count `uniform` values raise `FoamKitError` naming the file and line at the top level and in a sub-dict. No input raises a bare exception.
- [ ] Vectors, plain `s (…)` lists and one-line `nonuniform List<…>` text keep their current output (pinned). T-045's `value uniform (1);` row passes; tell the planner so T-045 drops it.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): write symmetric and full tensor values (T-082)`.

## Risks
- **Behaviour change:** tensor field files that could not be written now write. Their components gain `.0`, as vectors already do (option A, maintainer 2026-11-08).
- **Silent truncation:** see Cause; the main thing the reviewer checks.
- **OpenFOAM versions:** the 6-component order (`xx xy xz yy yz zz`) is the same in Foundation and ESI; FoamKit only keeps the order it read, so no mapping is needed.
