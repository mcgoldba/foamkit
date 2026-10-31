# T-052: Entry values made of two or more lists (`transform (1 0 0 0 1 0 0 0 1) (0.5 0.45 0.1);`) load and round-trip

- **Issue:** [#69](https://github.com/mcgoldba/foamkit/issues/69)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M
- **Related:** T-014 (#21, `ofNamedDimension` drops the value; the wrong type here is the same class), T-045 (#61, one-element lists), T-048 (#64, list item parser), T-027 (#38, `#calc`, which blocks the Foundation files below before they reach this bug).
- **Found by:** the T-042 reviewer (PR #66, round 4 note 4: "`a 1; b (…); c (1 2) (3 4);` at end of file still raises a bare `IndexError`"). The planner's reproduction showed it is not tied to the end of the file and that one shape is **silent corruption** of a stock ESI tutorial. Pre-existing on main.

## Goal
An entry whose value is two or more parenthesised groups, such as the rigid-body `transform (tensor) (vector);`, loads with every value and is written back unchanged. Any shape still unsupported raises `FoamKitError` naming file and line; it is never turned into a different type, a new entry or a bare `IndexError`.

## Reproduction (planner, 2026-10-30, `t-048-glued-parentheses-in-list-items` at 693d945 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| `transform (1 0 0 0 1 0 0 0 1) (0.5 0.45 0.1);` (top level or in a sub-dict) | **silent corruption:** loads as `ofNamedDimension(name='transform', dimensions=[0, 0, 0, 1, 0, 0, 0])`, written `transform   [0 0 0 1 0 0 0];`. The tensor and the vector are gone |
| `transform (1 2 3 4 5 6 7 8 9) (0.5 0.45 0.1);` | same: written `transform   [2 3 4 5 6 7 8];` |
| `c` / `(` / `1 2` / `)` / `(` / `3 4` / `);` (multi-line) | **silent corruption:** `c` gets `(1 2)` and a **new entry `unnamed_1`** gets `(3 4)`; both are written |
| `c (1 2) (3 4);`, `c (1 2)(3 4);`, `c (a b) (c d);`, `c (1 2 3) (4 5 6) (7 8 9);`, `transform (1 0 0 0 1 0 0 0 1) (2.929541 0 0.2);` | bare `IndexError: list index out of range` (`_parseListValues`, reads past the end of the file looking for a `)`), with or without entries after it, also inside a sub-dict |
| `c 2(1 2) 2(3 4);` | bare `ValueError: not enough values to unpack` (`_parseSingleLineEntry`) |
| `c (1 2) (3 4)` / `;` (`;` on the next line) | bare `AttributeError: 'ofWord' object has no attribute '_name'` |
| `t (` / `1 2` / `)` / `(3 4);` (first list multi-line, second on the closing line; also in a sub-dict) | **silent corruption** (T-048 review round 2, note 2; same on main and after T-048): the second list is written as an orphan entry `(3 4);`. Real files: F11-F14 `planingHullW3/constant/dynamicMeshDict`, where the translation `(0.586 0 0.156)` is orphaned |
| `box (0 0 -1) (0.1461 0.292 1);`, `c ((1 2) (3 4));` | OK, round-trip (must not change) |

OpenFOAM reads such an entry as a token stream; the code that looks the keyword up decides the types (`transform` is a `spatialTransform`: tensor then vector). Both forms are valid in every tested release.

## Real tutorial occurrences (planner scan, 2026-10-30; one-line `key (…) (…)…;` entries other than two 3-component groups; ESI from git `HEAD`)
| | F11 | F12 | F13 | F14 | ESI v2412-v2606 (each) |
|---|---|---|---|---|---|
| files | 4 | 4 | 4 | 5 | 3 (4 lines) |

All hits are `transform (1 0 0 0 1 0 0 0 1) (x y z);` in `constant/dynamicMeshDict`. Loaded on this branch:
- **ESI v2412-v2606 `multiphase/interFoam/RAS/floatingObject/constant/dynamicMeshDict:59`: loads and is written as `transform [0 0 0 1 0 0 0];`** (silent corruption of a stock tutorial in every tested ESI release).
- F11-F14 `incompressibleVoF/DTCHullMoving` and `DTCHullWave` `constant/dynamicMeshDict`, ESI `multiphase/interFoam/RAS/DTCHullMoving` and `multiphase/overInterDyMFoam/rigidBodyHull/background`: bare `IndexError`.
- F11-F14 `incompressibleVoF/floatingObject`, `floatingObjectWaves` and F14 `floatingBeam`: fail earlier on `#calc` (T-027); after T-027 they reach this bug.

## Scope
- Entry value parsing in `foamkit/types/__init__.py` (`_parseSingleLineEntry`, `_parseListValues`, and the multi-line entry path that creates `unnamed_<n>`): a value of two or more top-level `( … )` groups, one-line or across lines, is one entry holding all groups in order, written back as written.
- The dimension-set detection must not match a parenthesised value (`[…]` only).
- Shapes not handled raise `FoamKitError` with file and line.

## Out of scope
- Interpreting `transform` as a typed `spatialTransform`
- The `nu nu [dims] value` value loss (T-014)
- One-element lists (T-045); layout of the written entry (T-020)

## Acceptance criteria
- [ ] **Failing tests first:** every row of the table, at top level and inside a sub-dict, plus real fixtures copied byte-exact into `tests/releases/` with their source recorded: ESI v2606 `multiphase/interFoam/RAS/floatingObject/constant/dynamicMeshDict` and Foundation 14 `incompressibleVoF/DTCHullMoving/constant/dynamicMeshDict`.
- [ ] `transform (1 0 0 0 1 0 0 0 1) (0.5 0.45 0.1);` loads with both groups and every number; the written text has the same tokens; write 1 == write 2 and re-reads to the same value. Same for `c (1 2) (3 4);`, `c (a b) (c d);` and three groups.
- [ ] The multi-line form never creates an `unnamed_<n>` entry: it is one entry `c`, or `FoamKitError` with file and line.
- [ ] No input in the table raises `IndexError`, `ValueError`, `AttributeError` or `TypeError`; each round-trips or raises `FoamKitError` naming file and line (errors never pass silently).
- [ ] Both fixtures load and write 1 == write 2; in the ESI fixture the written `transform` line has the tensor and the vector.
- [ ] `box (0 0 -1) (0.1461 0.292 1);` and `c ((1 2) (3 4));` behave as today. No golden file changes. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Type change:** `box (…) (…)` currently loads as some type that users may index; keep it unless the tests show it loses data, and say so in the commit body if it changes.
- **Shared code:** `_parseListValues` is also changed by T-048 (in progress). Start after T-048 merges.
- `hex (…) (…)` inside `blocks ( … )` is a list item, not an entry value; the blockMesh fixtures guard it.

## Ranking rationale
A stock ESI tutorial is silently corrupted on write in every tested ESI release (the rigid body loses its transform), and 10 more stock files per release set fail with a bare `IndexError`. Silent corruption of stock files outranks loud load failures, as for T-048 and T-046.
