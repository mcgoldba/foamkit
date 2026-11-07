# T-061: Run the solver in parallel: `case.runSolver(np=N)`

- **Issue:** [#81](https://github.com/mcgoldba/foamkit/issues/81)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Track:** runtime (run, monitor, results)
- **Depends on:** T-060

## Goal
A user runs a decomposed case in parallel from Python with `case.runSolver(np=4)`, and a case that is not decomposed to match raises `FoamKitError` instead of starting a run that fails later.

## Today (planner, 2026-11-06)
FoamKit has no parallel run support. `fkf.isDecomposed` (`foamkit/functions/isDecomposed.py:5-22`) only compares time directories; nothing checks `numberOfSubdomains`.

## Scope
- `case.runSolver(np: int | None = None, decompose: bool = False, overwrite=False)` in `foamkit/types/__init__.py`:
  - `np` set: runs `mpirun -np <np> <application> -parallel` (argv list) in the case, logging to `log.<application>`; returns the T-060 `ofRun` handle.
  - Before starting, check that `system/decomposeParDict` exists, its `numberOfSubdomains` equals `np`, and `processor0` … `processor<np-1>` exist. Any mismatch raises `FoamKitError` naming the file and both numbers.
  - `decompose=True`: runs `decomposePar` first (blocking, `log.decomposePar`, loud on failure), then the solver.
  - `mpirun` not on `PATH` raises `FoamKitError`.

## Out of scope
- `reconstructPar`, scheduler submission, host files and MPI options (pass-through of extra `mpirun` arguments can be a later ticket if asked for)
- Choosing `np` automatically

## Acceptance criteria
- [ ] Failing tests first, with no OpenFOAM or MPI: a stub `mpirun` and stub application on `PATH` (Python scripts) that record their argv.
- [ ] `runSolver(np=2)` on a case with `numberOfSubdomains 2;` and `processor0/1` calls `mpirun -np 2 <application> -parallel` with `cwd` at the case.
- [ ] Mismatched `numberOfSubdomains`, a missing processor directory, a missing `decomposeParDict` and a missing `mpirun` each raise `FoamKitError` with the file or command named; no process is started.
- [ ] `decompose=True` runs the `decomposePar` stub first and stops with `FoamKitError` if it fails.
- [ ] `pytest -q` passes on Linux and Windows CI. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. A `feat:` commit.

## Risks
- `numberOfSubdomains` may be written with a `$` reference or `#calc`; if FoamKit cannot resolve it to an integer, raise `FoamKitError` rather than guess.
- MPI launchers differ (`mpirun`, `mpiexec`); only `mpirun` is supported here, and the error says so.
