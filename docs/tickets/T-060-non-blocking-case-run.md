# T-060: Start a case without blocking and stop it: `case.run()`, `case.runSolver()` and a run handle

- **Issue:** [#80](https://github.com/mcgoldba/foamkit/issues/80)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M
- **Track:** runtime (run, monitor, results)
- **Depends on:** T-059 (loud `Allrun` failures)
- **Followed by:** T-061 (parallel runs), T-062 (`fk run`)

## Goal
From Python, a user starts a case's `Allrun` or its solver, gets a handle back at once, and can check whether it is still running, wait for it, and stop it; every failure raises `FoamKitError`.

## Today (planner, 2026-11-06)
- The only way to run is `ofCase.allRun` (`foamkit/types/__init__.py:967-986`), which blocks until the script ends and keeps all output in memory.
- The README advertises `case.run()` (`README.md:69`), but no `run` method is defined on the case, so the example raises `AttributeError`.
- There is no way to run the solver named in `controlDict` directly, no handle to a running process, and no way to stop it.

## Public names (approved with this ticket)
- `case.run(script="Allrun", overwrite=False) -> ofRun`: starts the script in the case directory; output goes to `log.<script>` in the case.
- `case.runSolver(overwrite=False) -> ofRun`: starts the `application` named in `system/controlDict` (on Foundation 11+ that is `foamRun`, which reads `solver` itself); output goes to `log.<application>`.
- `fkt.ofRun`: `pid`, `logPath`, `running` (bool), `returncode` (`None` while running), `wait(timeout=None)`, `stop(timeout=10)`.
- `case.allRun()` keeps working (it may become `run().wait()`).

## Scope
- `foamkit/types/__init__.py` (`ofCase`, new `ofRun`); export from `foamkit.types`.
- `subprocess.Popen` with an argv list, `cwd` set to the case, stdout and stderr redirected to the log file (no pipes, so no deadlock); never `shell=True`.
- Errors (`FoamKitError`, naming the case and file):
  - the log file already exists and `overwrite` is false (OpenFOAM's own `runApplication` refuses in the same situation);
  - the script is missing or cannot be executed on this platform;
  - the application is not on `PATH` (message suggests sourcing OpenFOAM);
  - `controlDict` has no `application`;
  - `wait()` sees a non-zero exit (message includes the exit code and the last 20 log lines).
- `stop()` asks the process to end (terminate), waits up to `timeout`, then kills it; for `Allrun`, child processes started by the script are stopped too (process group on POSIX, process tree on Windows). `returncode` reflects the stop.

## Out of scope
- Parallel runs and `decomposePar` (T-061); the CLI (T-062)
- Reading residuals from the log (T-064)
- Job schedulers (Slurm and similar) and async APIs

## Acceptance criteria
- [ ] Failing tests first, with no OpenFOAM: stub "solvers" and scripts created in `tmp_path` and put on `PATH` (Python scripts, so the tests run on Linux and Windows CI) that print lines, sleep, and exit 0 or non-zero.
- [ ] `case.run()` and `case.runSolver()` return within 1 s while the stub is still sleeping; `running` is true, then false after `wait()`.
- [ ] The log file contains the stub's stdout and stderr; it is in the case directory and named as above.
- [ ] Each error in Scope raises `FoamKitError` with the case path and the file or command; an existing log is never overwritten unless `overwrite=True`.
- [ ] `stop()` ends a stub that ignores nothing within the timeout, and a stub `Allrun` that started a child: both the script and the child are gone afterwards.
- [ ] `README.md:69` `case.run()` now works against a case with an `Allrun` (checked by a test with a stub script; the README text itself is T-003's).
- [ ] Public functions have type hints and docstrings.
- [ ] `pytest -q` passes on Linux and Windows CI. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. A `feat:` commit.

## Risks
- **Name clash:** a case sub-directory called `run` or `runSolver` would become an attribute of the same name; check `_checkReserved` covers the new methods.
- **Windows:** stock `Allrun` scripts are POSIX shell; on Windows `case.run()` raises `FoamKitError` saying so (stubs in tests are Python).
- **Orphans:** if the Python process exits, the run continues (documented); `stop()` is the only supported way to end it from FoamKit.
- Foundation 11+ `foamRun` versus ESI solver applications: only the `application` value is used, so no version branching is needed here.
