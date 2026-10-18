# T-010: Canonical (Foundation 14) names with data-driven mapping for ESI and older Foundation

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M. Split into T-010a (renames: one table and the accessors) and T-010b (non-rename cases: fvOptions, solver) if T-010a alone fills a session.
- **Plan:** docs/plans/openfoam-compatibility.md, section 2.3
- **Depends on:** T-008 (and the T-007 fact-check table)

## Goal
A script can address case content by its **Foundation 14 name** on any supported case, and FoamKit finds the native file or key. Writes always keep the case's own native names.

## Design (maintainer guidance, 2026-10-18)
- **Canonical names:** the names used by the newest tested Foundation release, 14. ESI names and older-Foundation names map onto them.
- **One data-driven table:** `foamkit/compat.py`, built from frozen dataclass rows such as `Mapping(canonical, distribution, versions, native, kind)`. Thin generic accessors read the table. There is no hand-written function per name.
- **Kinds:**
  - `same`;
  - `renamed` (file or key rename);
  - `split`: one native object maps to several canonical ones (ESI `fvOptions` → `fvModels` + `fvConstraints`), handled explicitly;
  - `translated`: the value needs mapping (ESI `application simpleFoam` → Foundation 11+ `foamRun` with `solver incompressibleFluid`), using an explicit lookup table;
  - `none`: no equivalent.
- **No guessing:** when there is no mapping, or a `translated` value is not in its lookup table, raise `NoEquivalentError` (subclass of `KeyError`) with the case's release and the canonical name.
- **Native writes:** accessors return the native object. Editing it writes the native file or key. An ESI case is never rewritten into Foundation names.

## Proposed logical (canonical) names, for **maintainer sign-off at approval**

Confirm each name and version boundary against the T-007 fact-check table before implementing.

| Canonical (Foundation 14) | ESI v2412-v2606 | Older Foundation (best-effort) | Kind |
|---|---|---|---|
| `constant/momentumTransport` | `constant/turbulenceProperties` | `turbulenceProperties` (≤7) | renamed |
| `momentumTransport:RAS.model` | `RAS.RASModel` | `RAS.RASModel` (≤8) | renamed |
| `momentumTransport:LES.model` | `LES.LESModel` | `LES.LESModel` (≤8) | renamed |
| `constant/physicalProperties` | `constant/transportProperties` | `transportProperties` (≤9) | renamed |
| `constant/fvModels` | `constant/fvOptions` (source entries), `system/fvOptions` | `fvOptions` (≤9) | split |
| `system/fvConstraints` | `fvOptions` (constraint entries) | `fvOptions` (≤9) | split |
| `controlDict:solver` | `controlDict:application` via lookup (`simpleFoam`/`pimpleFoam` → `incompressibleFluid`, …) | `application` (≤10) | translated |
| function object `residuals` | `solverInfo` | — | renamed (used by T-011) |

## Scope
- `foamkit/compat.py`: the table, `resolve(case, canonical) -> Resolved` (native path or key, kind, release), `nativeName(case, canonical)`, and `NoEquivalentError`.
- Thin accessors on the case object, for example `case.canonical("constant/physicalProperties")`. This is a new method; no existing attribute changes.
- Tests: each tested fixture family for every name, plus tiny synthetic dicts for best-effort rows.

## Out of scope
- Converting whole cases between distributions
- Writing canonical names into a case
- Solver translations beyond the incompressible solvers in the lookup table; add rows later

## Acceptance criteria
- [ ] Every table row has a test. Rows for tested releases use the T-007 fixtures; best-effort rows use synthetic dicts and are labelled best-effort.
- [ ] The `split` case: on an ESI fixture, `fvModels` and `fvConstraints` each resolve to the native `fvOptions` with `kind="split"`. If the entries cannot be classified, the error says so rather than picking one.
- [ ] The `translated` case: `simpleFoam` maps to `incompressibleFluid`. An application not in the lookup table raises `NoEquivalentError`.
- [ ] Edits through an accessor change only the native file or key. A golden test shows an ESI case still has `turbulenceProperties` / `RASModel` after a write.
- [ ] Adding a new mapping is a one-row change. The reviewer checks that there is no per-name code.
- [ ] The public API is purely additive. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- The canonical names become public API, so maintainer sign-off on the table is required. Future Foundation renames will add rows rather than rename canonical names; the update policy is recorded in T-012.
- The version boundaries in the table are from memory until T-007 confirms them.
- Detection with `unknown`: `resolve` tries the native candidates in a documented order and reports which one it used.
