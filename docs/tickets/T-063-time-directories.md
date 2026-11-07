# T-063: Latest time and time-directory listing handle non-integer times (`0.5`, `1e-05`)

- **Issue:** [#83](https://github.com/mcgoldba/foamkit/issues/83)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Track:** runtime (run, monitor, results)

## Goal
`fkf.getLatestTime`, `fkf.isDecomposed` and a new `fkf.timeDirs` return the right times for any case, including non-integer time directories, so results are read from the time the solver actually wrote last.

## Today (planner, 2026-11-06, reproduced on a copy of `tests/fixtures/pitzDaily` with extra directories `0.5` and `1e-05`)
- `foamkit/functions/getLatestTime.py:47-51` keeps only names where `str.isdigit()` is true, so `0.5` and `1e-05` are ignored: `getLatestTime(case)` returns `('0', 'reconstructed')` (**silently wrong**).
- With `processor0/0.25` added it returns `('0.25', 'decomposed')`, although `0.5` is newer, and `fkf.isDecomposed(case)` returns `False` for the same case, contradicting it.
- `foamkit/functions/_paths.py:5-18` (`latestTimeName`, used for `postProcessing/<name>/<startTime>`) accepts any `float()`-parsable name, including `nan`, `inf` and `1_0`.

## Scope
- One shared helper in `foamkit/functions/_paths.py` that decides whether a directory name is an OpenFOAM time (decimal or exponent number, optionally signed; not `nan`/`inf`/underscores) and sorts by numeric value.
- `getLatestTime`, `isDecomposed`/`isReconstructed` and `latestTimeName` use it.
- New `fkf.timeDirs(path=None, processor=False) -> list[str]`: the time directory names of a case in numeric order (reconstructed, or `processor0` when `processor=True`), names exactly as on disk.

## Out of scope
- Reading field values from a time directory (T-068)
- Changing how `CaseParser` loads time directories into the case object

## Acceptance criteria
- [ ] Failing tests first, on a copy of `tests/fixtures/pitzDaily` with directories created in `tmp_path`: `0`, `0.5`, `1e-05`, `100`, `constant`, `nan`, `1_0`, and a `processor0` with its own times.
- [ ] `getLatestTime` returns `'100'` for the reconstructed set and the right `caseType` when `processor0` has a later or earlier time; `isDecomposed` agrees with it in every case tested.
- [ ] `timeDirs` returns `['0', '1e-05', '0.5', '100']` (numeric order, original names) and ignores `constant`, `nan`, `1_0`.
- [ ] Existing `test_isDecomposed_isReconstructed` still passes.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. A `fix:` commit whose body describes the corrected latest time.

## Risks
- **Behaviour change:** callers that got `'0'` for cases with only non-integer times now get the real latest time. This is a bug fix.
- Two names with the same value (`1` and `1.0`) are possible on disk; `timeDirs` keeps both and `getLatestTime` raises `FoamKitError` naming them rather than picking one.
