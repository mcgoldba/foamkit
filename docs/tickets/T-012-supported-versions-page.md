# T-012: "Supported versions" docs page

- **Type:** docs (owner: `docs-writer`)
- **Size:** S
- **Depends on:** T-001 (Sphinx site) and T-007 (fixtures and fact-check table). Update the page after T-010, T-011 and T-013 land.

## Goal
A user can see in one page which OpenFOAM releases and Python versions FoamKit supports, and what "supported" means.

## Scope
- `docs/supported-versions.md`, added to the `index` toctree.
- **Python:** 3.9+; tested in CI on 3.9 and 3.12 (from `.github/workflows/release.yml`).
- **Tested releases** (a T-007 fixture runs in CI): Foundation 11, 12, 13, 14 and ESI v2412, v2506, v2512, v2606.
- **foam-extend:** 4.1 and 5.0, tier "headers tested, otherwise best-effort". Header recognition and byte-for-byte header write are tested (T-005, T-006); release detection is tested (T-008); file and key names are not mapped (no `case.canonical` support).
- **Best-effort (untested):**
  - older releases, for example Foundation 7-10 and ESI v2006-v2406;
  - releases newer than the tested set;
  - known best-effort gaps, for example legacy named dimensioned entries (T-014) if that ticket has not landed.
- **Policy:**
  - "tested" means the four latest releases of each distribution. Each new release is added and the oldest dropped.
  - Canonical names follow the newest tested Foundation release (T-010).
- **Per-distribution notes**, taken from the T-007 fact-check table only:
  - file and key names;
  - banner style;
  - directives (`#sinclude`);
  - unit-annotated values (Foundation 13+);
  - `solverInfo` vs `residuals`;
  - `0.orig`.
- **Examples:** use `import foamkit.functions as fkf` and `import foamkit.types as fkt`.
- A pointer to the `openfoam` pytest marker.

## Out of scope
- API reference for `foamkit.release` / `foamkit.compat`
- Hosting

## Acceptance criteria
- [ ] The strict Sphinx build from T-001 exits 0 with the new page in the toctree.
- [ ] The tested rows match the fixture directories under `tests/fixtures/releases/` exactly, checked by listing.
- [ ] Best-effort releases are clearly marked as untested.
- [ ] Every name in the per-distribution notes appears in the T-007 fact-check table.
- [ ] Every code snippet runs without OpenFOAM or is labelled "requires OpenFOAM".
- [ ] `git diff --stat -- foamkit/` is empty, and `pytest -q` passes.

## Risks
- The page goes stale when the tested set rolls forward. The update policy is stated on the page itself.
