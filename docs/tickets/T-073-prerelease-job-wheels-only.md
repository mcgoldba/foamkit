# T-073: the pre-release Python job fails fast when a dependency has no wheel

- **Issue:** [#96](https://github.com/mcgoldba/foamkit/issues/96)
- **Type:** CI (owner: `implementer`)
- **Size:** S
- **Track:** infrastructure
- **Depends on:** T-070 (merged, f92f94e, PR #95)

## Goal
Every PR gets its `All tests passed` result within a few minutes, because the non-required Python pre-release job fails quickly, naming the missing wheel, instead of building dependencies from source for ~15 min.

## Today (planner, 2026-11-07)
- CI run 42403288874 on PR #95 (job 128495505883): `Test (Python 3.16, ubuntu-latest)` ran 18:50:45 → 19:06:02 (~15 min) and failed. The time went into `pip install -e ".[test]"`: retries on read timeouts, then source builds of matplotlib, contourpy, kiwisolver, numpy, pillow and pandas; pillow's build failed ("Failed to build pillow"), so no test ran.
- The required test jobs in the same run took 1.4-3.3 min. `All tests passed` (`needs: [test]`) waits for every matrix entry, the pre-release one included, so every PR waits ~15 min for it.
- The maintainer commented on PR #95 that the 3.16 failures are fine, since 3.16 is a future release.

## Scope
- `.github/workflows/release.yml`, `test` job only:
  - The existing step `Install package and test dependencies` gets `if: matrix.prerelease != true`; its `run:` line stays exactly as it is.
  - A new step, `if: matrix.prerelease == true`, runs
    `python -m pip install --only-binary=:all: --no-binary=foamkit -e ".[test]"`.
- **Approach and why:** `--only-binary=:all:` makes pip refuse every sdist, so a dependency with no wheel for 3.16 fails at resolve time ("Could not find a version that satisfies the requirement pillow… (from versions: none)") instead of being built. `--no-binary=foamkit` takes FoamKit back out of that rule: pip lets a later `--no-binary` for a name override `:all:`. Then the editable install of the checkout is never refused, whether or not this pip version applies format control to local directories. Its build backend still comes from wheels (setuptools has them). A separate step, rather than a matrix variable spliced into one command, keeps the required jobs' command byte-for-byte unchanged. The implementer checks this locally with the pinned pip before pushing (e.g. on 3.12 the command must install and the tests must run), and records the pip version in the PR body.

## Out of scope
- Caching pip or wheels.
- Making the 3.16 job required, or changing the matrix, `continue-on-error`, or `All tests passed`.
- `ci.yml`, `release-window.yml`, the `build` and `publish` jobs.

## Acceptance criteria
- [ ] For every required matrix entry the install step's `run:` text is byte-for-byte unchanged (check with `git diff`); only an `if:` is added to that step.
- [ ] The pre-release entry installs dependencies from wheels only, and FoamKit itself from the checkout (editable).
- [ ] When a dependency lacks a 3.16 wheel, the job fails and its log names the package (pip's own error is enough if it does).
- [ ] When every wheel exists, the job runs `python -m pytest` as now.
- [ ] The 3.16 job's failure stays non-blocking: the workflow and `All tests passed` stay green.
- [ ] PR body: the measured duration of the 3.16 job and of `All tests passed` on the PR (it no longer waits ~15 min; the target is under ~5 min).
- [ ] Required checks (`All tests passed`, `ruff + mypy (no new findings)`) pass; job names unchanged; a `ci:` PR title, e.g. `ci: install only wheels in the pre-release Python job (T-073)`.

## Risks
- **Backtracking:** with source builds refused, pip may fall back to older releases that ship an `abi3` or pure-Python wheel. That is fine if the tests then run. If resolving itself becomes slow, report it in the PR rather than adding flags.
- **Index timeouts** were part of the 15 min. If they recur, a job-level `timeout-minutes` for the pre-release entry only is a possible follow-up. It is not added here, so the required jobs' settings stay untouched.
- Once 3.16 wheels exist for every dependency, the job runs the tests as before; nothing needs reverting.
- No user-visible change.
