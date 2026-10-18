# T-013: Parse and round-trip unit-annotated values (Foundation 13+ input units)

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M. If the tester finds more forms than listed here, split it: T-013a scalars, T-013b lists and fields.
- **Plan:** docs/plans/openfoam-compatibility.md, bug B5

## Goal
Cases from Foundation 13/14 that write values with units (for example `0.1 [m/s]`, `[ft/s]`) load, edit and write back without parse errors or file corruption.

## Background
CFD Direct reports that Foundation OpenFOAM in 2026 made units in input files standard. I could not check the exact syntax: it must be taken from real v13/v14 tutorial files.

On 2026-10-18 I probed these guessed forms with scratch files (no code changed):

| Input | Current result |
|---|---|
| `nu 1.5e-05 [m^2/s];` | Parsed as `ofStr` `'1.5e-05 [m^2/s]'`. The text round-trips, but `.value` is not numeric, so edits and comparisons break. |
| `endTime 2000 [s];` | Same: `ofStr` `'2000 [s]'`. |
| `Uinlet (10 0 0) [m/s];` | **Corrupted.** `[m/s]` becomes a fourth list element and is written inside the parentheses. |
| `internalField uniform (10 0 0) [m/s];` | **Parse error** (`ValueError`, "must be a valid OpenFOAM field type"). |
| `nu [0 2 -1 0 0 0 0] 1.5e-05;` (classic dimensions) | OK, `ofDimensionedScalar`. |

## Scope
- The value and list parsing in `foamkit/types/__init__.py`:
  - how a trailing `[...]` after a scalar, vector or list is classified;
  - field (`uniform`/`nonuniform`) value parsing;
  - the corresponding `toString` methods.
- A small fixture `tests/fixtures/dicts/inputUnits*`, copied from real Foundation 13/14 tutorial files (source release and file recorded).
- Tests.

## Out of scope
- Converting between units. `foamkit/functions/_interpretUnitsAndConvert.py` and `pint` stay as they are.
- Validating unit strings.
- ESI. If ESI has an equivalent, record it as a follow-up.

## Acceptance criteria
- [ ] The tester first confirms the real v13/v14 syntax and records three or more distinct forms from real files in this ticket (scalar, vector/list, field, plus any others found).
- [ ] Failing tests exist for every form above that currently fails or corrupts.
- [ ] After the fix, every recorded form round-trips byte-identically (after FoamKit's normal whitespace formatting) and can be re-parsed.
- [ ] The numeric part is accessible as a number. The unit is kept as a separate attribute; name it in the ticket at implementation and note it in the CHANGELOG.
- [ ] Editing the numeric value keeps the unit annotation.
- [ ] Classic `[0 2 -1 0 0 0 0]` dimensioned entries and all existing golden files are unchanged.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- **Type change:** values that come back as `ofStr` today will come back as a typed object. User code comparing `.value` to the string `'2000 [s]'` would break. That code is unlikely, but call it out in the CHANGELOG.
- **Ambiguity:** `[...]` after a value can be a unit or a classic dimension set. Decide by content (numbers only, versus unit symbols) and test both.
