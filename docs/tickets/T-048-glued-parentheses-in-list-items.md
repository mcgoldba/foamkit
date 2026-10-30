# T-048: List items with glued parentheses lose them on write (`fields (T mag(U) p);` becomes `T mag U p`)

- **Issue:** [#64](https://github.com/mcgoldba/foamkit/issues/64)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-039 (#52, a **keyword** glued to its bracket, `fields(p U);`; its Step 1 records OpenFOAM's word-token rule, which this ticket reuses for list **items**), T-042 (#57, `#includeFunc f(a)` inside a list; same item parser), T-049 (`N{…}` items), T-020 (list layout).
- **Found by:** the planner while checking the T-040 review findings (PR #60). It is pre-existing on main.

## Goal
A list item written with parentheses attached, such as `mag(U)`, `div((I*interpolate(phi)))` or the blockMesh point in `arc 10 11(0.07 -0.07 1)`, loads as OpenFOAM reads it and is written back with its parentheses. Anything still unsupported raises `FoamKitError` with file and line; parentheses are never silently dropped.

## Reproduction (planner, 2026-10-30, `t-042-include-inside-a-list` at a9a9447 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| `fields ( p mag(U) );` (top level or in a sub-dict) | **silent corruption:** items `p`, `mag`, `U`; written `p` / `mag` / `U`. OpenFOAM then samples fields `mag` and `U` instead of `mag(U)` |
| multi-line list with `mag(U)` and `div(phi,U)` items | **silent corruption:** written `mag` / `U` / `div` / `phi,U` |
| `x ( 4(0 1 2 3) 4(4 5 6 7) );` (counted list, one-line or multi-line) | **silent corruption:** 10 flat integers, the inner lists are gone |
| `x ( a(0 1) );` | written `a` / `0` / `1` |
| `fields (mag(U));` | loads as `ofList ['mag(U']`, written `fields      ( mag(U);`; **re-read fails** with `IndexError` |
| `x ( 4 (0 1 2 3) );`, `edges ( arc 0 1 (0 0 0) );` (with a space) | load as `4`, `(0 1 2 3)` and round-trip |

## OpenFOAM semantics
- A word token may contain balanced parentheses (`ISstream` word rule; T-039 Step 1 records the source), so `mag(U)`, `div(phi,U)` and `columnAverage:columnAverage(UMean)` are **one word** each.
- A number ends at `(`, so `11(0.07 -0.07 1)` is the number `11` followed by a list, the same as `11 (0.07 -0.07 1)`. In a `List<List<T>>`, `4(0 1 2 3)` is a counted list. Either way the parentheses are structure that must be kept.

## Real tutorial occurrences (planner scan, 2026-10-30; `FoamFile` files under `tutorials/`, comments, strings, `#{ #}` blocks and `#includeFunc` arguments masked, `.m4` templates skipped; ESI from git `HEAD`)
| glued item inside a list | F11 | F12 | F13 | F14 | ESI v2412-v2606 (each) |
|---|---|---|---|---|---|
| `word(…)`: files (items) | 2 (2) | 2 (2) | 1 (1) | 1 (1) | 3 (4) |
| `N(…)`: files (items) | 0 | 0 | 0 | 1 (1) | 0 |

Each one loaded and confirmed: it loads, and the written file has lost the parentheses.
- F11/F12 `fluid/shockTube/system/sample:36` and `shockFluid/shockTube/system/sample:36`, F13 `shockFluid/shockTube/system/sample:36`, ESI `compressible/sonicFoam/laminar/shockTube/system/sample:22`: `fields (T mag(U) p);`.
- F14 `multiRegion/CHT/hotWire/system/controlDict:55`: `cacheTemporaryObjects ( div((I*interpolate(phi))) );`, written `div` / `(I*interpolate phi)`.
- F14 `fluid/concentricCylinders/system/blockMeshDict.orig:56`: `arc 10 11(0.07071067811 -0.07071067811 1)`, written as 5 flat items, so blockMesh no longer gets an arc point.
- ESI `heatTransfer/chtMultiRegionTwoPhaseEulerFoam/solidQuenching2D/system/controlDict:96` (`fields ( reactingEulerHtcModel(T.liquid) );`) and `incompressible/pimpleFoam/LES/periodicHill/transient/system/controlDict:116-117` (`columnAverage:columnAverage(UMean)`).
- Not counted: `constant/polyMesh/cells` and `faces` in Foundation `airFoil2D` (53,786 counted lists). FoamKit skips `polyMesh` directories.

## Scope
- The list item tokenizer (`_parseList` / `_parseListValues` in `foamkit/types/__init__.py`) for one-line and multi-line lists:
  - a word with balanced parentheses attached is one item, kept verbatim;
  - a number directly followed by `(` is the number then a sub-list, like the spaced form today;
  - an unbalanced glued item raises `FoamKitError` naming file and line.
- `fields (mag(U));`: never writes text that cannot be read back.

## Out of scope
- Keywords glued to their bracket (T-039)
- `N{…}` uniform-list items (T-049); `#includeFunc` in lists (T-042); `#eval` in lists (T-044)
- Keeping the original layout of the list (T-020)

## Acceptance criteria
- [ ] **Failing tests first:** every bug row of the table, at top level and inside a sub-dict, one-line and multi-line, plus real fixtures copied byte-exact into `tests/releases/` with their source recorded: Foundation 13 `shockFluid/shockTube/system/sample`, Foundation 14 `multiRegion/CHT/hotWire/system/controlDict` and Foundation 14 `fluid/concentricCylinders/system/blockMeshDict.orig`.
- [ ] `fields (T mag(U) p);` loads as 3 items (`T`, `mag(U)`, `p`); the written text keeps `mag(U)`; write 1 == write 2 and re-reads to the same items. Same for `div(phi,U)`, `div((I*interpolate(phi)))` and `columnAverage:columnAverage(UMean)`.
- [ ] `x ( 4(0 1 2 3) );` keeps the inner list (as `4` then `(0 1 2 3)`, or as one counted-list item); it never becomes flat integers.
- [ ] The 3 real fixtures load, keep every parenthesis, and write 1 == write 2. In the blockMesh fixture, the item after `arc 10 11` is the list `(0.07071067811 -0.07071067811 1)`.
- [ ] `fields (mag(U));` round-trips, or raises `FoamKitError` with file and line; never `IndexError` on re-read.
- [ ] No golden file changes. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Item count changes:** a list that held `mag`, `U` now holds `mag(U)`. Code that indexed list items by position sees fewer items. It is the bug fix; say so in the commit body.
- T-042 is changing the same item parser now. Start after T-042 merges.
- Do not change how `hex (0 1 …) (10 10 1)` or `arc 0 1 (0 0 0)` (with spaces) are read; the existing tests and `helmholtzResonance`/`pitzDaily` blockMesh fixtures guard this.

## Ranking rationale
**Second, right after T-042.** It silently changes the meaning of stock tutorials in every tested release: a `sample` or `controlDict` written by FoamKit asks OpenFOAM for the wrong fields, and a blockMesh arc loses its point. It is silent, unlike every other open load bug, and the fix is small and in the list code T-042 is already touching.
