# T-072: Release cadence, version rules and release steps

- **Issue:** [#93](https://github.com/mcgoldba/foamkit/issues/93)
- **Type:** docs + CI (owner: coordinator)
- **Size:** S
- **Track:** infrastructure
- **Requested by:** maintainer, 2026-11-07

## Goal
Users get a FoamKit on PyPI that keeps up with the latest OpenFOAM releases most of the year, gets fixes for silent data loss quickly, and has version numbers that say what changed.

## Today (2026-11-07)
- PyPI has `foamkit 0.1.0` (2026-10-03). `main` has 39 more commits, including `feat(cli)` and about ten silent-loss fixes, none released.
- `release.yml` publishes on a `v*` tag push (trusted publishing). Commitizen is configured (`semver`, `v$version`).
- The README release steps tag without `v` and push to `main`, which branch protection blocks.

## Scope
- `docs/releasing.md`: two scheduled minor releases a year (late January after ESI `vYY12`, mid-August after ESI `vYY06` + Foundation `N`); fix releases between windows; version-number rules (SemVer, PEP 440 spelling, commitizen-driven); 1.0 criteria; calendar (0.2.0 now, 0.3.0 January 2027, 0.4.0 August 2027); release steps through a `bump:` PR.
- `.github/workflows/release-window.yml` + `.github/release-window-issue.md`: on 5 January and 15 July, open a `release` issue with the window checklist (skipped if one with the same title is open).
- `release.yml` `build` job: on a tag push, fail if the tag differs from the `pyproject.toml` version.
- `pyproject.toml` `[tool.commitizen]`: `version_scheme = "pep440"`, `major_version_zero = true`, `prerelease_offset = 1`, `legacy_tag_formats = ["$version"]`.
- README "Releasing" section and `CLAUDE.md`: point to `docs/releasing.md`.

## Out of scope
- Publishing 0.2.0 (a separate `bump:` PR after this one, then the maintainer tags).
- ROADMAP decision entry (planner, next ROADMAP update).
- Supported-versions page (T-012).

## Acceptance criteria
- [ ] `python -m commitizen bump --dry-run` on `main` gives `0.1.0 → 0.2.0`; with `--increment MINOR --prerelease rc` it gives `0.2.0rc1`.
- [ ] `--files-only` updates `pyproject.toml` and `CHANGELOG.md` and makes no commit or tag.
- [ ] The tag guard passes for a matching tag and fails, with both versions in the message, for a mismatched one; it does not run for branch pushes or PRs.
- [ ] `release-window.yml` runs from `workflow_dispatch` and opens exactly one issue (a second run does not duplicate it).
- [ ] No Python source or test changes; `pytest -q` and the ruff/mypy ratchet are unchanged.
- [ ] PR title: `docs: add release cadence, version rules and release steps (T-072)`.
