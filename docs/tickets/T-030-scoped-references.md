# T-030: Scoped variable references (`$/a/b`, `$file!a/b`, `$../file!a/b`) in values

- **Issue:** [#41](https://github.com/mcgoldba/foamkit/issues/41)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S

## Goal
Values that reference another entry by scope or by file load, and are written back unchanged. Today they raise `ValueError` and the whole file fails.

## Evidence (real files, 2026-10-21)
One root cause: a `$` reference value is checked as a "valid key", and the check rejects `/`, `!` and `..`.
- **ESI v2606** `combustion/coldEngineFoam/freePiston/0/U:21` `internalField uniform $/internalField/U;` and `:37` `$/wall/U;` (`tests/releases/esi-v2606.freePiston.U`): `ValueError: The value '/internalField/U' is not a valid key.`
- **Foundation 14** `incompressibleFluid/cylinder/system/fvSolution:55` `timeScheme $fvSchemes!ddtSchemes/default;`: ValueError (planner checked the clone, 2026-10-21). The related `$!ddtSchemes/default` appears in that tutorial's `fvSchemes:39` inside `#ifeq (...)`, which is T-026's verbatim text.
- **Foundation 14** `floatingBeam/system/blockMeshDict:17` `centre $../constant/dynamicMeshDict!mover/bodies/beam/centreOfMass;` (`tests/releases/foundation-14.floatingBeam.blockMeshDict`): `ValueError: ... is not a valid key.`

## Scope
- The `$` variable parsing and validation path in `foamkit/types/__init__.py` (`ofVar` and the key validation it calls). Accept the OpenFOAM scoping syntax in **references**: leading `/` (root), `..` (parent), `/` separators, `name!path` (file-relative), `$<type>` hints, and `$!path` if the tester finds it outside conditionals. Keep the text unchanged on write.
- Key validation for **entry names** stays as strict as today.

## Out of scope
- Resolving references
- Scoped **keys** on the left-hand side, if found (record any as a follow-up)
- `#ifeq ($!ddtSchemes/default ...)` inside conditionals (T-026 keeps it verbatim)

## Acceptance criteria
- [ ] **Failing tests first** for each real form above, using the real fixtures. The F14 `fvSolution` lines come from the clone; record the source.
- [ ] After the fix, the freePiston `0/U` gets past these lines. If it then fails on `#remove`, that is covered by T-016. Each reference value round-trips unchanged.
- [ ] Entry names containing `/` or `!` are still rejected where they are rejected today (a regression test).
- [ ] All existing golden files are unchanged. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Loosening validation too far.** Only the `$` reference token is relaxed, never keys.

## Ranking rationale
Medium-high: it is a load failure in a stock Foundation 14 tutorial (`cylinder`) and ESI field files. It is small.
