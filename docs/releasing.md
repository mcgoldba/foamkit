# Releasing FoamKit

FoamKit is published to PyPI as [`foamkit`](https://pypi.org/p/foamkit). Pushing a `v*` tag runs `.github/workflows/release.yml`, which tests, builds and publishes through PyPI trusted publishing. This page covers **when** to release, **which number** to use, and **how**.

## When to release

There are two kinds of release.

### 1. Scheduled compatibility releases (twice a year)

OpenFOAM releases come in two clusters each year:

| Distribution | Release | Usual date |
|---|---|---|
| ESI (openfoam.com) | `vYY06`, `vYY12` | late June, late December |
| Foundation (openfoam.org) | `N` (one per year) | July |

FoamKit has one scheduled release about a month after each cluster. The month allows for any changes FoamKit needs for the new releases:

| Window | After | Prep issue opens | Target | Latest |
|---|---|---|---|---|
| **January** | ESI `vYY12` | 5 January | last week of January | end of February |
| **August** | ESI `vYY06` + Foundation `N` | 15 July | third week of August | end of September |

`.github/workflows/release-window.yml` opens the prep issue (label `release`) with the [release-window checklist](#release-window-checklist).

A scheduled release is **always at least a minor release**, because it changes the set of tested OpenFOAM releases. The "four latest releases of each distribution" policy is in [plans/openfoam-compatibility.md](plans/openfoam-compatibility.md). In each window:

- each new OpenFOAM release joins the tested set (real tutorial files in `tests/releases/`, with the release in the CHANGELOG);
- the oldest release of that distribution moves to best-effort. It is dropped only when a new one replaces it, so each distribution keeps four tested releases.

**The window is a date, not a feature gate.** If support for a new OpenFOAM release isn't ready by the target date, the release still ships. The new OpenFOAM release is then listed as *best-effort, not yet tested*, nothing is rotated out for it, and it joins the tested set in a later minor release. If the target date slips, the prep issue says why and gives the new date.

### 2. Fix and feature releases (between windows, as needed)

Fixes don't wait for a window.

- **Fixes for silent data loss or corruption:** release within a week of the merge. Users on PyPI should never keep a known silent-loss bug for months.
- **Other fixes and features:** release when there is something worth shipping, and at least once a month while `main` has unreleased `fix:` or `feat:` commits.

Commitizen chooses the number from the commits (see below), so an off-cycle release is a patch or a minor release depending on what landed. There are no maintenance branches: fixes go to `main` and ship in the next release. Older minor versions get no backports.

## Version numbers

FoamKit uses [Semantic Versioning](https://semver.org/) with [PEP 440](https://peps.python.org/pep-0440/) spelling (`0.3.0rc1`, not `0.3.0-rc.1`). Tags are `v<version>`. **The version does not encode an OpenFOAM release.** Each FoamKit release supports several OpenFOAM releases from more than one distribution. Which ones are tested is stated in the CHANGELOG entry and on the supported-versions page (T-012).

Commitizen computes the bump from the conventional-commit PR titles (PRs are squash-merged):

| Change | Commit | While `0.x` | From `1.0` |
|---|---|---|---|
| Bug fix, including turning silent loss into a `FoamKitError` | `fix:` | patch | patch |
| New public API, CLI command or option | `feat:` | minor | minor |
| A new OpenFOAM release joins the tested set, or one moves to best-effort | scheduled window | minor | minor |
| Deprecation (old name kept as an alias with a warning, per `CLAUDE.md`) | `feat:` | minor | minor |
| Minimum Python raised, after one minor release of notice. `requires-python` stops pip from installing it on the old Python, so it is not marked breaking | `feat:` | minor | minor |
| Deprecated name removed, or a valid call changes behaviour incompatibly | `feat!:` or `BREAKING CHANGE:` | **minor** | **major** |
| Docs, tests, CI, refactor | `docs:` `test:` `ci:` `refactor:` `chore:` | no release on its own | same |

Notes:

- **Turning a silent loss into a loud error is a fix, not a breaking change.** Code that "worked" while losing data was already broken. The CHANGELOG entry still names the new error so users can find it.
- **While `0.x`,** breaking changes bump the minor version (`major_version_zero = true` in `pyproject.toml`) and are listed under `BREAKING CHANGE` in the CHANGELOG.
- **Deprecations** stay for at least one minor release before removal. Before 1.0, the earliest removal is the next minor release. From 1.0, removal waits for the next major release.
- A scheduled release must be at least a minor release, because the tested set changed. If the dry run proposes only a patch, add `--increment MINOR`. Never use `--increment` to lower the bump commitizen proposes: from 1.0, that would hide a major.

### 1.0.0

1.0.0 is a maintainer decision. Proposed criteria:

- no known silent data-loss bugs on tested releases;
- the release fixture matrix (T-007) and lossless round-trip of unedited entries (T-020) are done;
- the public API is documented (T-001), and `SystemExit` has been removed from `FoamKitError`.

After 1.0, a major release happens only for breaking changes, never just because of the calendar.

### Pre-releases

For a scheduled release with large compatibility changes, publish a release candidate (`0.3.0rc1`) one to two weeks before the target date. `pip install foamkit` ignores pre-releases. Testers use `pip install --pre foamkit`. The final release's CHANGELOG entry also lists the commits from its release candidates (`changelog_merge_prerelease = true`), so its release notes are complete.

## Calendar

| Version | Target | Contents |
|---|---|---|
| **0.2.0** | week of 2026-11-16, after PR #91 (T-055) merges | Off-cycle catch-up: 39 commits since 0.1.0, including about ten fixes for silent loss (T-035, T-037, T-040, T-041, T-052, T-055) and the `fk` command. `FoamKitError` subclasses `Exception` and keeps `SystemExit` through 0.2.x (T-017). |
| 0.2.x | as needed | Fixes (for example T-056/T-057 comment loss) |
| **0.3.0** | last week of January 2027 | ESI v2612 (expected December 2026) joins the tested set; ESI v2412 moves to best-effort. `SystemExit` is removed from `FoamKitError` (ROADMAP: "the release after T-017 ships"). |
| **0.4.0** | third week of August 2027 | ESI v2706 and Foundation 15 (expected June and July 2027) join; ESI v2506 and Foundation 11 move to best-effort. |

Tested set by policy today: Foundation 11-14 and ESI v2412, v2506, v2512, v2606. Real tutorial files are so far in `tests/releases/` only for Foundation 11, 13, 14 and ESI v2606; T-007 adds fixtures for the rest.

## How to release

The steps are the same for every release. Branch protection blocks pushes to `main`, so the version bump lands through a PR, and the tag goes on the merged commit. **Only the maintainer pushes the tag** (it publishes to PyPI), or someone they explicitly ask to.

1. **Prepare the bump** on a branch off up-to-date `main`:

   ```bash
   git switch -c release/v0.2.0 origin/main
   python -m commitizen bump --dry-run            # check the version and CHANGELOG
   python -m commitizen bump --yes --files-only   # add --increment MINOR only if a window release would be a patch
   ```

   `--files-only` updates `pyproject.toml` and `CHANGELOG.md` and makes no commit or tag. For a release candidate, add `--prerelease rc`.

2. **Edit the CHANGELOG entry** if needed. Add to the generated lines; don't reword or remove them, because the tag check (step 4) looks for each commit's text: for a scheduled release, add a `### Supported OpenFOAM releases` list (tested and newly best-effort); name new `FoamKitError`s; spell out the user impact of any `BREAKING CHANGE`.

3. **Open the PR.** Commit as `bump: version 0.1.0 → 0.2.0` (commitizen leaves `bump:` commits out of the CHANGELOG) and use the same PR title. Wait for green CI, then the maintainer squash-merges.

   **The bump PR must be the last PR merged before the tag.** Branch protection doesn't require branches to be up to date, so a PR that merges while the bump PR is open would ship without a CHANGELOG entry. Don't merge other PRs while it is open. If `main` moved anyway, redo the bump on top of it:

   ```bash
   git fetch origin && git reset --hard origin/main
   python -m commitizen bump --yes --files-only   # same flags as before
   git commit -am "bump: version 0.1.0 → 0.2.0" && git push --force-with-lease
   ```

   This throws away the step-2 edits, so redo them before committing.

   `release.yml` checks this at tag time too (step 4).

4. **Tag the merged commit and push the tag** (maintainer):

   ```bash
   git switch main && git pull --ff-only
   git tag -a v0.2.0 -m "FoamKit 0.2.0"
   git push origin v0.2.0
   ```

   `release.yml` (`.github/scripts/check_release_tag.py`) refuses to publish if the tag doesn't match the `pyproject.toml` version, if the tagged commit isn't on `main`, or if a `feat`/`fix`/`refactor`/`perf`/breaking commit since the previous tag is missing from `CHANGELOG.md`. Nothing reaches PyPI in that case. Delete the tag (`git push origin :v0.2.0`, `git tag -d v0.2.0`), fix the cause and tag again.

5. **Check and announce:**
   - the `Publish to PyPI` job is green and <https://pypi.org/p/foamkit> shows the version;
   - `pip install foamkit==0.2.0` works in a clean environment and `fk --help` runs;
   - `gh release create v0.2.0 --title "FoamKit 0.2.0" --notes-file <CHANGELOG section>`;
   - close the release-window issue (scheduled releases).

### Release-window checklist

The prep issue's body is [`.github/release-window-issue.md`](../.github/release-window-issue.md); edit the checklist there.
