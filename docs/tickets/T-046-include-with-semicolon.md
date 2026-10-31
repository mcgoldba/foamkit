# T-046: `#include "f";` (with a `;`) is written back as `#include "f";"`, which cannot be read

- **Issue:** [#62](https://github.com/mcgoldba/foamkit/issues/62)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-004 (include variants kept on write), T-015 (`#includeFunc` quoting), T-042 (#57, include directives inside lists; same `ofInclude` class), T-029 (#40, `#includeModel`/`#includeConstraint`), T-027 (#38, value-position `#calc`/`#neg`).
- **Found by:** the T-040 reviewer (PR #60), noted in the T-040 ticket ("the `#include "f";` write bug"). It is pre-existing on main.

## Goal
An include directive followed by `;` loads with the plain file name as its value and is written back unchanged, so the file reads back. A value-position `key #include "f";` loads or raises `FoamKitError` with file and line, never `TypeError`.

## Reproduction (planner, 2026-10-30, `t-042-include-inside-a-list` at a9a9447 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| `#include "f";` (top level) | loads as `ofInclude` with value `f";`. **Written as `#include    "f";"`**: re-reading fails with `FoamKitError: Unterminated string starting on line 18`. A user who edits anything else in the file and writes it gets a file neither FoamKit nor OpenFOAM can read |
| `d { … #include "f"; a 1; }` (multi-line sub-dict) | same: `#include    "f";"`; re-read fails |
| `#sinclude "f";`, `#includeEtc "caseDicts/x";` | same (`#sinclude   "f";"`, `#includeEtc "caseDicts/x";"`) |
| `#include "f"` (no `;`) | round-trips (T-004) |
| `#includeFunc streamlines;`, `#includeFunc enstrophy(executeAtStart=no);` | round-trips, but `.value` is `streamlines;` with the `;` |
| `d { value #include "f"; }` (value position) | **fails:** `TypeError: ofInclude.__init__() got an unexpected keyword argument 'name'` |

## Real tutorial occurrences (planner, 2026-10-30; `git grep` / `grep` over `tutorials/`, ESI from git `HEAD`)
- **Foundation 11-14: 0** `#include`/`#sinclude`/`#includeEtc`/`#includeIfPresent` with a `;`. F12-14 `incompressibleFluid/boxTurb16/system/functions:17` has `#includeFunc enstrophy(executeAtStart=no);`, which round-trips today.
- **ESI v2412, v2506, v2512, v2606: 12 lines in 12 files each:**
  - 11 files with `#include "…";` inside a sub-dict, all **load and then write a file that does not read back** (confirmed on v2606 `mesh/foamyHexMesh/blob/system/collapseDict:62` and `mesh/foamyQuadMesh/square/system/foamyQuadMeshDict:161`): `incompressible/porousSimpleFoam/straightDuctImplicit/system/collapseDict` (+ `.collapseFaces`, `.indirectPatchFaces`), `mesh/foamyHexMesh/{blob,flange,simpleShapes}/system/collapseDict`, `mesh/foamyHexMesh/mixerVessel/system/collapseDict` (+ 2 variants), `mesh/foamyQuadMesh/{jaggedBoundary,square}/system/foamyQuadMeshDict`;
  - 1 value-position: `mesh/foamyHexMesh/flange/system/faceSetDict:30` `value #include "../facesToBeRemoved";` (`TypeError` on load).

## Scope
- The include-directive parser and `ofInclude` / `ofIncludeEtc` / `ofIncludeFunc` in `foamkit/types/__init__.py`: the trailing `;` is not part of the value; the directive records that it had one and writes it back, so the text is unchanged (`#include "f";` stays `#include "f";`, `#include "f"` stays without).
- Value-position include (`key #include "f";`): loads and round-trips, or raises `FoamKitError` naming file and line.

## Out of scope
- Includes inside lists (T-042), `#includeModel`/`#includeConstraint` (T-029)
- Resolving included files
- Padding between `#include` and the file name (T-020)

## Acceptance criteria
- [ ] **Failing tests first:** every bug row of the table, at top level and inside a multi-line sub-dict, for `#include`, `#sinclude`, `#includeIfPresent`, `#includeEtc` and `#includeFunc`, plus real fixtures copied byte-exact into `tests/releases/` with their source recorded: ESI v2606 `mesh/foamyHexMesh/blob/system/collapseDict` and `mesh/foamyHexMesh/flange/system/faceSetDict`.
- [ ] `#include "f";` loads with value `f` and is written `#include` + padding + `"f";`; the written file re-reads to the same entries, and write 1 == write 2. `iterDirectives` lists it.
- [ ] `#includeFunc streamlines;` has value `streamlines` and is still written with its `;`.
- [ ] The `collapseDict` fixture loads, writes and re-reads; write 1 == write 2.
- [ ] `value #include "../facesToBeRemoved";` loads and round-trips, or raises `FoamKitError` naming file and line, never `TypeError`.
- [ ] No golden file changes. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Value change:** `.value` of an include read with a `;` changes from `f";` to `f`. That is the bug fix; say so in the commit body.
- `ofInclude.toString` is also used inside lists by T-042. Land after T-042 merges, so both changes to `toString` are tested together.
- OpenFOAM accepts the stray `;` after a directive (it is an empty statement), in both distributions; the ESI tutorials above rely on it.

## Ranking rationale
**Right after T-048.** Every tested ESI release has 11 stock tutorial files that load but are written back corrupt, so an edit produces a file neither FoamKit nor OpenFOAM can read. It is the same "lost at the last step" failure as T-042, in more files. The fix is small and in the class T-042 touches.
