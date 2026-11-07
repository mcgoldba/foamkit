# T-011: Residuals/`solverInfo` and monitor parsing across distributions

- **Issue:** [#18](https://github.com/mcgoldba/foamkit/issues/18)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Track:** runtime (run, monitor, results)
- **Depends on:** nothing in code. **Blocked by** real `postProcessing` output (see "Questions for the maintainer" in `ROADMAP.md`).
- **Rescoped (2026-11-06):** no longer waits for T-007 and T-010. The `residuals` → `solverInfo` fallback lives in the monitor code for now; T-010 moves it into its name table when it lands. Text columns (solver names, convergence flags) added to the scope.

## Goal
`fk plot`, `fk monitor` and `fkf.getMonitor` read residuals and probe data written by both tested ESI and Foundation releases, with the right column names and without dropping or mangling any column.

## Today (planner, 2026-11-06)
- `fk plot` and `fk monitor` default to `residuals` (`foamkit/commandline/__init__.py:192-194`, `:216`); ESI writes the equivalent function object as `solverInfo`.
- Layout assumptions: `postProcessing/<name>/<startTime>/<file>` and tab-separated column headers (`foamkit/functions/getMonitor.py:45-63`, `foamkit/functions/getProbe.py:40-44`, `foamkit/types/__init__.py:3669`).
- If a file has no column-header line, `MonitorParser.makeOFMonitor` fails with an unbound `header` (`foamkit/types/__init__.py:3669-3675`).
- Rows with fewer values than columns are dropped with a `WARNING` (`foamkit/types/__init__.py:3559`).
- Plotting converts every column with `pd.to_numeric` (`foamkit/functions/monitor.py:51`), which fails on text columns such as solver names.
- The only `postProcessing` fixture (`tests/fixtures/pitzDaily/postProcessing`, Foundation 9 banner case) has no recorded source.

## Scope
- `foamkit/commandline/__init__.py` (the `residuals` default), `foamkit/functions/getMonitor.py`, `foamkit/functions/getProbe.py`, the column-header parsing in `foamkit/types/__init__.py` (`MonitorParser`, `_ofMonitorBase._parseLine`), `foamkit/functions/monitor.py` and `plot.py` (numeric columns only).
- Fixture `postProcessing` data from one ESI (v2606) and one Foundation (14) run (real output, trimmed, source recorded). Foundation 11 and ESI v2412 are added if the maintainer supplies them, to cover the tested range.

## Out of scope
- New plot features
- Restarted runs and `startTime='all'` (T-066)
- Reading residuals from solver logs (T-064)

## Acceptance criteria
- [ ] Both fixture `postProcessing/` trees parse into monitors with the correct column names and row counts.
- [ ] Asking for `residuals` on a case that has `solverInfo` but no `residuals` resolves to `solverInfo`; explicit names keep today's behaviour. The directory used is logged at INFO.
- [ ] Text columns (solver names, `converged` flags) are kept as text in `data`; plots use numeric columns only, and a `filter` that selects only text columns raises `FoamKitError` naming them.
- [ ] A data file with no column-header line raises `FoamKitError` naming the file.
- [ ] The row-dropping `WARNING` path is characterized on the real fixtures; if a real file hits it, the ticket raises `FoamKitError` with file and line instead.
- [ ] Existing `tests/test_monitor.py` passes unchanged.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.

## Risks
- Real `postProcessing` output needs a run, so the fixture source must be recorded. If none is available, keep the ticket blocked rather than inventing files.
- When T-010 lands, the fallback moves into its table; keep it in one small function so the move is a one-line change.
