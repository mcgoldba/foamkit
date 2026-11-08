# T-014: Named dimensioned entries (`nu nu [0 2 -1 0 0 0 0] 1e-05;`) lose their value on write

- **Issue:** [#21](https://github.com/mcgoldba/foamkit/issues/21)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Plan:** docs/plans/openfoam-compatibility.md, bug B6
- **Related:** T-081 (#108; the other dimension-set shapes that shift or drop tokens), T-013 (#20; named units), T-032 (number text).
- **Depends on:** none. Start after T-020 merges (same file). **Lands before T-081**, which depends on it (see Overlap with T-081).
- **Refreshed (maintainer, 2026-11-08):** real-file evidence added and ranked #3; the form is in tested releases, not only best-effort ones. Re-approval needed.

## Goal
The named dimensioned form `nu nu [0 2 -1 0 0 0 0] 1.5e-05;`, used in real Foundation 11 and ESI v2606 tutorials, is written back with its name, dimensions and value, also when the brackets have spaces inside (`[ 0 2 -1 0 0 0 0 ]`).

## Background
Reproduced on 2026-10-18 with a scratch file, and again on f8590d8 + 9ccebff on 2026-11-08:
- the input `nu nu [0 2 -1 0 0 0 0] 1.5e-05;` parses to `ofNamedDimension(name='nu', dimensions=[...])`;
- it is written as `nu [0 2 -1 0 0 0 0];`;
- **the value `1.5e-05` is lost**, silently, and write 1 == write 2, so the loss is permanent.
- `nu nu [0 2 -1 0 0 0 0] abc;` loses `abc` the same way. With an integer value (`E E [1 -1 -3 0 0 0 0] 0;`) the entry survives only by luck: 8 integers fail the 7-exponent count, so it is kept as `ofStr` text. With a vector (`g g [0 1 -2 0 0 0 0] (0 0 -9.81);`) it is kept as text.

### Real-file evidence (planner, 2026-11-08)
Method: `git grep` for `[…]` lines under `tutorials/` (Foundation 11 clone at 9cbf94f3, Foundation 14 at 31554318, ESI v2606 tarball read with `git grep --no-index`); each distinct one-line entry was loaded and written by FoamKit at f8590d8 and the tokens compared with the source.

| Release | Lines changed on write | Files |
|---|---|---|
| Foundation 11 | 16 | 10 |
| Foundation 14 | 0 | 0 |
| ESI v2606 | 64 | 29 |

All of them are this shape. A looser regex count finds 80 ESI lines (38 files) of the form with a non-integer value; **43 of them have spaces inside the brackets**. Examples:
- Foundation 11 `legacy/basic/laplacianFoam/flange/constant/physicalProperties:17` `DT DT [0 2 -1 0 0 0 0] 4e-05;` → `DT [0 2 -1 0 0 0 0];`
- Foundation 11 `XiFluid/kivaTest/constant/combustionProperties` (4 lines lost), `legacy/incompressible/adjointShapeOptimisationFoam/pitzDaily/constant/physicalProperties` (`lambda lambda [0 -2 1 0 0 0 0] 1e5;`)
- ESI `heatTransfer/buoyantSimpleFoam/hotRadiationRoom/constant/radiationProperties:28-29` (`absorptivity absorptivity [0 -1 0 0 0 0 0] 0.5;` → value lost; `E E [1 -1 -3 0 0 0 0] 0;` in the same file kept as text)
- ESI `combustion/XiDyMFoam/annularCombustorTurbine/constant/combustionProperties` (spaces: `Su Su [ 0 1 -1 0 0 0 0 ] 0.434;` → `Su [0 1 -1 0 0 0 0];`; 5 of its 8 entries lost, the 3 integer-valued ones kept as text)
- ESI `combustion/fireFoam/LES/flameSpreadWaterSuppressionPanel/constant/radiationProperties`, `incompressible/overSimpleFoam/aeroFoil/background_overset/constant/transportProperties`

## Overlap with T-081
Both tickets change `_parseDimensionValue` (~7127) and `_parseDimensionedType` (~6894). The split:
- **T-014 (this ticket, first):** the name in `key name [dims] value`, the value after it, and **spaces inside the brackets**, read by one bracket reader for the named and the unnamed form (43 real ESI lines need it; the unnamed `nu [ 0 2 -1 0 0 0 0 ] 1e-05;` comes with it).
- **T-081 (after T-014):** non-integer tokens in the brackets, wrong exponent counts, values that are not numbers, a value before the brackets, and the bare exceptions. It pins the spaced-bracket rows that T-014 fixes.

## Scope
- The named-dimension parsing and printing in `foamkit/types/__init__.py` (`ofNamedDimension` and the related dimensioned types, `_parseDimensionValue`, `_parseDimensionedType`), including spaces inside the brackets.
- A regression test with the real fixtures below.

## Out of scope
- Converting legacy entries to modern syntax.
- The T-081 shapes, named units (T-013), number text (`1e5` → `100000.0`, T-032).

## Acceptance criteria
- [ ] A failing test reproduces the value loss, without and with spaces inside the brackets, at the top level and in a sub-dict.
- [ ] Byte-exact fixtures in `tests/releases/` (source in the docstring, as in `tests/test_bound_box.py`):
  - Foundation 11 `tutorials/legacy/basic/laplacianFoam/flange/constant/physicalProperties` (commit 9cbf94f3339dd49286633b303c4155fd10ea8200, blob 7619059c);
  - ESI v2606 `tutorials/combustion/XiDyMFoam/annularCombustorTurbine/constant/combustionProperties` (from the `openfoam-OpenFOAM-v2606-tutorials` archive; record the archive URL and the file's `git hash-object`).
- [ ] After the fix, every named entry in both fixtures round-trips with its name, dimensions and value; the value is numeric when accessed; write 1 == write 2. Integer-valued entries (`XiShapeCoef XiShapeCoef [ 0 0 0 0 0 0 0 ] 1;`) keep their value too.
- [ ] `nu [0 2 -1 0 0 0 0] 1.5e-05;` and all existing golden files are unchanged.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): keep the value of named dimensioned entries (T-014)`.

## Risks
- **Type change:** integer-valued named entries that load as `ofStr` text today may become typed. Say so in the commit body.
- **Same function as T-081:** keep the change to the named form and the bracket spacing, so T-081 stays a separate S ticket.
- **OpenFOAM versions:** the form is in Foundation 11 (mostly `legacy/` and `XiFluid`) and ESI v2606; Foundation 14 tutorials no longer use it.
