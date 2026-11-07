Scheduled OpenFOAM compatibility release. Policy, version rules and release steps: [docs/releasing.md](https://github.com/mcgoldba/foamkit/blob/main/docs/releasing.md).

**Target:** last week of January (latest end of February) or third week of August (latest end of September). If the date slips, say why here and give the new date.

- [ ] New OpenFOAM releases since the last window: ESI ____, Foundation ____ (or "none yet")
- [ ] Real tutorial files for each new release added to `tests/releases/`; new failures ticketed
- [ ] Each new release decided as tested, or as best-effort, not yet tested
- [ ] For each distribution that gained a tested release, its oldest tested release moved to best-effort (compat plan, README, supported-versions page)
- [ ] Deprecations due for removal in this release removed (listed under `BREAKING CHANGE`)
- [ ] Optional: `rc1` published one to two weeks before the target
- [ ] CHANGELOG entry lists the tested and best-effort OpenFOAM releases
- [ ] Released with `python -m commitizen bump --yes --files-only --increment MINOR`, bump PR merged, tag pushed, PyPI checked, GitHub release created
