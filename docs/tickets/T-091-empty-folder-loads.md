# T-091: a case with an empty folder (`constant/triSurface/`, `0/`, `logs/`) loads instead of crashing `init` with a bare `UnboundLocalError`

- **Issue:** [#125](https://github.com/mcgoldba/foamkit/issues/125)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (the fix is one moved line in `FolderParser.makeOFFolder` plus a `mkdir` for each folder in the case writer)
- **Related:** T-089 (#123; one time-name rule. It touches the same folder-name code in `makeOFFolder` and found this bug), T-020a (#27; unedited files are written from source. An empty folder has no files, so it needs nothing from T-020a), and the other bare-exception crashes in `init`: T-089 (`TypeError` for `1e-05`/`-180` time directories), T-079 (#106; top-level `print;`), T-027 (#38; value-position `#calc`), T-031 (#42; `#include "f"; /* c */`).
- **Depends on:** none. It conflicts textually with T-089 in `makeOFFolder` (lines 612-630), so whichever lands second rebases.

## Goal
`fkf.init` on a case with an empty folder anywhere in its parsed tree loads, and the empty folder becomes an `ofFolder` with no entries. `case.write()` never silently drops a folder that is in the model, even when the case is written to a new location.

## Today (planner, reproduced on 401bb6c = `origin/main`, 2026-11-10)
Cause, confirmed in the code: `FolderParser.makeOFFolder` (`foamkit/types/__init__.py`) assigns `internalNames = {}` **inside** the `for obj in ….iterdir()` loop (line 612) and reads it after the loop (line 667). A directory with no entries at all never runs the loop body, so line 667 raises `UnboundLocalError: cannot access local variable 'internalNames'`. A folder with any entry, even one that is skipped (`.gitkeep`, `*.eMesh`, a non-dictionary file), runs the loop and loads. The same misplacement also resets the dict on every pass, so only the **last** entry's true name is restored at line 670. Example: in a folder holding `p(1)/` and `q(2)/`, both get `_name = None`. Folder `_name` is not used on write, so nothing is written wrongly today.

Probe: one change per copy of `tests/fixtures/pitzDaily`, then `fkf.init(case)`. For cases that load, the probe also ran `case.write()` in place, `case.setName('<new>')` + `case.write()` (written to a new location), and `fkf.load(case)` (the `.params` cache). It also ran `fkf.cloneCase(case, dest)` on every shape.

| Shape | `init` | Write (in place / new location) | Cache | `cloneCase` |
|---|---|---|---|---|
| empty `constant/` | **bare `UnboundLocalError`** (`__init__.py:667`) | - | - | copies the empty dir |
| empty `system/` | **bare `UnboundLocalError`** (after an INFO "not an OpenFOAM case") | - | - | `FoamKitError` "not a valid OpenFOAM case" |
| empty `system/include/` | **bare `UnboundLocalError`** | - | - | copies it |
| empty `0/` | **bare `UnboundLocalError`** | - | - | copies it |
| empty `0.5/` (second time dir) | **bare `UnboundLocalError`** | - | - | skipped (non-`0` time, by design) |
| empty `0.orig/` | **bare `UnboundLocalError`** | - | - | copies it |
| empty `constant/triSurface/` | **bare `UnboundLocalError`** | - | - | skipped (`includeTriSurface=False`, by design) |
| `constant/a/` holding only an empty `b/` | **bare `UnboundLocalError`** | - | - | copies both |
| empty `logs/` or `dynamicCode/` (top level) | **bare `UnboundLocalError`** | - | - | copies it |
| empty `postProcessing/`, empty `postProcessing/probes/0.5/` | loads (top-level `postProcessing` is skipped, not in the model) | dir kept / not created | not in cache | skipped (by design) |
| empty `processor0/`, empty `processor0/constant/` | loads (skipped, not in the model) | kept / not created | not in cache | skipped |
| empty `constant/polyMesh/` | loads (`polyMesh` is skipped) | kept / not created | not in cache | skipped |
| empty `.cache/` (hidden, top level) | loads (skipped) | kept / not created | not in cache | copies it |
| `constant/x/` holding only `.gitkeep` | loads: `case.constant.x` is an `ofFolder` with no entries | kept / **`constant/x` not created** | round-trips as `ofFolder` | copies it |
| `constant/x/` holding only `f.eMesh` + `notes.txt` | loads, same as above | kept / **not created** | round-trips | copies it |
| `constant/x/` holding only `y/transportProperties` | loads | kept / created (the dict file's write makes it) | round-trips | copies it |

So every empty folder that the parser walks crashes the whole load. The skipped ones (`polyMesh`, top-level `postProcessing`, `processor*` and hidden dirs) do not crash. A folder that loads with no entries is silently **left out** when the case is written to a new location: the writer (`_writeCaseObj` in `ofCase.write`) only creates a directory as the parent of a dictionary file it writes. An in-place write deletes nothing, so the folder stays on disk there.

**Frequency:** tutorials cannot show this, because git does not track empty directories (`git ls-files` lists files only), and a git clone never contains one. Cases that FoamKit is pointed at do have them, from tarballs, rsync copies, scripts that `mkdir` ahead of time, and cleaned run directories. The three most common empty folders in OpenFOAM work load fine today because their parents are skipped: `constant/polyMesh/` before `blockMesh`, an empty `postProcessing/`, and `processorN/constant/`. The realistic crashing ones (plausible, not measured) are an empty `constant/triSurface/` or `constant/geometry/` (snappyHexMesh set-ups before the surface is copied in), a `0/` created or emptied before its fields are written, an empty `system/include/`, and user folders at the case root such as `logs/`, `results/` or an emptied `VTK/`.

## Design (planner, 2026-11-10)
- **Option A (recommended; shown representable):** an empty folder loads as an `ofFolder` with no entries, as a `.gitkeep`-only folder already does today. Fix: initialise `internalNames` once, before the loop, so every renamed entry keeps its true name, not just the last one.
  - The case object: `case.constant` (or `case.t_0`, `case.constant.triSurface`, `case.logs`) is an `ofFolder`; `dict(folder)` holds only `_path` and `_type`; reading a missing file raises `AttributeError`, as for any folder. `len(folder)` raises `TypeError` for every `ofFolder` today; this ticket does not add `len`.
  - Empty `system/`: `init` keeps its existing INFO line "not an OpenFOAM case" and loads. Turning that into an error is T-023's question, not this ticket's.
  - **Writer:** `ofCase.write()` creates `case._path / folder._path` (`mkdir(parents=True, exist_ok=True)`) for every `ofFolder` in the model. That way a folder with no dictionary files is recreated when the case is written to a new location. Note that `ofFolder._path` is relative to the case (`constant/x`), while `_writeCaseObj` uses it as `loc`.
  - **Cache:** nothing new. The `.params/_case.json` entry `{"_path": …, "_type": "ofFolder"}` already round-trips through `fkf.load` (`initOFFolder`), as the `.gitkeep` row shows. Acceptance pins it.
  - **T-020a:** nothing. An empty folder has no files to write from source.
- **Option B (fallback, only if A grows beyond S):** `makeOFFolder` raises `FoamKitError` naming the empty folder's path (no traceback). It is loud, but it would still block loading the whole case over a folder with nothing in it, so the planner recommends A.

## Scope
- `foamkit/types/__init__.py`: `FolderParser.makeOFFolder` (`internalNames`), and `_writeCaseObj` in `ofCase.write` (the `mkdir` per folder).
- Tests: a new `tests/test_empty_folders.py` with one test per shape in the table, each built under `tmp_path` from a copy of `tests/fixtures/pitzDaily`.

## Out of scope
- Which directories `init` skips (`polyMesh`, `postProcessing`, `processor*`, hidden) and which `cloneCase` skips. Those are unchanged.
- Copying hidden or non-dictionary files when a case is written to a new location. The model holds no data for them; `cloneCase` is the copy tool.
- Time-directory naming (`1e-05`, `-180`, `nan`) is T-089.
- An `ofFolder.__len__`, and adding files or folders to an existing folder (the `TODO` on `_ofFolderBase`).

## Acceptance criteria
- [ ] **Failing tests first:** each crashing row of the table (empty `constant/`, `system/`, `system/include/`, `0/`, `0.5/`, `0.orig/`, `constant/triSurface/`, `constant/a/b/`, `logs/`) fails on `main` with `UnboundLocalError`. The `.gitkeep` and `f.eMesh`/`notes.txt` rows fail on "not created at the new location".
- [ ] `fkf.init` loads each crashing shape; the empty folder is an `ofFolder` whose `dict()` has no keys other than `_path`, `_type` (and `_name` if set), reached as `case.constant`, `case.system`, `case.system.include`, `case.t_0`, `case.t_0_5`, `case.t_0_orig`, `case.constant.triSurface`, `case.constant.a.b`, `case.logs`.
- [ ] The rows that load today (`postProcessing`, `processor0`, `constant/polyMesh`, `.cache`, `.gitkeep`, skipped files, `y/transportProperties`) load exactly as before: the same attributes, and skipped folders are still absent.
- [ ] `case.write()` in place leaves every empty folder on disk and writes the same files as for the same case without the empty folder. After `case.setName('<new>')` + `case.write()`, every `ofFolder` in the model exists under the new path, empty ones included (`constant/triSurface`, `constant/a/b`, `constant/x` with `.gitkeep`).
- [ ] `.params` round trip: after `case.write()`, `fkf.load(case_path)` returns a case whose empty folder is an `ofFolder`, and writing that loaded case to a new location recreates the folder.
- [ ] Renamed entries: in a folder holding `p(1)/` and `q(2)/`, both folders get their true names back (`_name` is `p(1)` and `q(2)`), not only the last one iterated. Dictionary files write to the same paths as before.
- [ ] Every file in `tests/releases/` and `tests/fixtures/pitzDaily` writes the same text as before.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): a case with an empty folder loads instead of crashing init (T-091)`.

## Risks
- **Behaviour change (wanted):** cases that crashed now load. A folder's `_name` now holds its true name for every renamed entry, not just the last one. Folder `_name` is not used on write, but it is saved in the `.params` cache.
- **Writer change:** writing to a new location now creates directories for folders with no dictionary files. An in-place write is unaffected (`exist_ok=True`).
- **T-089 overlap:** both tickets edit `makeOFFolder` near lines 612-630. Whichever lands second rebases; neither changes the other's behaviour.
- **OpenFOAM versions:** none. Empty directories mean the same thing in every distribution.
