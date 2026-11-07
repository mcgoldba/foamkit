# T-070: CI tests the oldest and newest supported Python on Linux and Windows

- **Issue:** [#90](https://github.com/mcgoldba/foamkit/issues/90)
- **Type:** CI (owner: `implementer`; `tester` only if a 3.15 failure needs a characterization test)
- **Size:** S
- **Track:** infrastructure
- **Approved in principle:** maintainer, 2026-11-07 (design below)

## Goal
Users on any Python from 3.9 to 3.15, on Linux or Windows, get a FoamKit that CI has tested on their end of the supported range, and CI keeps following new Ubuntu releases without dropping 3.9.

## Today (planner, 2026-11-07)
- `.github/workflows/release.yml` `test` job: `os: [ubuntu-24.04, windows-latest]` x `python-version: ['3.9', '3.12']`. `ubuntu-24.04` was pinned in PR #78 because `ubuntu-latest` moved to Ubuntu 26.04, where `actions/setup-python` has no 3.9.
- `actions/setup-python` manifest (checked 2026-11-07): Ubuntu 24.04 has 3.9-3.15 (+3.16 pre-release); Ubuntu 26.04 has 3.10-3.15 (+3.16 pre-release).
- Required checks on `main` today: `Test (Python 3.9, windows-latest)`, `Test (Python 3.12, windows-latest)`, `Test (Python 3.9, ubuntu-24.04)`, `Test (Python 3.12, ubuntu-24.04)`, `ruff + mypy (no new findings)`.
- `pyproject.toml` has only the generic `Programming Language :: Python :: 3` classifier, no per-version classifiers.

## Scope
- `.github/workflows/release.yml`: replace the cross product with an explicit `include:` list:

  | Python | OS | Required |
  |---|---|---|
  | 3.9 | `ubuntu-24.04` | yes (oldest supported Python on the newest Ubuntu that has it) |
  | 3.12 | `ubuntu-latest` | yes |
  | 3.15 | `ubuntu-latest` | yes |
  | 3.9 | `windows-latest` | yes |
  | 3.15 | `windows-latest` | yes |
  | 3.16 | `ubuntu-latest` | no: `allow-prereleases: true`, `continue-on-error: true` |

  Job names keep the pattern `Test (Python X, OS)`. `fail-fast: false` stays. `publish` still needs `test`; a failing pre-release job must not block publishing.
- `CLAUDE.md`: the `CI:` line describes the new matrix (the `Python 3.9+ ... matches the CI matrix` line stays true).
- Fixes for anything that fails on 3.15, if small; otherwise a new ticket per failure (see acceptance).

## Out of scope
- Changing the minimum Python version. The policy is decided (maintainer, 2026-11-07; recorded in ROADMAP Decisions): 3.9 stays. The oldest version is dropped only when it blocks a dependency or a language feature FoamKit needs, or when no supported CI runner can install it. Dropping it takes one minor release of notice: a warning when running on that version, plus a CHANGELOG note. A version that a supported RHEL release still ships with full-life support is not dropped, unless conda or uv covers those users and the docs say so. Python 3.9 has full-life support for the whole RHEL 9 life cycle (Red Hat Application Streams life cycle); CPython 3.9 itself reached end of life on 2025-10-31.
- Adding per-version classifiers to `pyproject.toml` (the project does not use them today).
- `ci.yml` (ruff + mypy on 3.12, ratchet baseline) and the `build` job's Python.
- Making the 3.16 pre-release job a required check.

## Acceptance criteria
- [ ] `release.yml` uses an explicit `include:` list matching the table above; the only other change is the `All tests passed` summary job (below).
- [ ] Every required job passes. Any 3.15 failure is fixed in this PR (with `FoamKitError` messages and behaviour unchanged) or, if larger than S, filed as a new ticket and the coordinator asks the maintainer before merging. No test is skipped, `xfail`ed or marked to get green.
- [ ] New `DeprecationWarning`s seen on 3.15 are listed in the PR body (fixed or ticketed), not filtered.
- [ ] The 3.16 job runs with `allow-prereleases: true` and `continue-on-error: true`; its failure leaves the workflow green.
- [ ] Classifiers: unchanged, since `pyproject.toml` has no per-version classifiers (re-check at implementation time; if any were added since 2026-11-07, they list each tested version: 3.9, 3.12 and 3.15).
- [ ] `CLAUDE.md` `CI:` line updated, e.g. "`release.yml` runs `pytest` on Python 3.9 (`ubuntu-24.04`), 3.12 and 3.15 (`ubuntu-latest`), 3.9 and 3.15 (`windows-latest`), plus a non-required 3.16 pre-release job."
- [ ] `ci.yml` and its ruff/mypy baselines are untouched and the `ruff + mypy (no new findings)` check passes.
- [ ] **Amended (maintainer, 2026-11-07, PR #95):** a summary job `All tests passed` (`needs: [test]`, `if: always()`) fails unless `needs.test.result` is `success`, so a failed, cancelled or skipped required test job fails it, and the 3.16 pre-release job does not. Branch protection on `main` is updated by the coordinator, with maintainer approval, to exactly these required checks:
  - `All tests passed`
  - `ruff + mypy (no new findings)`

  Removed: every `Test (Python X, OS)` check. Later matrix changes then need no settings change. (The original plan listed the five required `Test (…)` jobs, which would have needed a settings edit on every matrix change.)
- [ ] A `ci:` PR title, e.g. `ci: test Python 3.9, 3.12 and 3.15 on Linux and 3.9 and 3.15 on Windows (T-070)`.

## Risks
- **Required-check rename blocks PRs:** this PR never reports the two removed names, and other open PRs never report the new ones until they rebase. Order: wait until the new jobs are green on this PR, then the maintainer updates protection and merges; open PRs then rebase on `main`. Land it when no other PR is close to merging.
- **Newer Python:** 3.15 may remove modules or APIs, change behaviour or emit new `DeprecationWarning`s (in FoamKit or in dependencies: numpy, pandas, matplotlib, pint, rich, ipython). A dependency without 3.15 wheels on Windows can fail the install; that is a ticket or a maintainer question, not a reason to drop the job silently.
- **`ubuntu-latest` can move again:** a future Ubuntu may drop 3.12, which would fail that job loudly (wanted). 3.9 stays on the pinned `ubuntu-24.04` until that runner image is retired; then the minimum-version policy above applies ("no supported CI runner can install it").
- No user-visible API or behaviour change.
