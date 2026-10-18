# T-014: Legacy named dimensioned entries lose their value on write (best-effort releases)

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Plan:** docs/plans/openfoam-compatibility.md, bug B6

## Goal
The older named dimensioned form `nu nu [0 2 -1 0 0 0 0] 1.5e-05;`, found in older `transportProperties` files (best-effort releases), is written back with its value.

## Background
Reproduced on 2026-10-18 with a scratch file:
- the input `nu nu [0 2 -1 0 0 0 0] 1.5e-05;` parses to `ofNamedDimension(name='nu', dimensions=[...])`;
- it is written as `nu [0 2 -1 0 0 0 0];`;
- **the value `1.5e-05` is lost.**

## Scope
- The named-dimension parsing and printing in `foamkit/types/__init__.py` (`ofNamedDimension` and the related dimensioned types)
- A regression test

## Out of scope
- Converting legacy entries to modern syntax

## Acceptance criteria
- [ ] A failing test reproduces the value loss.
- [ ] After the fix, the entry round-trips with its name, dimensions and value, and the value is numeric when accessed.
- [ ] `nu [0 2 -1 0 0 0 0] 1.5e-05;` and all existing golden files are unchanged.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- This syntax is only in the best-effort range (no tested fixture). Use a hand-written fixture and record which release it imitates.
