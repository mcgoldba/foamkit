# T-008: Detect the OpenFOAM distribution and version (`FoamRelease`)

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M
- **Plan:** docs/plans/openfoam-compatibility.md, section 2.2
- **Depends on:** T-007

## Goal
Users and FoamKit internals can ask which OpenFOAM release a case or environment targets (`esi`, `foundation` or `unknown`, plus version) without OpenFOAM installed.

## Scope
- New module `foamkit/release.py`:
  - `FoamRelease` frozen dataclass (`distribution`, `version`, `major`, `source`);
  - `detect(case_path=None, override=None)`.
- **Detection order (maintainer-approved 2026-10-18):**
  1. explicit `override` argument, then config key `openfoam_release`;
  2. the **case banner** of `system/controlDict`;
  3. the environment (`WM_PROJECT_VERSION`, `FOAM_API`, `WM_PROJECT_DIR`);
  4. `unknown`.
- `fkf.foamRelease(path=None)` in `foamkit/functions/`.
- An optional lazy `case.release` property.
- The config default in `foamkit/config.ini` / `CONFIG_DEFAULTS`.

## Out of scope
- Changing any existing behaviour based on the result (T-009, T-010, T-011)

## Acceptance criteria
- [ ] Parametrized tests cover:
  - every T-007 fixture banner;
  - env combinations (ESI `v2606` with `FOAM_API=2606`; Foundation `14`; Foundation `dev`; unset);
  - a case banner that disagrees with the environment, where the banner wins;
  - an override, which beats both.
- [ ] `unknown` is returned, never raised, for missing or unreadable inputs and for an unrecognised banner.
- [ ] `foamkit.FOAM_VERSION` and `pf.foamVersion()` are unchanged (an existing-behaviour test is added first).
- [ ] Public functions have type hints and docstrings.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- The banner and env formats must come from the T-007 fact-check table, not from memory. `dev`/nightly builds have no numeric version, so use `major=None`.
- Best-effort releases with unfamiliar banners must fall back to the environment, then `unknown`, and never fail.
