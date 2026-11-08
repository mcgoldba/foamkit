# T-077: type hints on the public `ofListGroups` / `ofBoundBox` API

- **Issue:** [#104](https://github.com/mcgoldba/foamkit/issues/104)
- **Type:** code (owner: `implementer`; no behaviour change, so no failing tests)
- **Size:** S
- **Related:** T-071 (#92, PR #101), T-002 (CI ratchet baseline).
- **Depends on:** T-076 (it changes the `value` getter). Start after T-020 merges.

## Goal
Every public function added or re-based by T-071 has type hints, as CLAUDE.md requires, so editors and mypy users see the types of `ofBoundBox(...)`, `.value` and `.groups`.

## Today (planner, checked on f8590d8, 2026-11-08)
- No hints: `ofBoundBox.__init__`, the `ofBoundBox.value` getter and setter, `ofBoundBox.__iter__`/`__eq__`/`__repr__`, `ofListGroups.__init__`, `ofListGroups.__str__`.
- Hinted: `ofListGroups.groups` (only `-> list`), `ofListGroups.toString` (`-> str`).
- Private helpers without hints (optional here): `_numberReprs`, `_boxGroups`, `_ReadOnlyFloatList`.
- `mypy foamkit/` gives 123 errors, equal to the baseline in `.github/workflows/ci.yml` (ruff 189, format 55, mypy 123). In this code it reports one finding: `foamkit/types/__init__.py:1926: Dataclass attribute may only be overridden by another attribute [misc]`, on the `value` property. mypy skips the bodies of unannotated functions, so adding hints can surface new findings in them.

## Scope
- `foamkit/types/__init__.py`: hints on the functions listed above. Use `typing` forms valid on Python 3.9 (`List[...]`, `Optional[...]`, or `from __future__ import annotations`), e.g. `groups -> List[ofList]` and `value -> List[List[float]]`.
- `.github/workflows/ci.yml`: lower the ratchet baseline if the counts drop.

## Out of scope
- Hints elsewhere in the module. Behaviour changes. Repo-wide ruff format (Deferred).

## Acceptance criteria
- [ ] Every function listed under Today has parameter and return hints that are valid on Python 3.9.
- [ ] `mypy foamkit/`, `ruff check .` and `ruff format --check .` show no new findings. Any finding the new hints surface is fixed, or else the PR body explains why it is left. If a count drops, the baseline in `ci.yml` is lowered in this PR.
- [ ] `pytest -q` passes, and `tests/test_bound_box.py` passes unchanged.
- [ ] A `refactor:` or `chore:` PR title, e.g. `refactor(types): type hints on ofListGroups and ofBoundBox (T-077)` (no CHANGELOG entry for users).

## Risks
- Hints that are wrong for real inputs (for example `int` vs `float` items, or `ofList` vs plain lists) mislead users. Check them against the T-071 tests.
- **OpenFOAM versions:** none.
