# T-023: `fk` subcommands fail cleanly on a path that is not a case (no tracebacks)

- **Issue:** [#32](https://github.com/mcgoldba/foamkit/issues/32)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-017 (its top-level `FoamKitError` handler in `foamkit/__main__.py`) and T-025 (`userMsg` cannot raise `MarkupError`, so `ERROR:` lines are always clean).
- **Found by:** the T-017 tester, 2026-10-20. The planner reproduced it against main on 2026-10-20.

## Maintainer principle (2026-10-20)
**User errors never show a traceback.** This covers bad arguments, running a command in an invalid directory, and a missing `fk init` cache. Each one prints one clean `ERROR:` line and exits 1. It applies to every `fk` subcommand, and to future CLI work too (recorded in ROADMAP). Tracebacks are only for real bugs.

## Goal
Running an `fk` subcommand on a folder that is not an OpenFOAM case, or that has no `fk init` cache, prints one clear `ERROR:` line and exits with status 1. No Python traceback is shown.

## Audit (reproduced 2026-10-20 on an empty folder)
Pattern: a precondition failure is reported at INFO or WARNING level (or not at all), execution continues, and a later step crashes.

| Command | Where | What happens today |
|---|---|---|
| `fk init -path <not a case>` | `ofCase.__post_init__`, `foamkit/types/__init__.py:717`: `userMsg("Specified path is not an OpenFOAM case ...")` at the default **INFO** level | It continues into `FolderParser(..., 'constant')`, which raises **`FileNotFoundError`** with a rich traceback; exit 1. |
| `fk write -path <no cache>` | `pf.load`, `foamkit/functions/load.py:71`: "No cached case data found" at **WARNING**, returns `None`; then `commandline/__init__.py` `write()` calls `case.write()` | **`AttributeError: 'NoneType' object has no attribute 'write'`** with a traceback; exit 1. |
| `fk plot U -casePath <not a case>` | `fkf.getMonitor`/`getProbe` path building (`getMonitor.py:47-48`, `getProbe.py:42-43`), with no check | **`FileNotFoundError`** for `postProcessing/U`, with a traceback; exit 1. |
| `fk monitor ... -casePath <not a case>` | `pf.monitor`; same lookup path as `plot`, from reading the code | Expected to behave like `plot`. **Not reproduced:** the CLI could not start during the audit because `__main__.py` was being edited for T-017. The tester confirms it. |
| `fk edit [-ipython False]` with no cache | `pf.load` WARNING → `case = None`; the console starts anyway (`commandline/__init__.py` `edit()`, `_iPython_env.py:9`) | No crash, but the user gets a console with `case = None`. **Decision (2026-10-20): this must become a clean `ERROR:` and exit 1. No console opens.** |
| `fk cloneCase` | `cloneCase.py:45-46` checks `isCase` with `"ERROR"` | Already clean. No change. |
| `fk restore` | not a subcommand (`COMMANDS` in `__main__.py`) | Not applicable. `fkf.restore()` is library-only. |

## Scope
- **CLI layer** (`foamkit/commandline/__init__.py`):
  - `init`: if the path is not a case (`fkf.isCase`), call `userMsg(..., "ERROR")` with the path.
  - `write`: if `pf.load` returns `None`, call `userMsg("No cached case data found ... run 'fk init' first", "ERROR")`.
  - `plot` and `monitor`: if `casePath` is not a case, or the requested `postProcessing/<name>` folder is missing, call `userMsg(..., "ERROR")` naming the missing folder.
  - `edit` with no cache (both the IPython and `-ipython False` paths): raise `FoamKitError` via `userMsg("No cached case data found ... run 'fk init' first", "ERROR")` **before** starting any console. Exit 1 with a clean `ERROR:` line. Never open a console with `case = None` (maintainer decision, 2026-10-20).
  - **Bad arguments:** check that argparse errors for each subcommand (unknown option, missing required value, `-ipython notabool`, wrong `yrange` length in `monitor`) print a usage/`ERROR` message and exit non-zero without a Python traceback. Argparse exits with status 2 by design; keep 2 for argparse usage errors, and only make sure no traceback is printed. Fix any that do show one.
- **Library layer, minimal:** `ofCase.__post_init__` (`types/__init__.py:717`).
  - When `system/` or `constant/` is missing, raise `FoamKitError` via `userMsg(..., "ERROR")` instead of letting `FileNotFoundError` escape.
  - Keep today's INFO message when only the `0`/`0.orig` folder is missing, because such cases still load today.

## Out of scope
- Changing `pf.load()` to raise instead of returning `None`. That is a public library behaviour change and would need a deprecation path; it is a separate ticket if wanted.
- The bare `except:` blocks (see the plan's Known gaps)
- New CLI features

## Acceptance criteria
- [ ] **Failing tests first** in `tests/test_cli.py` (subprocess, using T-017's pattern). For each of `fk init`, `fk write`, `fk plot`, `fk monitor`, `fk edit` and `fk edit -ipython False` on an empty temp folder, assert:
  - exit code 1;
  - stdout contains exactly one `ERROR:` line naming the path or the missing item;
  - **no `Traceback` and no rich traceback box** in stdout or stderr.
- [ ] After the fix all six pass. `fk edit` opens no console (the test must not hang: run it with a timeout and closed stdin). Commands on the valid pitzDaily fixture behave as before (the existing CLI tests are unchanged).
- [ ] `fkt.ofCase(<folder without system/>)` raises `FoamKitError` (an `Exception` after T-017), not `FileNotFoundError`. A folder with `system/` and `constant/` but no `0/` still loads.
- [ ] **Bad-argument sweep:** for every subcommand in `COMMANDS` (`init`, `edit`, `setConfig`, `write`, `plot`, `monitor`, `cloneCase`, `cloneCases`), one invalid-argument invocation exits non-zero with no Python traceback. For `monitor` this includes a wrong `yrange` length (`ERROR`, exit 1), and for `edit` `-ipython notabool`.
- [ ] `fk cloneCase <not a case> <dest>` keeps its existing clean `ERROR` (regression test).
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Scripts calling `fkt.ofCase` on partial folders:** these now get `FoamKitError` instead of `FileNotFoundError`. Code catching `FileNotFoundError` would miss it. This is unlikely; mention it in the commit body.
- **Repeated `ERROR:` lines:** if the library also prints an `ERROR:` line, the CLI must not print a second one. T-017's handler already avoids double printing.

## Ranking rationale
Right after T-016, not before it. T-025 also goes before it.
- It is user-facing and small, but every affected command already exits 1. The cost today is an ugly traceback and an unclear message, not lost data or a case that can't load.
- T-016 unblocks loading stock Foundation 14 cases, which is higher value.
- It depends on T-017's handler, so it cannot go earlier anyway.
