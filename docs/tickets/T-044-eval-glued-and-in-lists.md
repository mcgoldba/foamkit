# T-044: `#eval` forms used by ESI: `#eval{-$x}` with no space, and `#eval` inside lists

- **Issue:** [#59](https://github.com/mcgoldba/foamkit/issues/59)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-027 (#38, value-position `#calc`/`#neg`; does **not** cover `#eval`), T-039 (#52, keyword glued to its bracket, `x{`/`x(`; does **not** cover a directive glued to its body), T-040 (#54, one-line `{…}` blocks), T-042 (directives in lists), T-016 (`eval` is listed as "interpreted" in `OF_DIRECTIVES`).
- **Found by:** the T-041 reviewer (PR #56), on ESI v2606 `mesh/refineMesh/refineFieldDirs/system/blockMeshDict`. It is pre-existing on main.

## Goal
`#eval` entries in the forms ESI tutorials use load and are written back with their expression text unchanged. Anything still unsupported raises `FoamKitError` naming file and line; a list never silently loses its items.

## Reproduction (planner, 2026-10-29, `t-040-one-line-brace-blocks` at 376edf3 + uncommitted tests; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| real ESI v2606 `refineFieldDirs/system/blockMeshDict` (line 36 `Cx  0.310358;    Cy  #eval{-$Cx};`) | **fails:** `FoamKitError: Could not find functionEntry bracket type.` (no file or line in the message) |
| `Cy #eval{-$Cx};` on its own line | **fails:** `IndexError: list index out of range` |
| `xdim #eval{0.5 * $N};` | `IndexError` |
| `Cy #eval{ -$Cx };`, `Cy #eval {-$Cx};`, `Cy #eval "-$Cx";` | load and round-trip |
| top-level one-line list `origin (#eval{0.5 * $S} 0 0);` | **silent loss:** loads as an empty list and is written `origin ( );`. Inside a sub-dict (the real `multiWorld2/slab1` shape) it raises `FoamKitError` "one-line '{ ... }' blocks … (T-040)" since T-041 |
| multi-line list item `(#eval{0.5 * $S} 0 0)` | loads as one string item; written with the expression's spacing changed (`0.5  * $S`) |

So the bug is a **glued body**: `#eval{` followed directly by a non-space character. Neither T-027 nor T-039 covers it, hence this ticket.

## Real tutorial occurrences (planner, 2026-10-29)
- **Foundation 11-14: 0** `#eval` in tutorials.
- **ESI v2412, v2506, v2512, v2606: 20 files each** with `#eval{` glued to its body (`git grep -E '#eval\{[^ ]'` over `tutorials/`), e.g.:
  - value position: `mesh/refineMesh/refineFieldDirs/system/blockMeshDict:36-37`, `basic/laplacianFoam/multiWorld2/top/system/blockMeshDict:28` (`xdim  #eval{0.5 * $NSLABS};`), `incompressible/pimpleFoam/LES/NACA4412/system/forceCoeffs:28-29` (v2506+);
  - inside lists: `multiWorld2/slab1..4/system/blockMeshDict:23` (`origin  (#eval{0.5 * $SLAB_OFFSET} 0 0);`), `NACA4412/system/blockMeshDict:118-155`, `laminar/filmPanel0/system/blockMeshDict:45-51`.
- **`#eval` inside a list** (any spacing): 8 files, 31 occurrences per ESI release (planner token scan).
- Loaded with FoamKit (ESI v2606): `refineFieldDirs`, `multiWorld2/slab1`, `NACA4412/system/blockMeshDict` and `wallMountedHump/setups.orig/common/system/blockMeshDict` all fail with "Could not find functionEntry bracket type."; `filmPanel0/system/blockMeshDict` loads.

## Scope
- `_parseVerbatimEntry` and the value-position directive path in `DictFileParser`: recognise `#eval{` when the body starts right after the `{` (and `#eval{…}` closing on the same line), in value position and as a list item. Use T-035's scanner to find the matching `}`.
- The list item parser: a one-line list holding `#eval{…}` keeps every item. Keep the `#eval{…}` item's text verbatim.
- The "Could not find functionEntry bracket type." error names the file and line.

## Out of scope
- Evaluating expressions
- `#calc`/`#neg` (T-027); other directives in lists (T-042)
- Glued entry keywords `x{`/`x(` (T-039); one-line dict blocks in general (T-040)

## Acceptance criteria
- [ ] **Failing tests first:** every bug row of the reproduction table, at top level and inside a sub-dict, plus real fixtures copied byte-exact into `tests/releases/` with sources: ESI v2606 `refineFieldDirs/system/blockMeshDict` and `multiWorld2/slab1/system/blockMeshDict`.
- [ ] After the fix both files load; `Cy`, `Dy`, `transform.origin` are present; the `#eval` text is written back unchanged; write 1 == write 2. Add the two files to `tests/test_brace_scan.py` `REAL_OUTCOMES`.
- [ ] `origin (#eval{0.5 * $S} 0 0);` never loads as an empty list: it keeps 3 items, or raises `FoamKitError` with file and line.
- [ ] Every remaining unsupported `#eval` form raises `FoamKitError` with file and line, never `IndexError`.
- [ ] No golden file changes. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- T-040 is rewriting one-line list parsing now. The silent-empty-list row is close to T-040's "one-line lists of dicts lose every item": the T-040 tester should add `origin (#eval{0.5 * $S} 0 0);` as a guard (it must not stay silent). If T-040 already fixes it, keep the test here as a regression guard.
- ESI-only syntax; Foundation does not have `#eval`. ESI v2412+ is a tested release.

## Ranking rationale
**In the backlog after T-043, ahead of T-039.** It blocks 20 ESI tutorial files per tested ESI release, but all fail loudly on real files today (the silent empty list needs a top-level one-line list, which no tutorial has). It ranks above T-039 (6 Foundation 11 files) on file count, and below the ranked seven, which unblock more files or fix crash-on-write.
