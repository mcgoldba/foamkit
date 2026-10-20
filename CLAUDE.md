# Project conventions

Python package providing a Pythonic interface to OpenFOAM case editing (FoamKit, formerly PyFoamd).

## Commands
<!-- Adjust to match your repo -->
- Tests: `pytest -q`
- Lint: `ruff check . && ruff format --check .`
- Types: `mypy foamkit/`

## Code standards
- Python 3.9+ (matches `requires-python` and the CI matrix), type hints on all public functions, concise docstrings
- Public API changes need a deprecation path (keep old name as an alias with a warning)
- No `shell=True`, `eval`, or unchecked path joins; treat case files as untrusted input
- Tests must not require an OpenFOAM install; mark ones that do with `@pytest.mark.openfoam`

## Team workflow
Agents live in `.claude/agents/`. Hand-offs happen through files, not chat history. Each ticket is tracked on GitHub (`mcgoldba/foamkit`) as one issue and lands as one pull request.

1. `planner` updates `ROADMAP.md`, writes tickets to `docs/tickets/`, and opens a GitHub issue per new ticket (labels `ticket`, `needs-approval`, `size: S|M`; `documentation` for docs tickets). The ticket file links its issue on an `- **Issue:**` line.
2. **Maintainer approves the tickets** (human gate): the `needs-approval` label is replaced with `approved`. Only start tickets labelled `approved`.
3. The coordinator creates a branch off up-to-date `main`, named `t-<nnn>-<slug>` (e.g. `t-017-foamkiterror-exception`).
4. `tester` writes characterization/failing tests for the ticket
5. `implementer` makes the change for that ticket and runs all checks
6. The coordinator commits, pushes and opens a **draft PR** with `gh pr create --draft`:
   - Title: the conventional-commit subject that should land on `main`, e.g. `fix(types): parse #includeFunc with arguments (T-015)`. PRs are squash-merged, so the title becomes the commit that commitizen turns into the CHANGELOG.
   - Body: fill in `.github/pull_request_template.md` (`Closes #<issue>`, what changed for users, checks). Leave the "Maintainer reviewed" box unticked; only the maintainer ticks it.
7. `reviewer` reviews `git diff origin/main...HEAD` and returns APPROVE or REQUEST CHANGES. The coordinator posts the report on the PR (`gh pr comment <n> --body-file <report>`).
8. On REQUEST CHANGES, loop back to step 5 with the review findings, push, and post the new review.
9. On APPROVE and green CI, the coordinator marks the PR ready (`gh pr ready`). **The maintainer merges** (human gate): they review the diff and the reviewer report, tick "Maintainer reviewed" in the PR body, and use "Squash and merge". Branch protection on `main` requires a PR and the CI checks but no approving review, since GitHub does not let an author approve their own PR. Merging closes the issue; then mark the ticket done in `ROADMAP.md` in the next ticket's PR.

One ticket at a time. Do not start a new ticket until the previous one's PR is merged. Never push to `main` directly.

CI: `release.yml` runs `pytest` on Linux and Windows (Python 3.9 and 3.12). `ci.yml` runs ruff and mypy as a ratchet against the T-002 baseline: no new findings are allowed, and when a change removes findings, lower the baseline in `ci.yml` in that PR.
