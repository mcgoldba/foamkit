# T-032: Numbers are written the way they were read (`5e-4` stays `5e-4`)

- **Issue:** [#43](https://github.com/mcgoldba/foamkit/issues/43)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-020. This is one root cause inside "write it back the way it was". If T-020 lands first with per-entry source text, this ticket may be covered for unedited entries; then keep only the edited-value part, or close it as duplicate.

## Goal
An unedited numeric value is written back exactly as it appeared in the source.

## Evidence (2026-10-21)
- Planner reproduction: `a 5e-4;` is written as `a 0.0005;`. `1e-05` and `2.0` happen to survive, because Python's float `repr` matches.
- Reported by the T-016 tester on real files. Exponent notation is common in Foundation and ESI `fvSolution`, `physicalProperties` and `fvConstraints`, for example `limitLowPressure(min=1e4)`.

## Root cause
Numbers are converted to `int`/`float` at parse time and printed with Python's formatting. The source token is not kept.

## Scope
- Numeric parsing and printing in `foamkit/types/__init__.py` (`ofInt`/`ofFloat` and how they are created). Keep the source token. When the value has not been reassigned, `toString()` uses the token; otherwise it uses today's formatting.
- Arithmetic and comparison on `.value` behave exactly as today.

## Out of scope
- How edited values are formatted
- Other layout (T-020)

## Acceptance criteria
- [ ] **Failing test first:** `5e-4`, `1E-5`, `1e+05`, `.5`, `5.`, `-0.0`, `1.50` and `00012` each round-trip unchanged. Record any form OpenFOAM does not accept and drop it.
- [ ] `.value` returns the same Python number as today for each form (an existing-behaviour test).
- [ ] Assigning a new value writes it with today's formatting.
- [ ] All existing golden files are unchanged, unless a golden currently records a reformatted number. If so, the diff is limited to those numbers now matching the fixture source, and is reviewed.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Cache:** the JSON cache (`case.save`/`fkf.load`) must keep the token, or document that a cache round trip normalizes numbers.

## Ranking rationale
Low-medium: the value is not changed, only its formatting. It belongs with the "write it back the way it was" work (T-019, T-020).
