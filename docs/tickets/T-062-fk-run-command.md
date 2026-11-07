# T-062: `fk run` starts a case from the command line

- **Issue:** [#82](https://github.com/mcgoldba/foamkit/issues/82)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Track:** runtime (run, monitor, results)
- **Depends on:** T-060, T-061, T-023 (#32, clean CLI errors)

## Goal
`fk run` starts a case's `Allrun` (or, with `-solver`, its solver, optionally `-np N`), prints the log path, waits, and exits with the run's exit code; Ctrl-C stops the run cleanly.

## Scope
- `foamkit/commandline/__init__.py` and `foamkit/__main__.py` (`COMMANDS`): a `run` subcommand with `-path`, `-solver`, `-np N`, `-decompose`, `-overwrite`, using `case.run()` / `case.runSolver()` from T-060/T-061.
- Prints one line with the log path at start; on exit prints the exit code.
- Ctrl-C calls `stop()` on the run and exits 130.
- Every user error (not a case, log exists, application or `mpirun` missing, run failed) prints one `ERROR:` line and exits non-zero, with no traceback (maintainer principle, 2026-10-20).

## Out of scope
- Live plotting while running (`fk monitor` already does this from a second terminal)
- Detaching (background) runs

## Acceptance criteria
- [ ] Failing tests first in `tests/test_cli.py` style, with stub scripts on `PATH`: success exits 0 and prints the log path; a failing stub exits non-zero with one `ERROR:` line; a non-case path, an existing log and a missing application each give one `ERROR:` line and no traceback.
- [ ] Interrupting the command (simulated `KeyboardInterrupt`) stops the stub and exits 130.
- [ ] `fk --help` lists `run`.
- [ ] `pytest -q` passes on Linux and Windows CI. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. A `feat:` commit.

## Risks
- The CLI uses single-dash long options (`-path`); keep that style for consistency.
