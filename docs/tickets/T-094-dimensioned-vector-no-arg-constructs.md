# T-094: `ofDimensionedVector()` with no arguments constructs again, with the all-zero dimension set

- **Issue:** [#133](https://github.com/mcgoldba/foamkit/issues/133)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (the constructor of `ofDimensionedVector` in `foamkit/types/__init__.py`, plus tests in `tests/test_dimension_assignment.py`)
- **Related:** T-088 (#116, PR #131; added the validating `dimensions` setter that the dataclass default now hits), T-093 (the other T-088 review finding), T-082 (#110; tensor writes).
- **Depends on:** T-088 (merged). No other ticket.

## Goal
`fkt.ofDimensionedVector()` constructs with no output and the all-zero dimension set, as `ofDimension()` and `ofDimensionedScalar()` do, while an explicit invalid set still raises `FoamKitError`.

## Today (planner, reproduced on 01fd879 = `origin/main`, 2026-11-11)
```python
import foamkit.types as fkt
fkt.ofDimensionedVector()
```

| Call | On 45716b0 (before T-088) | On 01fd879 (now) |
|---|---|---|
| `ofDimensionedVector()` | constructs, **`.dimensions == []`** (an invalid set, stored silently) | **prints `ERROR: Dimension set: dimensions must be 7 integer exponents, e.g. [0 2 -1 0 0 0 0]; got [].` and raises `FoamKitError`** (the user passed no set) |
| `ofDimensionedVector(dimensions=[0, 1, -1, 0, 0, 0, 0])` | `[0, 1, -1, 0, 0, 0, 0]` | `[0, 1, -1, 0, 0, 0, 0]` |
| `ofDimensionedVector(dimensions=[0, 1])` | **`[0, 1]` stored silently** | `FoamKitError` (correct; T-088) |
| `ofDimension()`, `ofDimensionedScalar()`, `ofNamedDimension()` | construct | construct, `[0, 0, 0, 0, 0, 0, 0]` |
| `ofDimensionedTensor()`, `ofDimensionedSymmTensor()`, `ofDimensionedSphericalTensor()` | `TypeError: Value for 'ofVector' must be a list of length 3.  Got 'None'` | `FoamKitError` ``... got <property object at 0x...>.`` (see Out of scope) |

Cause: `ofDimensionedVector` is a `@dataclass` with no `__init__` of its own, so the generated `__init__(self, value=None, _comment=None, name=None, dimensions=<factory>)` replaces `ofDimensionedScalar.__init__` and assigns the field default `dimensions=[]` (`_ofDimensionedScalarBase`, near line 1419) through the validating `dimensions` property (T-088).

Impact: the parser never produces this type (`g [0 1 -2 0 0 0 0] (0 -9.81 0);` loads as `ofStr` today), so no file is affected. It is a loud regression of a public constructor in unreleased code, with a misleading message. No-argument construction is also how a `.params` cache load builds each entry (`foamkit/functions/load.py`, `type_()`).

## Design (planner, 2026-11-11)
- **No set given means all zeros**, as `ofDimension(None)` and `ofDimensionedScalar(dimensions=None)` already do; only an explicit value goes through `_dimensionSet`.
- Recommended: give `ofDimensionedVector` an explicit `__init__` (a `@dataclass` keeps an `__init__` defined in the class body) with the **same parameters and positional order as today**, `(value=None, _comment=None, name=None, dimensions=None)`, storing the set the same way `ofDimensionedScalar.__init__` does (`__dict__['dimension']`, so the `.params` cache key is unchanged). The implementer may choose another way if every criterion holds.
- Explicit `dimensions=[]` keeps raising: it is an invalid set the user passed, not a missing one.

## Scope
- `foamkit/types/__init__.py`: `ofDimensionedVector` (and `_ofDimensionedVectorBase`/`_ofDimensionedScalarBase` only if the field default must change).
- `tests/test_dimension_assignment.py`: add `ofDimensionedVector()` to the no-argument default tests.

## Out of scope
- **Tensor classes** (`ofDimensionedTensor`, `ofDimensionedSymmTensor`, `ofDimensionedSphericalTensor`): they could not be built with no arguments before T-088 either (`TypeError` about the missing vector value). Since T-088 the first error is a `FoamKitError` quoting `<property object at 0x...>`, because the `dimensions` property of `ofDimension` becomes their dataclass default. Making them constructible, or fixing that message, is a separate ticket if the maintainer wants one.
- `ofDimensionedVector`'s value path: `ofDimensionedVector(name='g', value=fkt.ofVector(value=[0, -9.81, 0]))` raises `Float value: ... is not a number`, and its `toString` writes no dimension set (both on 45716b0 too). Reading one-line dimensioned vectors is T-081/T-082 territory.

## Acceptance criteria
- [ ] **Failing test first:** the bold "now" row of `ofDimensionedVector()`.
- [ ] `ofDimensionedVector()` and `ofDimensionedVector(dimensions=None)` construct with no output (`capsys` empty); `.dimensions == [0, 0, 0, 0, 0, 0, 0]` and `.dimension` is an `ofDimension` with that set.
- [ ] `ofDimensionedVector(dimensions=v)` stores `[0, 1, -1, 0, 0, 0, 0]` for every accepted input of T-088's `VALID` set (list, tuple, string, spaced string, integral floats, an `ofDimension`).
- [ ] `ofDimensionedVector(dimensions=v)` for `[]`, `[0, 1]`, `[0, 'a', -1, 0, 0, 0, 0]`, `[0, 2.5, -1, 0, 0, 0, 0]` and `'a'` raises `FoamKitError` with the T-088 message; no bare exception escapes.
- [ ] `inspect.signature(fkt.ofDimensionedVector)` lists `value, _comment, name, dimensions` in that order; `ofDimensionedVector.dimensions is ofDimensionedScalar.dimensions` (existing T-088 test) stays green.
- [ ] The tensor classes' no-argument behaviour is pinned as it is on 01fd879 (raises, never constructs with an invalid set), so a later change is deliberate.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): ofDimensionedVector() constructs with the all-zero dimension set (T-094)`.

## Risks
- **Positional arguments:** replacing the generated `__init__` must keep `(value, _comment, name, dimensions)`; delegating to `ofDimensionedScalar.__init__`'s order `(arg1, arg2, name, value, ...)` would silently reinterpret positional calls.
- **Behaviour change:** before T-088 a no-argument object held `[]`; it now holds seven zeros, matching the other dimensioned types (T-088 is unreleased).
- No OpenFOAM version differences (no file format change).
