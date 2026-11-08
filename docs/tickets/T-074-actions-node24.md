# T-074: move GitHub Actions off Node.js 20

- **Issue:** [#97](https://github.com/mcgoldba/foamkit/issues/97)
- **Type:** CI (owner: `implementer`)
- **Size:** S
- **Track:** infrastructure

## Goal
CI runs only actions built for Node.js 24, so the job logs carry no Node.js 20 deprecation warning and CI keeps working when GitHub removes Node 20.

## Today (planner, 2026-11-07)
- Every job log on PR #95 ends with: "Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/checkout@v4, actions/setup-python@v5." This was already there before T-070.
- `uses:` in the three workflows, with the latest release found via `gh api repos/<owner>/<repo>/releases/latest` and `runs.using` from each tag's `action.yml`:

  | Action | Used in | Pinned | Runtime | Latest (date) | Runtime |
  |---|---|---|---|---|---|
  | `actions/checkout` | `release.yml` (test, build), `ci.yml`, `release-window.yml` | `@v4` | node20 | v7.0.1 (2026-07-20) | node24 |
  | `actions/setup-python` | `release.yml` (test, build), `ci.yml` | `@v5` | node20 | v7.1.0 (2026-10-22) | node24 |
  | `actions/upload-artifact` | `release.yml` (build) | `@v4` | node20 | v7.0.2 (2026-10-07) | node24 |
  | `actions/download-artifact` | `release.yml` (publish) | `@v4` | node20 | v8.0.2 (2026-10-07) | node24 |
  | `pypa/gh-action-pypi-publish` | `release.yml` (publish) | `@release/v1` | composite (Docker); internally pins `setup-python` v6.2.0, node24 | v1.14.3 (2026-10-20) | already fine |

  The warning names only checkout and setup-python because the artifact actions run only in `build` (and `publish`, only on tags); they target node20 too.

## Scope
- Bump `actions/checkout@v4` → `@v7`, `actions/setup-python@v5` → `@v7`, `actions/upload-artifact@v4` → `@v7`, `actions/download-artifact@v4` → `@v8` in `release.yml`, `ci.yml` and `release-window.yml`. Before bumping, re-check that these are still the latest majors.
- `pypa/gh-action-pypi-publish@release/v1` stays (no change needed).
- Breaking changes from the release notes that matter here (the implementer confirms each one):
  - **checkout v6:** credentials are persisted to a separate file instead of `.git/config`, and `persist-credentials` still defaults to `true`. The `build` job's `fetch-depth: 0` and `check_release_tag.py` (`git` against `origin/main`) must still work. **v7:** blocks checking out fork PRs under `pull_request_target`/`workflow_run`; neither trigger is used.
  - **setup-python v6:** node24 (runner >= 2.327.1; GitHub-hosted runners qualify). **v7:** ESM, and the `pip-install` input was removed (not used). `allow-prereleases` is still an input in v7.
  - **upload-artifact v5-v7 / download-artifact v5-v8:** both sides of an artifact must use compatible majors (the v4 rule). upload v7 adds `archive: false` (not used, so `dist/` is still zipped); download v8 errors on hash mismatches by default and skips unzipping non-zip content. Name-based download to `dist/` keeps its path (the v5 path change affects only downloads by ID).

## Out of scope
- Pinning actions to commit SHAs (see Risks).
- Any change to job names, triggers, `if:` conditions, matrix, steps or baselines.

## Acceptance criteria
- [ ] No `uses:` in `.github/workflows/` points to a node20 action; the PR body lists each old → new version.
- [ ] No "Node.js 20 is deprecated" warning in any job log on the PR (test jobs, `Build distributions`, `ruff + mypy (no new findings)`).
- [ ] All required checks pass: `All tests passed`, `ruff + mypy (no new findings)`; job names unchanged, so branch protection needs no edit.
- [ ] Publish path checked as far as possible without a release: `Build distributions` passes and uploads the `dist` artifact (visible in the run's artifacts); the `publish` job's `if:`, `needs:`, `environment` and `permissions` are unchanged in the diff; upload and download use the compatible majors above.
- [ ] `release-window.yml` still parses (its `workflow_dispatch` is not run, so no issue is created; checking the workflow file is valid in the Actions tab is enough).
- [ ] A `ci:` PR title, e.g. `ci: move GitHub Actions to Node.js 24 majors (T-074)`.

## Risks
- **Publish job untested until the next tag:** `download-artifact@v8` and `pypi-publish` only run on a `v*` tag. A mismatch would show up at release time. The release steps in `docs/releasing.md` already stop at a failed publish, and the tag can be re-pushed after a fix.
- **Credential handling (checkout v6+):** a script that reads the token from `.git/config` would break; none do today.
- **Tag-based pins move:** `@v7` follows new minor releases. Pinning every action to a commit SHA (with Dependabot updates) is a possible later hardening step, not part of this ticket.
- No user-visible change.
