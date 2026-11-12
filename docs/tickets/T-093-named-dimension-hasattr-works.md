# T-093: `hasattr(entry, 'value')` on a value-less dimension set (`dimensions [0 1 -1 0 0 0 0];`) returns `False` instead of raising

- **Issue:** [#132](https://github.com/mcgoldba/foamkit/issues/132)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (the two getters of `ofNamedDimension` in `foamkit/types/__init__.py`, plus tests in `tests/test_dimension_assignment.py`)
- **Related:** T-088 (#116, PR #131; added the `.value`/`.dimension` guards this ticket narrows), T-094 (the other T-088 review finding), T-017 (`FoamKitError` becomes an `Exception` subclass).
- **Depends on:** T-088 (merged). No other ticket.

## Goal
Reading `.value` or `.dimension` on a value-less dimension set follows Python's attribute protocol (`AttributeError`, nothing printed), so `hasattr`, `getattr(..., default)` and `inspect.getmembers` work, while assigning them still raises a `FoamKitError` that points to `.dimensions`.

## Today (planner, reproduced on 01fd879 = `origin/main`, 2026-11-11)
```python
import copy, inspect, pickle
from foamkit.types import ofNamedDimension
n = ofNamedDimension(name='dimensions', dimensions=[0, 1, -1, 0, 0, 0, 0])
```

| Call | On 45716b0 (before T-088) | On 01fd879 (now) |
|---|---|---|
| `hasattr(n, 'value')`, `hasattr(n, 'dimension')` | `False` | **prints ``ERROR: Entry 'dimensions': a dimension set has no `.value`; assign `.dimensions` instead.`` and raises `FoamKitError`** |
| `getattr(n, 'value', None)` | `None` | **the same ERROR line and `FoamKitError`** |
| `inspect.getmembers(n)` | 43 members | **`FoamKitError` (`.dimension`)** |
| `copy.deepcopy(n)`, `pickle` round trip | works | works |
| `n.value = 1`, `n.dimension = [0]*7` | **stored as a stray, unused attribute** | `FoamKitError` pointing to `.dimensions` (correct; T-088) |

Every field file (`0/U`, `0/p`, ...) has a `dimensions` entry, so any loop that probes entries with `hasattr`/`getattr(..., default)` now stops at it. `FoamKitError` still subclasses `SystemExit` (until T-017), so `hasattr` does not even swallow it as an ordinary exception.

Cause: T-088 made the getters of `ofNamedDimension.value` and `.dimension` call `_noSuchAttribute`, which raises `FoamKitError` via `userMsg(..., 'ERROR')`. `hasattr` and `getattr` with a default only catch `AttributeError`. Internal code is not affected: `_fpNames` skips property names and nothing in `foamkit/` probes `value`/`dimension` with `hasattr`.

## Design (planner, 2026-11-11)
- **Keep both properties; change only the getters.** The getter raises a plain `AttributeError` whose message names the entry and points to `.dimensions`, e.g. ``AttributeError("Entry 'dimensions': a dimension set has no `.value`; use `.dimensions`.")``. It prints nothing (no `userMsg`).
- **Setters stay as they are:** `FoamKitError` naming the entry and pointing to `.dimensions`, nothing stored (errors never pass silently).
- Rejected: deleting the getters (a setter-only property). Python's own message differs by version ("unreadable attribute" on 3.9/3.10, "property 'value' of 'ofNamedDimension' object has no getter" on 3.11+) and does not mention `.dimensions`.

## Scope
- `foamkit/types/__init__.py`: the `value` and `dimension` getters of `ofNamedDimension` (and `_noSuchAttribute` if the message text is shared).
- `tests/test_dimension_assignment.py`: new tests next to the existing `ofNamedDimension` guard tests.

## Out of scope
- `ofDimensionedScalar` (`nu [dims] 1e-05;`, `nu nu [dims] 1e-05;`): it has real `.value` and `.dimension`.
- `FoamKitError`'s base classes (T-017).
- Other attributes that types do not have (they already raise `AttributeError`).

## Acceptance criteria
- [ ] **Failing tests first:** the three bold "now" rows.
- [ ] On `ofNamedDimension(name='dimensions', dimensions=[0, 1, -1, 0, 0, 0, 0])` and on the `dimensions` entry of `tests/fixtures/pitzDaily/0/U` (loaded): `hasattr(n, 'value')` and `hasattr(n, 'dimension')` are `False`; `getattr(n, 'value', 'x')` and `getattr(n, 'dimension', 'x')` return `'x'`; `inspect.getmembers(n)` returns and includes `dimensions`. None of these prints anything (`capsys` empty).
- [ ] `n.value` and `n.dimension` raise `AttributeError` whose message names the entry and contains `.dimensions`.
- [ ] The existing T-088 tests stay green unchanged: `n.value = ...` and `n.dimension = ...` raise `FoamKitError` naming the entry and pointing to `.dimensions`, leave no attribute in `vars(n)` and leave the written text unchanged.
- [ ] `copy.deepcopy(n)` and a `pickle` round trip write `dimensions [0 1 -1 0 0 0 0];` as before; `case.save()` → `fk load` → write of pitzDaily keeps `0/U` byte-identical.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): hasattr on a dimension set returns False instead of raising (T-093)`; the commit body says reading `.value`/`.dimension` on a value-less dimension set raises `AttributeError`, and assigning them still raises `FoamKitError`.

## Risks
- **Behaviour change:** code that caught `FoamKitError`/`SystemExit` from *reading* these attributes now gets `AttributeError` (T-088 is unreleased, so no release shipped that behaviour).
- An uncaught `n.value` shows a normal Python traceback rather than a one-line `ERROR:`; this is the standard attribute protocol the maintainer asked for, and assignments keep the one-line error.
- No OpenFOAM version differences (no file format change).
