# T-059: A failed `Allrun` raises `FoamKitError` instead of passing silently

- **Issue:** [#79](https://github.com/mcgoldba/foamkit/issues/79)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Track:** runtime (run, monitor, results)
- **Related:** T-060 (non-blocking `case.run()`), T-003 (#10, README `case.run()` example)

## Goal
When a case's run script fails, is missing or cannot be executed, `case.allRun()` and `fkf.allRun()` raise `FoamKitError` naming the script, the case and the exit code, instead of logging and returning normally.

## Today (planner, 2026-11-06, read on `t-052-entry-value-of-several-lists` at 9d2094e)
- `foamkit/types/__init__.py:979-986`: `subprocess.CalledProcessError` is caught and only logged; `allRun` returns `None`, so a failed run looks like a successful one. `ofStudy.run` (`foamkit/types/__init__.py:4063`) then carries on with the next sample.
- A missing or non-executable script raises a bare `FileNotFoundError` / `PermissionError` (or `OSError` on Windows) with a traceback.
- The child runs in the Python process's working directory, not the case directory (no `cwd=`), so scripts that do not `cd` to their own directory run against the wrong case.
- `foamkit/functions/allRun.py:15` calls `CaseParser(runDir).initOFCase()` (defined at `foamkit/types/__init__.py:1081`), so `fkf.allRun()` reaches the script and has the same silent-failure bug. Checked by the coordinator on Windows (2026-11-06): with a POSIX stub `Allrun` that exits 3, `fkf.allRun` raised a bare `OSError: [WinError 193]`.

## Scope
- `ofCase.allRun` in `foamkit/types/__init__.py` and `foamkit/functions/allRun.py`.
- Run the script with `cwd` set to the case directory; argv list, never `shell=True`.
- On a non-zero exit, raise `FoamKitError` with the case path, the script, the exit code and the last 20 lines of the captured output (stdout and stderr).
- Missing script, non-executable script, or a script that the platform cannot run (a POSIX script on Windows) raise `FoamKitError` naming the path; no traceback through the `fk` CLI.

## Out of scope
- Non-blocking runs, solver-direct runs, stopping and parallel runs (T-060, T-061)
- Changing `ofStudy` beyond what follows from the raise (it now stops at the first failed sample)

## Acceptance criteria
- [ ] Failing tests first, with no OpenFOAM: a stub `Allrun` (a small Python or shell script created in `tmp_path`; shell-based tests skipped on Windows) that exits 0, exits 3, is missing, and is not executable.
- [ ] Exit 3 raises `FoamKitError` whose message contains the case path, `Allrun`, `3` and the stub's last output line.
- [ ] Missing and non-executable scripts raise `FoamKitError` naming the path.
- [ ] The stub sees the case directory as its working directory.
- [ ] `fkf.allRun(path)` behaves like `case.allRun()` for every stub above.
- [ ] `ofStudy.run` with a failing sample raises `FoamKitError` naming the sample.
- [ ] The existing `test_allRun_with_large_output_does_not_deadlock` still passes.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. A `fix:` commit whose body describes the behaviour change.

## Risks
- **Behaviour change:** scripts that relied on a failed run returning normally (for example an `ofStudy` that should continue past failures) now stop. That was silent failure, so this is a bug fix; say so in the commit body.
- Windows cannot run POSIX `Allrun` scripts; the error must say so rather than fail with `WinError 193`.
