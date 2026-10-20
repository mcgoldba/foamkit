# T-002: Make the CLAUDE.md lint and type checks runnable (ruff + mypy baseline)

- **Issue:** [#9](https://github.com/mcgoldba/foamkit/issues/9)
- **Type:** code (config only; owner: `implementer`; no tester step, because there is no behaviour to test)
- **Size:** S

## Goal
A contributor can run the CLAUDE.md commands `ruff check . && ruff format --check .` and `mypy foamkit/` in the dev environment. Today's findings are recorded as a baseline, so every later ticket can honestly check "no new findings".

## Scope
- `environment.yml`: add `ruff` and `mypy` (conda-forge).
- `pyproject.toml`:
  - add a `dev` (or `lint`) optional extra with `ruff` and `mypy`;
  - add `[tool.ruff]` with `target-version = "py39"` and a minimal rule set (ruff defaults);
  - add `[tool.mypy]` with `python_version = "3.9"` and lenient settings (`ignore_missing_imports = true`), so the baseline is meaningful rather than thousands of errors.
- Record the baseline counts for `ruff check`, `ruff format --check` (number of files that would be reformatted) and `mypy foamkit/` in a short section appended to this ticket at completion.

## Out of scope
- Fixing any lint or type finding, or running `ruff format` on the code (large diff; separate decision, see ROADMAP deferred)
- Adding lint or mypy to CI (follow-up, once the baseline is zero or a baseline-diff mechanism exists)
- Pre-commit hooks

## Acceptance criteria
- [ ] After a fresh `mamba env create -f environment.yml`, `ruff --version` and `mypy --version` work.
- [ ] `ruff check .`, `ruff format --check .` and `mypy foamkit/` all run to completion without a config or usage error. A non-zero exit caused by findings is expected.
- [ ] The baseline numbers are recorded in this ticket.
- [ ] `git diff --stat -- foamkit/ tests/` is empty.
- [ ] `pytest -q` still passes (99 passed, 1 skipped).

## Risks
- Newer ruff and mypy releases may drop support for targeting `py39`. Pin a minimum version and check that the tools still accept a 3.9 target.
- A strict mypy config would produce a meaningless baseline. Keep the config lenient and tighten it in later tickets.

## Baseline (recorded at completion)
Tools: ruff 0.17.1, mypy 1.20.2 (what a fresh solve of `>=1.19,<1.21` picks; installed into the existing foamkit env, Python 3.12, not a fresh `env create`). The same mypy result (127 errors in 3 files) was re-verified with mypy 1.19.1 in a Python 3.9 env.

| Command | Exit | Baseline |
|---|---|---|
| `ruff check .` | 1 | 195 findings (rules E4, E7, E9, F), 49 auto-fixable, 28 more with unsafe fixes |
| `ruff format --check .` | 1 | 55 files would be reformatted, 1 already formatted (Markdown excluded) |
| `mypy foamkit/` | 1 | 127 errors in 3 files (48 source files checked) |

Notes:
- ruff is pinned `>=0.17.1,<0.18` and the rule set is fixed explicitly (`select = ["E4", "E7", "E9", "F"]`) so the count does not drift with ruff releases. `*.md` is excluded via `extend-exclude`.
- mypy is pinned `>=1.19,<1.21`: mypy 2.x rejects `python_version = "3.9"` ("Python 3.9 is not supported (must be 3.10 or higher)"). ruff 0.17.1 still accepts `target-version = "py39"`.
- mypy uses `follow_imports = "skip"` plus `follow_imports_for_stubs = true` only for overrides on the runtime dependencies (numpy, pandas, matplotlib, pint, rich, IPython). In a Python 3.12 env numpy's stubs use the `type` statement, which mypy cannot parse under a 3.9 target, so the run would abort. Third-party types are therefore `Any` in the baseline; the standard library is still type-checked (probe: `a: int = os.getcwd()` is flagged). Revisit when the target is raised.
- `shim/` is linted and formatted under the root config.
- The types command `mypy foamkit/` matches CLAUDE.md (the package lives in `foamkit/`; there is no `src/` dir).
- `pytest -q`: 99 passed, 1 skipped.
