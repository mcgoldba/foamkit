<!--
Title: the conventional-commit subject that should land on main, e.g.
  fix(types): parse #includeFunc with arguments (T-015)
PRs are squash-merged, so the title becomes the commit commitizen turns into the CHANGELOG.
-->

Closes #<!-- issue number -->

## What changes for users
<!-- One to three lines. "None (internal)" is fine. -->

## Checks
- [ ] `pytest -q` passes
- [ ] ruff / ruff format / mypy: no findings above the baseline in `.github/workflows/ci.yml` (lower it if this PR removes findings)

## Review
- [ ] Reviewer agent report posted on this PR (verdict: APPROVE)
- [ ] **Maintainer reviewed the diff and the reviewer report**
