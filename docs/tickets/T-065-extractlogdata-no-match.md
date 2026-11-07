# T-065: `fkf.extractLogData` says which log has no match instead of crashing or returning nothing

- **Issue:** [#85](https://github.com/mcgoldba/foamkit/issues/85)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Track:** runtime (run, monitor, results)

## Goal
When a log does not contain the requested pattern, or the named log does not exist, `fkf.extractLogData` raises `FoamKitError` naming the log file and the pattern, instead of an `AttributeError` or an empty list.

## Today (planner, 2026-11-06, reproduced on a copy of `tests/fixtures/pitzDaily`)
- A log without a match: `foamkit/functions/extractLogData.py:75-76` calls `.group(1)` on `None`, so `extractLogData('log.x', 'cells: {}', path=case)` raises `AttributeError: 'NoneType' object has no attribute 'group'`.
- A log that does not exist: `foamkit/functions/extractLogData.py:55` skips the case, so `extractLogData('nolog', 'x {}', path=case)` returns `[]` and the caller cannot tell "no such log" from "no cases" (**silent skip**).

## Scope
- `foamkit/functions/extractLogData.py` only.
- No match: `FoamKitError` with the log path and the search pattern.
- Missing log in a case that `listCases` found: `FoamKitError` naming the case and log, unless the new keyword `missing="skip"` is passed, which keeps today's skip and logs one `WARNING` per skipped case. The default is the error (errors never pass silently).

## Out of scope
- Reading residuals from logs (T-064)

## Acceptance criteria
- [ ] Failing tests first for both rows above.
- [ ] The error messages contain the log path and the pattern; no traceback through the CLI.
- [ ] `missing="skip"` returns the matches from the cases that have the log and warns once per skipped case.
- [ ] Existing `test_extractLogData_with_labels` still passes.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. A `fix:` commit whose body names the new default.

## Risks
- **Behaviour change:** scripts that called `extractLogData` over a directory where some cases have no log now get an error; the fix is `missing="skip"`. Say so in the commit body.
