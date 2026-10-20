# T-011: Residuals/`solverInfo` and monitor parsing across distributions

- **Issue:** [#18](https://github.com/mcgoldba/foamkit/issues/18)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-007, T-010 (uses its `residuals` ↔ `solverInfo` table row)

## Goal
`fk plot` and `fkf.getMonitor` read residuals and probe data written by both tested ESI and Foundation releases.

## Scope
- `foamkit/commandline/__init__.py:193` (the `residuals` default)
- `foamkit/functions/getMonitor.py:47-48`
- `foamkit/functions/getProbe.py:42-43`
- Column-header parsing at `foamkit/types/__init__.py:3160-3175`
- Fixture `postProcessing` data from one ESI (v2606) and one Foundation (14) run (real output, trimmed)

## Out of scope
- New plot features

## Acceptance criteria
- [ ] Both fixture `postProcessing/` trees parse into monitors with the correct column names and row counts.
- [ ] Asking for `residuals` on an ESI case resolves through the T-010 table to `solverInfo` when `residuals` is missing. Explicit names keep today's behaviour. The directory used is logged at INFO level.
- [ ] Existing `tests/test_monitor.py` passes unchanged.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- Real `postProcessing` output needs a run, so the fixture source must be recorded. If none is available, keep the ticket blocked rather than inventing files.
