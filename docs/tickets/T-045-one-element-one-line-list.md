# T-045: One-element one-line lists: `x (10);` crashes on load, `x (a);` changes on the second write

- **Issue:** [#61](https://github.com/mcgoldba/foamkit/issues/61)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-037 (#49, merged; one-line lists no longer gain an empty item), T-040 (#54, merged; added the strict xfail that has no ticket), T-020 (#27, layout of unedited entries in general; this ticket only fixes the one-element case, which changes type, not just layout), T-039 (#52, glued `x(1);`, out of scope here).
- **Found by:** the T-040 reviewer (PR #60, round 3, note 2). It is pre-existing on main.

## Goal
A one-line list with one item, such as `libs (fieldFunctionObjects);` or `domains (10);`, loads, is written back as a one-line list, and reads back as the same list, so write 1 == write 2. Anything still unsupported raises `FoamKitError` with file and line, never `TypeError` or `AttributeError`.

## Reproduction (planner, 2026-10-30, `t-042-include-inside-a-list` at a9a9447 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| `inGroups (fixed);` | loads as `ofList`. Write 1 is `inGroups    ( fixed);`. That text re-reads as an `ofSplitList`, so write 2 is `inGroups` / `(` / `    fixed` / `);`. Stable from write 2. Same for `x ("a");`, `x ($a);` and inside a sub-dict |
| `libs ("libsampling.so");` (golden-pinned) | `tests/golden/case/controlDict.written.txt:62`, `tests/golden/dicts/pitzDaily/system/controlDict.txt:62` and `tests/golden/dicts/dicts/functionEntries.txt:38` record write 1 as `libs        ( "lib….so");`. `tests/test_golden.py` `test_repeated_writes_converge` documents the drift |
| `x (10);`, `x (1.5);`, `d { domains (10); }` | **fails:** `TypeError: ofSphericalTensor.__init__() got multiple values for argument '_comment'` (whole file) |
| `x ( 10 );`, `x (10 );`, `x ( a );` | load as `ofSplitList`, written multi-line, stable (layout only, T-020) |
| `value uniform (1);` | loads as `ofUniformField(ofSphericalTensor)`; **write fails:** `AttributeError: 'ofSphericalTensor' object has no attribute '_name'`. 0 tutorial occurrences (`uniform (N)`, Foundation 11-12 and ESI v2606 grep) |
| `x (1 2 3);`, `x (a b);` | written multi-line, stable (T-020) |

So the bug is a list written `(` + item + `)` with no space inside: it reads as a one-line `ofList`, and a numeric item is turned into a one-component tensor whose constructor fails.

## Real tutorial occurrences (planner scan, 2026-10-30)
Method: every `FoamFile` file under `tutorials/` (ESI read from git `HEAD`), with comments, strings and `#{ #}` blocks masked; an entry `key (item);` on one line, with whitespace between the key and `(` and no space inside the brackets. Glued `key(item);` is T-039 and is not counted.

| | F11 | F12 | F13 | F14 | ESI v2412 | v2506 | v2512 | v2606 |
|---|---|---|---|---|---|---|---|---|
| numeric item, `TypeError` on load: files (lines) | 8 (8) | 0 | 1 (1) | 3 (5) | 15 (30) | 15 (30) | 17 (34) | 17 (34) |
| other item, write 1 != write 2: files (lines) | 168 (281) | 204 (358) | 255 (504) | 258 (539) | 384 (669) | 387 (672) | 390 (675) | 392 (677) |

- Numeric, loaded and confirmed `TypeError`: F11 `multiphaseEuler/titaniaSynthesis/0/T.particles:44` (`componentColumns    (1);`; F11 `wallBoilingPolydisperse/constant/phaseProperties:228` fails earlier, at line 97, for another reason); F13/F14 `multiphaseEuler/bubbleColumnEvaporatingDissolving/constant/fvModels:40` (`k (1.492e-2);`); ESI v2606 `IO/cavity_parProfiling/system/decomposeParDict:22` (`domains (10);`), `heatTransfer/chtMultiRegionFoam/multiRegionHeater/system/heater/changeDictionaryDict:58` (`thicknessLayers (1e-3);`), `incompressible/icoFoam/cavity/cavity/system/PDRblockMeshDict`.
- Other: mostly `libs (…);`, `inGroups (…);`, `patches ("…");`, `zones (…);`. Confirmed on the real F11 `rotorDisk/system/snappyHexMeshDict` (`tests/releases/foundation-11.rotorDisk.snappyHexMeshDict`): loads, write 1 != write 2.

## Scope
- The one-line list reader (`_parseListValues` / the `ofList` path in `foamkit/types/__init__.py`): a one-item list is read as a list with one item. A numeric item is an `ofInt`/`ofFloat`, not an `ofSphericalTensor`, in a plain `key (N);` entry.
- `ofList.toString`: a one-item list read from one line is written on one line without the extra space, `key (item);`, so it re-reads as the same type.
- `ofSphericalTensor`: the constructor no longer raises `TypeError`, and `uniform (1)` writes back unchanged, or raises `FoamKitError` with file and line.

## Out of scope
- Key/value padding and multi-line layout in general (T-020); `x ( a );` stays multi-line after the first write.
- Glued `key(item);` (T-039)
- Lists with two or more items

## Acceptance criteria
- [ ] **Failing tests first:** every bug row of the reproduction table, at top level and inside a sub-dict, plus real fixtures copied byte-exact into `tests/releases/` with their source recorded: ESI v2606 `IO/cavity_parProfiling/system/decomposeParDict` and Foundation 14 `multiphaseEuler/bubbleColumnEvaporatingDissolving/constant/fvModels`.
- [ ] `inGroups (fixed);`, `libs ("libsampling.so");`, `x ($a);` and `domains (10);` each load as a one-item list whose item has the right type (`ofStr`, `ofVar`, `ofInt`), are written `key (item);` on one line, and write 1 == write 2 == write 3 with the same tree on every re-read.
- [ ] Both real fixtures load and write 1 == write 2. `componentColumns (1)` and `k (1.492e-2)` keep their value text.
- [ ] `value uniform (1);` round-trips unchanged, or raises `FoamKitError` naming file and line. Never `TypeError` or `AttributeError`.
- [ ] The strict xfail `XF_ONE_ELEMENT_LIST` in `tests/test_one_line_blocks.py` (the `rotor` case of `test_real_snappyHexMeshDict_write_1_equals_write_2`) passes with the marker removed. Until then its reason is retagged to start with `T-045:` (the tester does this first). The `test_repeated_writes_converge` docstring in `tests/test_golden.py` no longer cites `libs ("lib.so");` as expected drift.
- [ ] **Golden changes are limited to exactly 3 lines**, each moving toward the source text: `libs        ( "libsampling.so");` becomes `libs        ("libsampling.so");` in `tests/golden/case/controlDict.written.txt:62` and `tests/golden/dicts/pitzDaily/system/controlDict.txt:62`, and the same for `"libutilityFunctionObjects.so"` in `tests/golden/dicts/dicts/functionEntries.txt:38`. The padding before `(` stays (T-020).
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Type change:** `x (10);` becomes a one-item list instead of failing, and a re-read `inGroups (fixed);` stays an `ofList` instead of becoming an `ofSplitList` on the second read. Code that checked the type after a write sees the first-read type. Say so in the commit body.
- **OpenFOAM meaning:** in a field value, `(1)` can be a one-component `sphericalTensor`. In a plain entry OpenFOAM decides the type from the code reading it, so FoamKit cannot know. Keep the value text exact either way; only `uniform`/`nonuniform` values may stay tensors.
- **Golden lines:** the 3 golden lines above change. That is the intended fix (write 1 currently adds a space the source does not have). Any other golden change is a regression.

## Ranking rationale
**In the backlog after T-043 and T-047.** The `TypeError` blocks 1-8 Foundation and 15-17 ESI tutorial files per release, loudly. The second-write drift touches 168-392 files per release, but it is formatting plus a list-type change with no data loss, and it is stable from write 2. It also clears an unticketed strict xfail from T-040.
