# T-043: `keyword #{ … #}` code entries: top-level crash, unknown keywords, one-line form

- **Issue:** [#58](https://github.com/mcgoldba/foamkit/issues/58)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M. If part 3 (the one-line form) turns out to need more than the shared dispatch, split it into its own S ticket and do parts 1-2 here.
- **Related:** T-033 (#44, `#codeStream` writer; it shares `_ofVerbatimCode.toString`); T-016 (directive framework and `OF_VERBATIM_CODE_ENTRIES`); T-035 (`#{ #}` aware scanner); T-028 (`#codeDict`).
- **Found by:** the T-041 tester (PR #56). It is pre-existing on main.

## Goal
An entry whose value is a `#{ … #}` verbatim block loads and is written back unchanged, whatever its keyword, at top level or in a sub-dict, multi-line or on one line. Anything still unsupported raises `FoamKitError` with file and line, never `AttributeError`.

## Reproduction (planner, 2026-10-29, `t-040-one-line-brace-blocks` at 376edf3 + uncommitted tests; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| top-level `codeExecute` / `#{` / `Info<< "hi" << endl;` / `#};` | **fails on read:** `AttributeError: 'ofCodeExecute' object has no attribute '_name'`, in `DictFileParser.readDictFile` (`foamkit/types/__init__.py:4411`: `value._name` is read before the `hasattr(value, '_name')` check; `_ofVerbatimCode` is an unnamed type) |
| top-level `codeInclude`, `codeOptions`, `codeLibs` `#{ … #}` | same `AttributeError` (`'ofCodeInclude' …`) |
| the same `codeExecute` / `codeOptions` block inside a sub-dict | loads and round-trips, stable |
| top-level or sub-dict `code` / `#{ … #};` | **fails:** `FoamKitError: Invalid syntax on line N`. `code` is not in `OF_VERBATIM_CODE_ENTRIES` (which holds `codeContext`, `codeData`, `codeEnd`, `codeExecute`, `codeInclude`, `codeLibs`, `codeOptions`, `codeRead`, `codeWrite`, `localCode`) |
| `evaluate #{ … #};`, `expression #{ … #};`, `fieldMask #{ … #};` in a sub-dict | same "Invalid syntax" |
| one-line `codeExecute #{ sleep(1); #};` in a sub-dict | **fails:** `FoamKitError: Unknown directive '#' on line N` |

In OpenFOAM, `#{ … #}` is a verbatim-string token that can be the value of any keyword; the keyword list is not fixed.

## Real tutorial occurrences (planner, 2026-10-29)
Method: every `FoamFile` dictionary under `tutorials/` containing `<word> #{` was loaded and written with FoamKit (60 s timeout per file). Script: `codeload.py` in the session scratchpad.

- **Top level (part 1):** Foundation 11-14: **0**. ESI v2412-v2606: 1 file each, `mesh/moveDynamicMesh/twistingColumn/constant/dynamicMeshDict` (`codeInclude`, `localCode`, `code` at lines 23, 28, 61). It fails with `AttributeError: 'ofCodeInclude' object has no attribute '_name'` on v2606.
- **Keyword not in the registry (part 2), "Invalid syntax":**
  - F11: `incompressibleFluid/pipeCyclic/0/U` (`code`), `incompressibleFluid/pitzDailyPulse/0/U` (`code`);
  - F14: 5 files: `pipeCyclic/0/U` and `fluid/blockedChannel/constant/alphaInternalField`, `incompressibleFluid/blockedChannel/constant/alpha.volume` (`evaluate`, new in F14), `moodyChart/constant/gradP` and `pitzDailyPulse/0/U` (`code`);
  - ESI v2606: 9 files, e.g. `incompressible/simpleFoam/pipeCyclic/0.orig/U` (`code`), `combustion/XiEngineFoam/kivaTest/system/controlDict` (`code`), `compressible/rhoSimpleFoam/squareBendLiq/0.orig/T` (`expression`), `TJunctionAverage/system/setExprFieldsDict` (`expression`, `fieldMask`), `interFoam/RAS/damBreakLeakage/system/createBafflesDict`.
- **One-line form (part 3), "Unknown directive '#'":** ESI v2606: 7 files, e.g. `IO/cavity_parProfiling/system/controlDict:59` (`codeExecute #{ sleep(1); #};`), `TJunctionAverage/system/setExprBoundaryFieldsDict:26`, `turbineSiting/system/setExprFieldsDict:23` (`expression #{ … #};`). Foundation 11-14: 0 found.
- Other failures in the same files belong to other tickets: `#codeStream` blocks ("Could not find functionEntry bracket type", F11/F14 `resources/blockMesh/*`, `potentialFoam/cylinder`; T-033/T-016 area), `#codeDict` (T-028), scoped `$` (T-030), value-position `#calc` (T-027), `#eval` (T-044). The tester records which ones this ticket unblocks.

## Scope
1. **Top level:** the top-level entry insertion in `DictFileParser.readDictFile` handles `_ofVerbatimCode` values the way the sub-dict path does (check `_name` safely; key by `vcType`). Same keys and duplicates handling as sub-dicts.
2. **Any keyword:** a keyword followed by `#{` (same line or next line) is a verbatim code entry. Either keep the registry and add a generic verbatim-code type for unregistered keywords, or replace the registry lookup with "next token is `#{`". Decide in the PR. A new public class name is an API addition: name it in the PR body for the maintainer.
3. **One-line form:** `keyword #{ … #};` on one line, using T-035's scanner to find `#}`.
- Writing: an unedited entry is written back unchanged (keyword, `#{` placement, code text, `#};`). Repeated writes are stable.

## Out of scope
- `#codeStream` writer churn and brace placement (T-033)
- `#codeDict` / `#word` (T-028)
- Running or validating the code

## Acceptance criteria
- [ ] **Failing tests first:** every row of the reproduction table, at top level and in a sub-dict, plus the real fixtures (byte-exact, with sources): ESI v2606 `twistingColumn/constant/dynamicMeshDict`, Foundation 14 `incompressibleFluid/pipeCyclic/0/U` (`evaluate`), Foundation 11 `pitzDailyPulse/0/U` (`code`, `codeInclude`) and ESI v2606 `IO/cavity_parProfiling/system/controlDict` (one-line).
- [ ] After the fix, each loads with every entry, the code text is unchanged, and write 1 == write 2. The top-level `codeExecute` guard comment in `tests/test_entries_per_line.py` (the `CODE_BODY` note, which uses a sub-dict because of this bug) is updated, and a top-level variant of those code-block tests is added.
- [ ] A `#{` with no closing `#}` raises `FoamKitError` naming file and line (T-035 behaviour unchanged).
- [ ] Existing `#{ #}` tests and the goldens (`tests/golden/dicts/dicts/functionEntries.txt`) are unchanged.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- `_ofVerbatimCode.toString` and its re-indentation are shared with `#codeStream` (T-033). Do not change sub-dict output; the goldens guard it. Land T-043 and T-033 one after the other, not in parallel.
- Treating any `word #{` as code must not catch `#{` inside strings or comments (T-035 scanner) or directive bodies such as `#calc #{ … #}` (T-016 tests cover these).
- Foundation and ESI use different keyword sets (`evaluate` is F14-only; `expression`/`fieldMask` ESI-only), which is why the generic rule is preferred over growing the registry.

## Ranking rationale
**Seventh, after T-029** (T-040, T-042, T-027, T-026, T-030, T-029, T-043). The top-level crash itself hits only one ESI tutorial (twistingColumn), but the same entry family fails in 2 (F11) to 5 (F14) Foundation files and about 17 ESI v2606 files, including stock coded boundary conditions (`pipeCyclic`, `pitzDailyPulse`). All of these fail loudly (no silent loss), so it ranks below the silent-loss and crash-on-write tickets and below T-027 (100+ files per Foundation 13/14 release). The `AttributeError` (not a `FoamKitError`) breaks the clean-error rule, which puts it ahead of the remaining backlog.
