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

### Real-file evidence (2026-10-19, Foundation 13/14 pitzDaily)
- **No** `[m/s]`-style unit annotations appear in pitzDaily for 13 or 14, so the forms in the table above are still unverified.
- Foundation 13 `constant/physicalProperties`: `nu [0 2 -1 0 0 0 0] 1e-05;`, which parses as `ofDimensionedScalar`. OK.
- Foundation 14 `constant/physicalProperties`: plain `nu 1e-05;`. OK.
- Foundation 13 `0/U`: `dimensions [0 1 -1 0 0 0 0];`, which parses as `ofNamedDimension`. OK.
- **Foundation 14 `0/U`: `dimensions [velocity];` (a named dimension set) parses as `ofStr('[velocity]')`**, not as a dimension type. Source: `https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-14/master/tutorials/incompressibleFluid/pitzDaily/0/U`.

## Scope
- **Step 1 (tester):** record the real unit syntax. pitzDaily shows none, so grep the wider Foundation 13/14 tutorial trees for `\[[a-zA-Z^/ ]+\]` after values and in `dimensions` entries. Record each distinct form with its source URL. If no annotated value forms exist, report back; the annotated-value part of this ticket may then be descoped by the maintainer.
- **Named dimension sets (Foundation 14):** `[velocity]`, plus every other name found in the 14 tutorials (record them). Parse them into a dimension type, not `ofStr`. The name is kept and written back unchanged. Classic `[0 1 -1 0 0 0 0]` handling is unchanged.
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
- [ ] The tester first records the real v13/v14 syntax found by the wider tutorial grep, with sources. If fewer than the listed forms exist, it reports back before implementation.
- [ ] `dimensions [velocity];` from the real Foundation 14 `0/U` (fixture copied byte-exact) parses to a dimension type, not `ofStr`, exposes the name, and round-trips byte-identically. The same holds for every other named set found.
- [ ] Failing tests exist for every form above that currently fails or corrupts.
- [ ] After the fix, every recorded form round-trips byte-identically (after FoamKit's normal whitespace formatting) and can be re-parsed.
- [ ] The numeric part is accessible as a number through `.value`. The unit string (for example `'m/s'`) is on a new **`.units`** attribute (maintainer-approved 2026-10-18), and is `None` for values without units. There is a CHANGELOG entry under Fix.
- [ ] Editing the numeric value keeps the unit annotation.
- [ ] Classic `[0 2 -1 0 0 0 0]` dimensioned entries and all existing golden files are unchanged.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- **Type change (approved as a bug fix, 2026-10-18):** values that come back as `ofStr` today will come back typed. User code comparing `.value` to the string `'2000 [s]'` would break. The CHANGELOG note is required; no deprecation alias is needed.
- **Ambiguity:** `[...]` after a value can be a unit or a classic dimension set. Decide by content (numbers only, versus unit symbols) and test both.
