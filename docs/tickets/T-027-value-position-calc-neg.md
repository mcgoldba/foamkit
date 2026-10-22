# T-027: Value-position `#calc` and `#neg` (`key #calc "…";`, `key #neg $x;`)

- **Issue:** [#38](https://github.com/mcgoldba/foamkit/issues/38)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-016
- **Split from:** T-016, 2026-10-21 (maintainer-approved)

## Goal
Entries whose value is a `#calc` or `#neg` expression load, and are written back with their original source text. These are very common in Foundation `blockMeshDict` and field files.

## Evidence (real tutorial trees, 2026-10-21)
- **`key #calc "…";`:** Foundation, about 15/36/133/133 files in 11/12/13/14. ESI has 2, only in the IO test dictionary.
  - Example: Foundation 14 `incompressibleFluid/cylinder/system/blockMeshDict:27` `cylRadius #calc "$diameter / 2.0";` (`tests/releases/foundation-14.cylinder.blockMeshDict`).
  - Fails with `TypeError: ofCalc.__init__() got an unexpected keyword argument 'name'`. Foundation 13 `aerofoilNACA0012Steady/0/U` (`tests/releases/foundation-13.aerofoilNACA0012Steady.U`) fails the same way.
- **`key #neg $x;`:** Foundation, about 102/119/135/135 files.
  - Example: the same `blockMeshDict:29` `cylMin #neg $cylMax;`.
  - Fails with "Could not find functionEntry bracket type".
- The ticket's earlier example, a top-level `#calc "1+2"`, occurs in **no** tutorial.

## Scope
- Value-position handling for `#calc` and `#neg` in `DictFileParser`:
  - fix the `ofCalc` constructor so it accepts a `name`;
  - add `#neg` as a value-position directive. Use T-016's `ofVerbatimDirective`, or a small named type if `#neg` needs to keep its operand (`$x`) addressable. Decide in the PR and justify the choice.
- On write, the **source text** is kept exactly: quoting, `$<scalar>` type hints and spacing inside the quotes.
- Update the `OF_DIRECTIVES` rows for `calc` and `neg`.

## Out of scope
- Evaluating expressions
- `#calc` inside conditional blocks (it stays part of T-026's verbatim text)

## Acceptance criteria
- [ ] **Failing tests first** with the real fixtures `foundation-14.cylinder.blockMeshDict` (lines 27-34: `#calc`, `#neg`, `$<scalar>`) and `foundation-13.aerofoilNACA0012Steady.U`.
- [ ] After the fix, both parse. Every `#calc`/`#neg` entry is written back with its value text unchanged, and the key stays addressable (`d.cylRadius`).
- [ ] Top-level `#calc "1+2"` and `#calc #{ ... #}` also parse. They are not in any tutorial, but cheap to cover.
- [ ] All existing golden files are unchanged. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- Full loading of `foundation-14.aerofoilNACA0012Steady.U` also needs T-016 (`#codeBlock`) and T-013 (`angleOfAttack 0 [deg];`, `dimensions [velocity];`). Do not make that file an acceptance criterion here.

## Ranking rationale
**Second, right after T-016.** It is the most widespread load failure in the inventory: more than 100 files per Foundation 13/14 release, mostly `blockMeshDict`. The ticket is small.
