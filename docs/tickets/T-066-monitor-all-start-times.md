# T-066: Function-object monitors of restarted runs: `startTime='all'` reads every start time

- **Issue:** [#86](https://github.com/mcgoldba/foamkit/issues/86)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Track:** runtime (run, monitor, results)
- **Depends on:** T-063 (time-name helper), T-011 (real `postProcessing` fixtures)
- **Blocked by:** real restarted-run output (see "Questions for the maintainer" in `ROADMAP.md`)
- **Decision needed at approval:** how overlapping times are handled (options below).

## Goal
For a run that was restarted, `fkf.getMonitor(name, startTime='all')` returns the monitor data from every `postProcessing/<name>/<startTime>/` directory, and asking for a monitor that does not exist raises `FoamKitError` listing the monitors that do.

## Today (planner, 2026-11-06)
- `foamkit/functions/getMonitor.py:42-47`: `'all'` is documented as "collects data from all start times" but is treated as `'latestTime'`, so only the last restart's data comes back (**silent data loss**).
- A missing `postProcessing/<name>` gives a bare `FileNotFoundError` from `foamkit/functions/_paths.py:12`. `fkf.monitor` and `fk plot` use that exception for control flow (`foamkit/functions/monitor.py:34-38`, `foamkit/commandline/__init__.py:202-206`).
- A start-time directory with several files picks the last name with a `WARNING` (`foamkit/functions/getMonitor.py:54-59`).

## Overlapping times (maintainer picks one at approval)
When a run restarts from time 500 after the first run wrote up to 600, both directories hold rows for 500-600.
- **Option A:** rows from the later start time replace the earlier ones; one `WARNING` gives the number of replaced rows.
- **Option B:** keep every row; the result has a `startTime` column so the user can choose.

## Scope
- `foamkit/functions/getMonitor.py` (and the monitor object's `update()` for the latest start time only).
- A missing monitor raises `FoamKitError` naming `postProcessing/<name>` and listing the names present; `fkf.monitor` and `fk plot` catch `FoamKitError` (not `FileNotFoundError`) to fall back to probes, and if both fail they raise one error naming both paths.
- Several data files in one start-time directory with no `dataFileName`: `FoamKitError` listing the files (instead of picking the last).

## Out of scope
- Probes from several start times (`getProbe`): a follow-up if the same need appears there
- Distribution-specific monitor names (T-011)

## Acceptance criteria
- [ ] Fixture: real output of a run restarted once (two start-time directories), trimmed, source recorded.
- [ ] Failing tests first: `'all'` returns rows from both directories in time order, with the overlap handled per the chosen option; `'latestTime'` and an explicit time are unchanged.
- [ ] A missing monitor and an ambiguous data file each raise `FoamKitError` with the paths named.
- [ ] Existing `tests/test_monitor.py` passes unchanged.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. A `fix:` commit.

## Risks
- **Behaviour change:** directories with several data files (for example force and moment files from one function object) now need `dataFileName`. That replaces a guess with an error, as the project rules require.
