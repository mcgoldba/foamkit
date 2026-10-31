# T-047: Brace-delimited references `${name}` raise a bare `ValueError`, or empty a list

- **Issue:** [#63](https://github.com/mcgoldba/foamkit/issues/63)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-030 (#41, scoped `$` references). Both relax the same reference check (`ofVar`, "is not a valid key"), so land this one after it.
- **Related:** T-026 (#37, `${…}` inside `#if`/`#ifeq` stays T-026's verbatim text), T-028 (#39, `#word "… ${FOAM_API:-unset}"`), T-044 (#59, `#eval`), T-016 (`${…}` inside `#message` strings already loads).
- **Found by:** the T-040 reviewer (PR #60), noted in the T-040 ticket ("`${a}` `ValueError`"). It is pre-existing on main.

## Goal
Values and entries written with a brace-delimited reference, `${name}`, load and are written back unchanged. Anything still unsupported raises `FoamKitError` naming file and line; a list never silently loses its items.

## Reproduction (planner, 2026-10-30, `t-042-include-inside-a-list` at a9a9447 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| `a 1;` / `b ${a};` (top level or in a sub-dict) | **fails:** `ValueError: The value '{a}' is not a valid key.` (bare, no file or line) |
| `b ${d.a};`, real F13/F14 `min ${${FOAM_CASE}/0/T!TWind};` | same `ValueError` |
| `a 1;` / `b ( ${a} 2 );` (one-line list) | **silent loss:** loads as an **empty list** and is written `b` / `(` / `);` |
| multi-line list with a `${a}` item | `FoamKitError: Invalid syntax.  List value does not begin with '('.` (no line) |
| a `${name}` line on its own inside a dict (ESI dict-merge form, e.g. `${_plane}`) | `FoamKitError: Invalid syntax on line N` |
| `b "${a}";`, `#message "… ${FOAM_API:-unset}"`, `omega constant ${{ 2.1 * (2*pi()) }};` | load and round-trip |
| `b $a;`, `b ( $a 2 );` | load and round-trip |

## Real tutorial occurrences (planner scan, 2026-10-30; `FoamFile` files under `tutorials/`, comments and strings masked; ESI from git `HEAD`)
| `${` outside strings | F11 | F12 | F13 | F14 | ESI v2412 | v2506 | v2512 | v2606 |
|---|---|---|---|---|---|---|---|---|
| outside `#if` lines: files (occurrences) | 0 | 0 | 1 (4) | 2 (6) | 37 (203) | 38 (204) | 41 (208) | 43 (212) |
| on `#if`/`#ifeq` lines (T-026) | 0 | 0 | 0 | 0 | 2 (9) | 2 (9) | 2 (9) | 2 (9) |
| inside a list | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

- Foundation, all fail with the `ValueError`: F13/F14 `fluid/stackPlume/system/fvConstraints:20-21` (`min ${${FOAM_CASE}/0/T!TWind};`), F14 `fluid/concentricCylinders/0/T.orig:50` (`${${FOAM_CASE}/constant/physicalProperties!baffle};`, an entry on its own).
- ESI v2606, all 43 files loaded: **28 fail at the `${…}` line**. 12 raise the bare `ValueError` (e.g. `lumpedPointMotion/bridge/steady/system/controlDict`, `pimpleFoam/RAS/TJunctionArrheniusBirdCarreauTransport/system/controlDict` `${../../../rhoInf}`, `interFoam/RAS/mixerVesselAMI/system/snappyHexMeshDict` `${../vessel}`, `mesh/blockMesh/pipe/0.orig/pointDisplacement`). 16 raise "Invalid syntax on line N" at a `${name}` dict-merge line (e.g. `rhoSimpleFoam/squareBend/system/sampling` `${_plane}`, `snappyHexMesh/distributedTriSurfaceMesh/system/snappyHexMeshDict` `${_decomp}`, `moveDynamicMesh/faceZoneBlock/0/pointDisplacement` `${movingZone}`). The other 15 fail earlier for other reasons (block comments T-031, `#eval` T-044, `IndexError`) or load (`${{ … }}`).
- 0 tutorial files have `${…}` inside a list, so the silent empty list is not hit by stock files.

## Scope
- The `$` reference path in `foamkit/types/__init__.py` (`ofVar` and its "valid key" check), extended after T-030: accept `${…}` with balanced braces, including nested `${${FOAM_CASE}/…}`, scoped names (`.`, `/`, `..`, `!`) and the ESI default forms `${name:-word}` / `${name:+word}`. The text is kept unchanged on write.
- A `${name}` entry on its own inside a dict, with or without `;` (dict merge): kept verbatim in place, like a `$name;` entry today if that works, otherwise as a verbatim entry.
- The list item parser: `${a}` is one list item in one-line and multi-line lists.
- Any `${…}` form still unsupported raises `FoamKitError` naming file and line, never a bare `ValueError`.

## Out of scope
- Expanding references or environment variables
- `${…}` inside `#if`/`#ifeq` (T-026), inside `#word`/`#message` strings (T-028, T-016)
- `${{ … }}` expressions (load today)

## Acceptance criteria
- [ ] **Failing tests first:** every bug row of the table, at top level and inside a sub-dict, plus real fixtures copied byte-exact into `tests/releases/` with their source recorded: Foundation 14 `fluid/stackPlume/system/fvConstraints` and ESI v2606 `incompressible/simpleFoam/squareBend/system/sampling` (or another file from the 16 whose only blocker is the `${name}` line; the tester checks).
- [ ] `b ${a};`, `b ${d.a};`, `min ${${FOAM_CASE}/0/T!TWind};` and `b ${FOAM_API:-0};` load, keep their text, and write 1 == write 2.
- [ ] `b ( ${a} 2 );` never loads as an empty list: it keeps 2 items, or raises `FoamKitError` with file and line. Same for the multi-line list.
- [ ] Both real fixtures load and write 1 == write 2.
- [ ] No input in this ticket raises a bare `ValueError`.
- [ ] Entry **names** that are not valid keys are still rejected (regression test; T-030 adds the same).
- [ ] No golden file changes. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Loosening validation:** only the reference token is relaxed, never entry names (same rule as T-030).
- **ESI-only forms** (`:-`, `:+`, dict merge with `${…}`) are best kept verbatim; FoamKit must not try to interpret them.
- The silent empty list is in the list parser T-042 and T-048 also touch; land after them.

## Ranking rationale
**In the backlog after T-043, ahead of T-045.** It blocks 28 ESI files per release and 1-2 Foundation 13/14 files, loudly but with a bare `ValueError` that has no file or line. It also removes a silent empty-list path that no stock tutorial hits today. It follows T-030, which fixes the same check for unbraced scoped references.
