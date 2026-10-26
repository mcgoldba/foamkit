# T-029: `#includeModel` and `#includeConstraint` keep their quoting and support arguments

- **Issue:** [#40](https://github.com/mcgoldba/foamkit/issues/40)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-004, T-015. It reuses T-015's argument scanning and original-quoting design.
- **Split from:** T-016, 2026-10-21 (maintainer-approved)

## Goal
Foundation `fvModels` and `fvConstraints` files that use `#includeModel` / `#includeConstraint` load, and are written back the way they were, like `#includeFunc` since T-015.

## Evidence (real tutorial trees, 2026-10-21)
- **`#includeModel`:** Foundation, 4/4/7/7 files in 11/12/13/14. Example: `fluid/roomHeating/constant/fvModels:17` `#includeModel heatSource` (`tests/releases/foundation-14.roomHeating.fvModels`). It loads today, but **is written quoted** (`"heatSource"`).
- **`#includeConstraint`:** Foundation, 7/9/11/13 files. Example: `XiFluid/engine2Valve2D/system/fvConstraints:17-19` (`tests/releases/foundation-14.engine2Valve2D.fvConstraints`):
  ```
  #includeConstraint limitLowPressure(min=1e4)
  #includeConstraint limitTemperature(phase=u, min=290, max=3000)
  ```
  This **fails** with "Could not find functionEntry bracket type".
- **`#includeIfPresent`** (Foundation only, 1 per release) also loads but is written quoted. Include it here if its quoting differs from the source; T-004 kept the keyword, not the quoting.

## Scope
- Treat `#includeModel`, `#includeConstraint` (and `#includeIfPresent`, if needed) like `#includeFunc` after T-015: keep the original quoting per entry and support `name(args)` with nested parentheses. Share the code with `ofIncludeFunc` rather than duplicating it.

## Out of scope
- Resolving the included files

## Acceptance criteria
- [ ] **Failing tests first** with both real fixtures, plus a `#includeIfPresent` line from a Foundation tutorial (record its source).
- [ ] After the fix, both files load, and every directive line is written back byte-identical (keyword, quoting, arguments).
- [ ] T-015's `#includeFunc` tests still pass unchanged.
- [ ] All existing golden files are unchanged. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Refactoring the shared code could change `#includeFunc` output.** T-015's tests guard it.

## Ranking rationale
Medium-high: a load failure in 7-13 Foundation `fvConstraints` files per release, and wrong quoting in `fvModels`. It is small, because it reuses T-015.
