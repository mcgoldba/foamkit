# T-009: Default header for newly created files comes from `detect()` at write time

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-008, T-006

## Goal
A dictionary file that FoamKit creates from scratch gets a banner matching the target release. Today the banner is fixed at import time from `WM_PROJECT_VERSION`, and without OpenFOAM it comes out as a Foundation banner with an empty `Version:`.

## Scope
- `foamkit/types/__init__.py:362-376` (default header lines)
- `OF_HEADER` `:44-49`
- Golden tests

## Out of scope
- Headers of files read from disk; those are kept verbatim by T-006

## Acceptance criteria
- [ ] Tests cover new-file header output for ESI, Foundation and `unknown`.
- [ ] The ESI line order and wording match a real ESI file from T-007.
- [ ] The `unknown` output is unchanged from today. If it changes, golden files are updated with the reason stated, and there is a `fix:` commit whose body describes the user-visible change.
- [ ] No import-time read of the environment is added.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- This is a visible output change for users with OpenFOAM sourced. Describe it in the `fix:` commit body.
