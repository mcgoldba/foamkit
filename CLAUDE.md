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
Agents live in `.claude/agents/`. Hand-offs happen through files, not chat history.

1. `planner` updates `ROADMAP.md` and writes tickets to `docs/tickets/`
2. **Maintainer approves the tickets** (human gate)
3. `tester` writes characterization/failing tests for one ticket
4. `implementer` makes the change for that ticket and runs all checks
5. `reviewer` reviews the diff and returns APPROVE or REQUEST CHANGES
6. On REQUEST CHANGES, loop back to step 4 with the review findings

One ticket at a time. Do not start a new ticket until the previous one is approved.
