# T-064: Read residuals, Courant numbers and run status from a solver log, live

- **Issue:** [#84](https://github.com/mcgoldba/foamkit/issues/84)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M (if the tester finds more than two log dialects, split: T-064a residuals and status, T-064b Courant and timing)
- **Track:** runtime (run, monitor, results)
- **Blocked by:** real solver logs (see "Questions for the maintainer" in `ROADMAP.md`)
- **Related:** T-060 (`ofRun.logPath`), T-011 (residuals from `postProcessing`)

## Goal
A user reads a solver log (`log.foamRun`, `log.simpleFoam`, …) into a table of per-time-step residuals, iterations, Courant numbers and timing, refreshes it while the run is writing without re-reading the file, and can tell whether the run finished, is still going, or stopped with an OpenFOAM error.

## Today (planner, 2026-11-06)
FoamKit reads residuals only from `postProcessing` function-object files (`foamkit/functions/getMonitor.py`). A run without the `residuals`/`solverInfo` function object cannot be followed at all. `fkf.extractLogData` (`foamkit/functions/extractLogData.py:9-84`) returns one regex match per log and is not a residual reader.

## Public names (approved with this ticket)
- `fkf.readLog(path) -> fkt.ofLog`
- `ofLog.data`: `pandas.DataFrame` indexed by `Time`, columns such as `Ux initial`, `Ux final`, `Ux iterations`, `p initial`, …, `Courant mean`, `Courant max`, `deltaT`, `ExecutionTime`, `ClockTime` (only the columns present in the log).
- `ofLog.update()`: parses only lines appended since the last read; a partly written last line is left for the next call (same contract as the monitor `update()` in `tests/test_monitor.py`).
- `ofLog.status`: `"running"`, `"finished"` (the log ends with OpenFOAM's `End` line) or `"failed"` (a `FOAM FATAL ERROR` / `FOAM FATAL IO ERROR` block); `ofLog.error`: that block's text, else `None`.

## Scope
- New reader in `foamkit/types/__init__.py` (or a new module under `foamkit/`), exported as above.
- Solver-performance lines (`<solver>:  Solving for <field>, Initial residual = …, Final residual = …, No Iterations …`), `Courant Number mean: … max: …`, `deltaT = …`, `ExecutionTime = … s  ClockTime = … s`, `Time = …`.
- Multiple solves of one field per time step (PISO/PIMPLE correctors): the first initial residual and the last final residual are kept, and the iteration counts are summed. This is recorded in the docstring.
- A line that starts like a solver-performance or Courant line but cannot be parsed raises `FoamKitError` with the file and line; nothing is skipped silently.

## Out of scope
- Plotting and the CLI (`fk monitor` reading logs can be a follow-up once this API is stable)
- Function-object output (T-011, T-066)
- Parallel log merging (OpenFOAM writes one log for a parallel run, so none is needed)

## Acceptance criteria
- [ ] Fixtures: real, trimmed logs (source release, tutorial, command and date recorded in a README next to them) from at least Foundation 14 (`foamRun`, steady and one transient tutorial with Courant lines) and ESI v2606 (`simpleFoam` and `pimpleFoam`); one log cut mid-line; one log ending in a `FOAM FATAL ERROR`.
- [ ] Failing tests first: column names, row counts and a few spot values per fixture.
- [ ] `update()` after appending the rest of a cut log gives the same `data` as reading the full log in one go; the cut line is not lost or duplicated.
- [ ] `status` and `error` are right for finished, cut and failed logs.
- [ ] A corrupted solver-performance line raises `FoamKitError` naming the file and line.
- [ ] Tests need no OpenFOAM. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. A `feat:` commit.

## Risks
- Log formats differ between Foundation and ESI and between releases; only formats seen in the real fixtures are supported, and anything else that looks like a residual line raises.
- Large logs: parse line by line, never `read_text()` of the whole file on `update()`.
