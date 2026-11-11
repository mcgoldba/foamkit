# T-092: a key the user wrote as `unnamed_3` keeps its name, and a keyword-less entry never overwrites another entry

- **Issue:** [#127](https://github.com/mcgoldba/foamkit/issues/127)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M (one idea, but it touches the three key generators in the reader, about 25 writer call sites that decide "print the key or not" through `printNameStr`/`_isGeneratedKey`, the `.params` cache and the T-020a fingerprint, and it changes one T-084 test. It is one focused session; it is not split because a marker that the writers do not all read would be worse than the name rule.)
- **Related:** T-084 (#112, PR #126; bare lists are written without the generated key. This ticket replaces how T-084's writers recognise that key), T-090 (#124; one-line bare lists, same reader path), T-079 (#106; top-level keyword-only entries, same `ofDict.__setitem__`), T-080 (#107; counted bare lists are read as the key `t_2`, not `unnamed_<n>`; unchanged here), T-020a (#27; the edit fingerprint must see the marker).
- **Depends on:** T-084 (#112) merged: this ticket rewrites the writer checks that T-084 adds.

## Goal
A key that is in the file, even one spelled `unnamed_<n>`, is always written back with its name, and an entry with no keyword (bare list, bare `{…}` block) is never stored under a key that another entry already holds, so no entry is silently dropped, overwritten or renamed.

## Today (planner, reproduced on 8aa540d = T-084, 2026-11-10)
The reader gives a keyword-less entry the key `unnamed_<n>` (`UNNAMED_TAG`, `foamkit/types/__init__.py:78`; generators at lines 2404, 2424 and `_NoneKey` at 2500, numbered by a per-dict counter `_nUnnamed` that ignores keys already in use). The writers decide "this key was generated, do not print it" from the **name pattern** alone: `_isGeneratedKey(name)` (line 90, regex `unnamed_[0-9]+$`) in `printNameStr` (about 25 callers), `ofList._closing` (1844), `ofSplitList.toString` (1863) and `ofDict.toString` (2589, 2597). Probe: `DictFileParser(path).readDictFile()` on each body after the pitzDaily header, then `toString()` (unedited, T-020a) and `toString(_preserve=False)` (regenerated). Multi-line bare lists are used for the collision rows, because a one-line bare list raises (T-090).

| Case | Result | Silent? |
|---|---|---|
| `a 1;` / `unnamed_3 (1 2 3);` / `b 2;`, regenerated | written `(1 2 3);` with no key: the name is dropped | **yes** |
| same, edited after `init` → `save` → `load` (append an item), `case.write()` | written `( 1 2 987654 );` with no key | **yes** |
| `unnamed_2 5;` (scalar), regenerated | written `5;` | **yes** |
| `unnamed_2 { x 1; }` (sub-dict), regenerated | written `{ x 1; }` | **yes** |
| `unnamed_1 (1 2);` then a bare multi-line list `( 3 4 )` | one key `unnamed_1` = `(3 4)`; `(1 2)` is gone, **also from the unedited write** | **yes, data loss** |
| bare `( 3 4 )` then `unnamed_1 (1 2);` | one key `unnamed_1` = `(1 2)`; `(3 4)` is gone, unedited write too | **yes, data loss** |
| `unnamed_1 7;` then bare `( 3 4 )` / bare list then `unnamed_1 7;` | the later one wins; the other is gone | **yes, data loss** |
| `unnamed_2 (1 2);` then two bare lists | keys `unnamed_2` = 2nd bare list, `unnamed_1` = 1st; `(1 2)` is gone | **yes, data loss** |
| `sub { unnamed_1 (1 2); ( 3 4 ) }` | `sub.unnamed_1` = `(3 4)`; `(1 2)` gone on regenerate (the unedited top-level `sub` is still written from source) | **yes, data loss** |
| `unnamed_1 (1 2);` then a bare `{ q 1; }` | one key `unnamed_1` = the dict; the list is gone, unedited write too | **yes, data loss** |
| legacy file written by FoamKit before T-084: `unnamed_1 ( (0 0 0) );` | read as the named entry `unnamed_1`; unedited write keeps the keyword; regenerated write drops it (the T-084 "repair") | the repair is silent, by design of T-084 |
| `my_unnamed_x 5;`, `my_unnamed_x { x 1; }`, `unnamed_x { … }` (file) | named entries, written with their names; no warning | no (correct) |
| `d['unnamed_5'] = 3` or `d.unnamed_5 = 3` (code) | written `{ 3 }`: the key the user gave is dropped | **yes** |
| `d.update(fkt.ofInt(name='unnamed_7', value=1))`, also `name='my_unnamed_x'` | WARNING "Found reserved name in dictionary key.", then a bare `UnboundLocalError` (`name_` never set in the `elif UNNAMED_TAG in itemName` branch, line 2405; the substring test also catches `my_unnamed_x`) | no, but a bare crash |

The `.params` cache keeps the entries and their keys; generated-ness is "remembered" only because it is recomputed from the name, so after `load` a user key `unnamed_3` is treated as generated too (row 2). `UNNAMED_TAG` is used nowhere outside `foamkit/types/__init__.py`.

**Frequency:** 0. `git grep -i unnamed -- tutorials` finds nothing in the Foundation 11 and Foundation 14 clones. A file only holds a key `unnamed_<n>` if a user chose that name or an older FoamKit wrote it (every release before T-084 wrote the generated key on a regenerated write). The collisions need such a key plus a keyword-less entry in the same dict.

## Design (planner, 2026-11-10)
- **Option A (recommended): a reader-side marker.**
  - When the reader stores an entry under a key it generated, it sets a marker on the **entry**: a class attribute `_keyless = False` on the base type, set to `True` on the instance by the reader. This is the pattern `ofList._semicolon` already uses: a plain JSON boolean, set by `setattr` from the cache loader (`load.py`, every `_` key of a cached object is `setattr` on a no-arg instance), and add `'_keyless'` to the `_fpNames` base list so the T-020a fingerprint sees it for list items too (`ofDict` entries are fingerprinted from `vars`). An attribute on the entry moves with the entry; a set of keys on the parent dict would need its own cache field and would go stale on rename.
  - Every writer check reads the marker, never the name: `printNameStr`, `ofList._closing`, `ofSplitList.toString`, `ofDict.toString`. `_isGeneratedKey` is deleted (it is private; no alias needed).
  - **Free key:** the generated key is the next `unnamed_<n>` **not already in that dict** (skip taken numbers). That fixes every collision where the user's key comes first.
  - **Late collision:** when a named entry arrives whose key is already held by a generated (marked) entry, the reader raises `FoamKitError` naming the file and both line numbers ("`unnamed_1` on line 20 is also the key FoamKit gave the keyword-less entry on line 17; rename it"). Renaming the generated entry instead would change what `d.unnamed_1` returns depending on what comes later in the file, and keeping the order of `vars(d)` while renaming needs a rebuild of the dict; with 0 real files, the loud error is the safe choice. (A later ticket can rename if a real file needs it.)
  - **Code path:** `d['unnamed_5'] = 3`, `d.unnamed_5 = 3` and `d.update(ofInt(name='unnamed_7'))` make ordinary named entries (no marker), written `unnamed_5 3;`. The reserved-name branch at line 2405 goes: an `unnamed_` substring is no longer reserved, and the name `_name` raises `FoamKitError` (today both crash with a bare `UnboundLocalError`).
  - **Legacy files (case 3):** a key `unnamed_<n>` in a file is kept and written with its name, whatever wrote it. A file cannot tell whether a user or an older FoamKit wrote `unnamed_1`, so "repairing" it is a guess that drops a real key in the user case; writing back what the file says is the safe default. To stay loud about the old bug, the reader logs one WARNING per file when a **top-level** key matches `unnamed_<digits>` and its value is a list or a bare dict: "`unnamed_1` (line N) may be a keyword an older FoamKit wrote; OpenFOAM does not expect it in a bare-list file; delete the keyword if so." Nothing is changed. T-084's test `test_a_file_written_with_the_keyword_is_regenerated_without_it` is rewritten to the new rule: the regenerated text keeps `unnamed_1`, and the warning is logged once.
- **Option B:** any key `unnamed_<n>` in a file raises `FoamKitError` naming the file and line. Simple and collision-free, but it blocks loading every file an older FoamKit wrote, so the planner does not recommend it.
- **Option C:** keep the name pattern and only pick free numbers. It fixes the collisions where the user's key comes first, but a user key `unnamed_3` is still written without its name (rows 1-4) and the late collision still overwrites; it leaves silent loss in place, so it is not recommended.

## Scope
- `foamkit/types/__init__.py`: `UNNAMED_TAG` generators (`ofDict.__setitem__` ~2402-2428, `_NoneKey` ~2500, and wherever the parser stores bare lists/blocks), `_isGeneratedKey`/`printNameStr` and their writer callers, `ofList._closing`, `ofSplitList.toString`, `ofDict.toString`, `_fpNames`; the late-collision error in the reader (it needs the line numbers the parser already has).
- `foamkit/functions/load.py` only if the marker does not round-trip through the existing `setattr` path.
- Tests: a new `tests/test_unnamed_keys.py` (one test per table row) and the one rewritten test in `tests/test_bare_top_level_list.py`.

## Out of scope
- Renaming the generated key to something other than `unnamed_<n>` (the read side `d.unnamed_1` stays as T-084 left it).
- Duplicate ordinary keys (`a 1;` / `a 2;`) and OpenFOAM's merge rules for them; not probed here.
- One-line bare lists (T-090), counted bare lists read as `t_2` (T-080), top-level keyword-only entries (T-079).

## Acceptance criteria
- [ ] **Failing tests first:** rows 1-4, every collision row and both code-path rows of the table fail on the T-084 code as listed (name dropped, entry lost, or bare `UnboundLocalError`).
- [ ] A user key `unnamed_3` (list, scalar `unnamed_2 5;`, sub-dict) keeps its name in the regenerated write, in an edited write, and in an edited `case.write()` after `init` → `save` → `load`.
- [ ] Every collision row where the user key comes first keeps both entries: the user's under its key, the keyword-less one under the next free `unnamed_<n>`; both are written (the keyword-less one bare), and write 1 == write 2. Same inside a sub-dict.
- [ ] A user key `unnamed_<n>` that follows a keyword-less entry holding that key raises `FoamKitError` naming the file and both lines, with no traceback for the user.
- [ ] The marker survives the cache: after `init` → `save` → `load`, a bare list is still written without a key and a user `unnamed_3` still with it; editing an item of either is found by the fingerprint and written.
- [ ] Legacy: `unnamed_1 ( (0 0 0) );` loads as the named entry and writes `unnamed_1` back (unedited and regenerated), with exactly one WARNING naming the file and line. The T-084 test is rewritten to this and says why in its docstring.
- [ ] `d['unnamed_5'] = 3`, `d.unnamed_5 = 3` and `d.update(fkt.ofInt(name='unnamed_7', value=1))` write `unnamed_5`/`unnamed_7` with the key; `my_unnamed_x` logs no warning; a key `_name` raises `FoamKitError`.
- [ ] All T-084 tests other than the rewritten one pass unchanged; every file in `tests/releases/` and `tests/fixtures/pitzDaily` writes the same text as before (unedited and regenerated).
- [ ] `grep _isGeneratedKey foamkit/` finds nothing.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): keep user keys named unnamed_<n> and never overwrite an entry with a keyword-less one (T-092)`.

## Risks
- **Behaviour change:** a file an older FoamKit wrote with `unnamed_1` is no longer repaired on a regenerated write; it keeps the keyword and warns. This reverses part of T-084 on purpose (not yet released when this ticket was written).
- **New error:** a late collision now raises where the reader used to overwrite silently; 0 tutorial files.
- **Cache:** a `.params` cache saved before this ticket has no marker, so after `load` its bare lists are written with `unnamed_1`, as every release before T-084 did; there is no way to tell a cached generated key from a user key. The `fix:` commit body tells users to re-run `fk init` on such cases; the tester pins this with a test on a cache file without the marker.
- **Writer reach:** about 25 `printNameStr` callers; a missed one prints the generated key. The release-corpus write test and a test per entry type in the table guard it.
- **OpenFOAM versions:** none; keyword-less entries mean the same in every distribution.
