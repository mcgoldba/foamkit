# T-069: `ofStudy.run` writes into the study path, logs instead of printing, and sorts samples

- **Issue:** [#89](https://github.com/mcgoldba/foamkit/issues/89)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Track:** runtime (run, monitor, results)
- **Depends on:** T-059 (a failed sample raises)

## Goal
A parametric study run with `fkt.ofStudy(...).run()` writes its sample table into the study's `path` (not the working directory), reports progress through the `foamkit` logger, and runs samples in the order given by `sort`.

## Today (planner, 2026-11-06, `foamkit/types/__init__.py:3930-4072`)
- `run()` writes `studySamplePoints.txt` to the Python working directory (`:4015`), and the `path` field (`:3936`) is never used; cases go next to the template instead.
- Progress uses `print` (`:4017`, `:4034`, `:4059`).
- `sort=` is marked "raises a KeyError" (`:4021`); `ascending` is documented as a list but passed through as given.
- `ignoreIndices=[]` is a mutable default (`:3994`).

## Scope
- `ofStudy.run` only. The sample table is written to `self.path / "studySamplePoints.txt"`; whether cases also move to `self.path` is decided by the tester's characterization and stated in the commit body (default: unchanged, next to the template, to avoid moving existing studies).
- `print` becomes `logger.info`.
- `sort` accepts column names or positions and a bool or list of bools for `ascending`; an unknown column raises `FoamKitError` naming it.

## Out of scope
- Running samples concurrently, schedulers, or a new study API
- `ofStudy.diff` (still unimplemented; a separate ticket if wanted)

## Acceptance criteria
- [ ] Failing tests first with `dryRun=True` on a copy of `tests/fixtures/pitzDaily` as the template: the sample table lands in `path`, not the working directory; `sort=['a']` and `sort=[0]` run in the expected order; an unknown sort column raises `FoamKitError`.
- [ ] No `print` output from `run()`; the same messages appear in the `foamkit` log at INFO.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. A `fix:` commit.

## Risks
- **Behaviour change:** scripts that read `studySamplePoints.txt` from the working directory must read it from the study path. Say so in the commit body.
