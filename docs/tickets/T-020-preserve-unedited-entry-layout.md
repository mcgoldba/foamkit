# T-020: Preserve key/value padding and layout of unedited entries on write

- **Issue:** [#27](https://github.com/mcgoldba/foamkit/issues/27)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M. The first step is a short design note in this ticket. If that note shows more than M, split by entry kind: T-020a scalars and words, T-020b lists and sub-dictionaries.
  - **Design note (2026-11-08): more than M as a whole. Split by depth, not by entry kind; approved by the maintainer, 2026-11-08** (see "Size verdict" below). This ticket becomes **T-020a**, covering the top level of a file. **T-083 (T-020b, #111)** covers keeping the layout inside an edited sub-dictionary.
- **Plan:** docs/plans/openfoam-compatibility.md, bug B9
- **Depends on:** T-019.
- **Rescoped (2026-11-06):** moved up to right after T-055 (maintainer). It no longer waits for T-007: its corpus is the real files already in `tests/releases/` plus `tests/fixtures/pitzDaily`. T-007 now lands after this ticket, and its fixtures must round-trip byte-identically with no T-020 `xfail`.
- **Followed by:** T-083 (#111, T-020b), then T-050 (#67, `fk format` and `format_on_write`).

## Maintainer decision (2026-10-30)
"lets keep the original layout as default, and have a format command the reformats the whole file. Lets also add a user specifiable option to reformat files on write by default."
- **Preserving the layout of unedited entries is the default write behaviour** (this ticket). Edited and new entries are written in the standard style.
- Reformatting a whole file is T-050 (#67): `fk format`, `fkf.formatDictFile`/`fkf.formatCase`, and an opt-in `format_on_write` config key plus a `case.write(format=...)` argument. When that option is on, it **bypasses** this ticket's preservation and regenerates every entry in the canonical style. T-050 lands after this ticket and builds on its preserve-or-regenerate split, so this ticket needs no format option. Its write path should keep "regenerate this entry" as one call that T-050 can force for every entry.
- T-050 also changes the standard style for edited entries: keyword column 16 instead of 12, and no tab after long keywords. Until T-050 lands, this ticket keeps today's style for edited entries.

## Goal
An unedited read → write reproduces each entry's original spacing and layout. Only entries the user changed are re-formatted (T-020a: the top-level entry that contains the change).

## Today
- The writer re-aligns key/value padding (`TAB_SIZE`-based columns).
- It re-flows some lists: `tests/test_golden.py:36-42` notes that `libs ("lib.so");` becomes a multi-line list.
  - That one-element example is split out to T-045 (2026-10-30): `libs ("lib.so");` is written `( "lib.so")`, which re-reads as a different list type, and `domains (10);` fails to load. T-020 keeps the general layout work.
- Goldens record this normalized output.

## Gap today (planner, 839663c, 2026-11-08)
Unedited `DictFileParser(f).readDictFile().toString()` vs the source text, line diff (`difflib`). Corpus: the 25 of 41 files in `tests/releases/` that load, plus the 9 pitzDaily dictionaries. Every one of the 34 files changes. In total, 1143 of 2721 source lines are changed or lost, and 2314 output lines differ.

Kinds of change: **P** key/value padding (including the tab after `#includeFunc`, `#include`, `#sinclude`); **B** blank lines between entries dropped, or added after lists/dicts; **L** lists re-flowed (one-line → multi-line; item spacing `(  0 -10  10)` → `(0 -10 10)`; `hex (…) $cells simpleGrading (…)` items split over 5 lines); **1** one-element list written `( "x")` (T-045); **N** number spelling (`1e-6` → `1e-06`, `1e-2` → `0.01`, `(0 0 0)` → `(0.0 0.0 0.0)`; T-032); **C** `//` comment after an entry or list item dropped, moved or **duplicated** (T-056, T-057); **K** `/* */` block comment flattened onto one line (T-031); **D** a one-line `{ … }` block or a line of several entries opened out (T-040/T-041 output); **E** `};` written `}`; **F** FoamFile block padding; **I** `#includeModel heatSource` written quoted (T-029); **U** a top-level unnamed list written with an `unnamed_1` keyword (T-084, see note 3).

| File | Lines | Changed (−src/+out) | Kinds |
|---|---|---|---|
| esi-v2606.bendJunction.blockMeshDict | 346 | −231/+450 | P B L C K D |
| esi-v2606.blob.collapseDict | 84 | −27/+21 | P B N F |
| esi-v2606.externalCoupled | 62 | −24/+26 | P B 1 C K |
| esi-v2606.floatingObject.dynamicMeshDict | 83 | −31/+56 | P B L 1 N C (comment in a `table`) |
| esi-v2606.helmholtzResonance.blockMeshDict | 251 | −160/+265 | P B L D C |
| foundation-11.capillaryRise.setFieldsDict | 36 | −4/+13 | P B L |
| foundation-11.controlDict | 58 | −19/+22 | P B |
| foundation-11.damBreak.fvSchemes | 62 | −20/+22 | P B D |
| foundation-11.heatedDuct.snappyHexMeshDict | 110 | −43/+279 | P B L D E |
| foundation-11.pipeCyclic.topoSetDict | 28 | −5/+10 | P B |
| foundation-11.refineFieldDirs.blockMeshDict | 125 | −86/+130 | P B L N C K |
| foundation-11.rotorDisk.snappyHexMeshDict | 136 | −37/+161 | P B L 1 N C (duplicated) D E |
| foundation-13.parcelInBox.cloudPositions | 19 | −2/+6 | B L **U** |
| foundation-13.shockTube.sample | 38 | −10/+34 | P B L 1 |
| foundation-14.DTCHullMoving.dynamicMeshDict | 83 | −24/+58 | P B L 1 |
| foundation-14.aerofoilNACA0012.physicalProperties | 46 | −7/+16 | P B |
| foundation-14.concentricCylinders.blockMeshDict.orig | 103 | −28/+103 | P B L |
| foundation-14.cylinder.momentumTransport | 51 | −13/+18 | P B |
| foundation-14.helmholtzResonance.blockMeshDict | 243 | −160/+265 | P B L D C |
| foundation-14.hotWire.controlDict | 58 | −17/+19 | P B |
| foundation-14.pitzDaily.momentumTransport | 28 | −5/+5 | P B |
| foundation-14.planingHullW3.dynamicMeshDict | 71 | −23/+48 | P B L 1 |
| foundation-14.refineMeshSector.blockMeshDict | 123 | −85/+129 | P B L N C K |
| foundation-14.roomHeating.fvModels | 19 | −1/+3 | B I |
| foundation-14.simpleRushtonMRF.createBafflesDict.baffles | 39 | −2/+8 | P B |
| pitzDaily 0/U | 45 | −7/+14 | P B N |
| pitzDaily 0/p | 37 | −5/+10 | P B |
| pitzDaily constant/momentumTransport | 28 | −6/+6 | P B |
| pitzDaily constant/transportProperties | 23 | −3/+4 | P B |
| pitzDaily system/blockMeshDict | 65 | −5/+16 | P B L |
| pitzDaily system/controlDict | 72 | −22/+37 | P B L 1 |
| pitzDaily system/fvSchemes | 57 | −12/+20 | P B |
| pitzDaily system/fvSolution | 58 | −16/+26 | P B N C |
| pitzDaily system/setFieldsDict | 34 | −3/+14 | P B L |

Not loading on main (16 files, picked up when their ticket lands): T-026 `esi-v2606.good-if1.dict`, `esi-v2606.good-if3.dict`, `esi-v2606.squareBend.blockMeshDict`, `foundation-14.cylinder.fvSchemes`; T-027 `foundation-13.aerofoilNACA0012Steady.U`, `foundation-14.aerofoilNACA0012Steady.U`, `foundation-14.cylinder.blockMeshDict`, `foundation-14.rotatingCube.blockMeshDict`; T-028 `esi-v2606.good-word-expand.dict`, `foundation-14.trayedPipe.createZonesDict`; T-029 `foundation-14.engine2Valve2D.fvConstraints`; T-030 `esi-v2606.freePiston.U`, `foundation-14.floatingBeam.blockMeshDict`; T-031 `esi-v2606.potentialFoam-cylinder.blockMeshDict`; T-046 `esi-v2606.flange.faceSetDict`; T-057 `foundation-14.SandiaD_LTS.radiationProperties`.

Notes:
1. No `#codeStream` (T-033) entry is in a corpus file that loads. Header (T-006) and the blank lines after FoamFile (T-019) are already exact.
2. The FoamFile block's padding (**F**, `collapseDict`) is not covered by T-019, which only fixed blank lines. Without it, that file cannot reach 0, so T-020a covers the block as one atomic entry.
3. **U** (`parcelInBox.cloudPositions`, a file whose content is one bare list) is a **silent data change on every write today**: the output gains a keyword (`unnamed_1 ( … );`), and OpenFOAM's reader expects a bare list. With T-020a an unedited write keeps the source, but a regenerated one still adds the keyword. Ticketed as T-084.
4. Line ends: `case.write()` and `writeCase` open files in text mode (`'w'`). On Windows an LF source is written CRLF. The byte-identical criterion here is on `toString()` vs the source read with universal newlines. On-disk line-end preservation is ticketed as T-085 (maintainer, 2026-11-08).

## Design note (planner, 2026-11-08)
**1. Where source text is captured.**
- **Unit:** an entry of a container. In T-020a the container is the top level of an `ofDictFile`, plus the FoamFile block as one entry. T-083 adds every `ofDict`.
- **Span:** the whole **original** lines, from the line where the entry's `_parseLine` call starts to the last line it consumes. It includes a trailing `// comment` and any text after `;` on that last line.
  - The parser works on lines rewritten by `_joinIncludeFunc` and `_splitEntries`. The span is mapped back with `_lineMap`, which today records only the first original line of a joined `#includeFunc`, so it must also record the last.
  - The original lines are kept as read (universal newlines).
- **Leading blank lines** are the entry's *gap*, stored apart from its text. An edited entry keeps the blank lines around it, and a deleted entry takes its gap with it.
  - Comment lines are not part of a gap: they are `ofComment` entries with spans of their own.
  - The first entry's gap starts after the FoamFile block's blank lines, which T-019's `_blank_lines_after` keeps owning.
  - Everything after the last entry (blank lines, a missing final newline) is the container's `tail`.
- **Line groups:** entries whose spans share an original line form one group with one text. Examples: T-041's `x1  14; x2   6; // X divisions`, `div(rhoPhi,U) … grad(U);Gauss upwind;`, a trailing comment that the parser also returns as an `ofComment` (the `rotorDisk` duplicate), a top-level one-line block.
  - A group is written from source only if all its members are present, consecutive and unmodified.
  - Otherwise every member is regenerated on its own line, and the first member keeps the gap.
- **Storage:** on the container, not on the entries. `ofDictFile._srcLayout` is added to `_CLASS_VARS`, like `_blank_lines_after` and `_comment_keyword`. It holds plain lists and strings, so it is JSON-serialisable:
  `{"foamFile": [text, fp], "entries": [[[key, ...], gap, text, [fp, ...]], ...], "tail": text}`
  - Records are keyed by the `__dict__` key: `_comment_<n>`, the include keys and `_1` duplicates included.
  - Why the container: `d.endTime = 3000` may replace the entry object under the same key, so text stored on the object, gap included, would be lost. An entry object copied into another file or depth must not bring its old text: under a new key it is simply new, so it is regenerated.
  - Not `_srcText`: `ofListGroups` already uses that name for number tokens (T-071), and those stay as they are.
- **Cache: kept.** `_srcLayout` goes out through `attrDict()` and back through `setattr` in `_parseCaseDict`, as `_blank_lines_after` already does.
  - Probe at 839663c: for every pitzDaily dictionary, the cache serialisation of every top-level entry is identical before and after `save` → `load`. Fingerprints therefore match, and an unedited cache round trip writes the source.
  - If a reload ever builds a slightly different object, that entry is regenerated (normalized), never written stale.
  - The cache grows by about the size of the dictionary text.

**2. The "modified" signal: value comparison, not a flag.**
- At parse time each entry gets a fingerprint `fp`: blake2b, 16-byte hex, of `json.dumps` of the same `_toDict` serialisation `case.save` uses, with `_srcLayout` left out. At write time it is computed again. Equal: source text. Different: standard style.
- **Why not a flag:** a flag must be set on every mutation path. These include `ofDict.__setattr__` and `__setitem__`, the `.value` setters of ~20 types, `ofList.value.append(...)`, `ofListGroups.groups[i][j] = …`, `del`, `_name` renames through `__setitem__`, and nested `case.a.b.c = x`.
  - One missed path writes stale text: a silent data change (CLAUDE.md, "Errors never pass silently").
  - Value comparison can only err the safe way: a false "modified" just regenerates. This is the same principle as T-071's `_srcReprs` check.
- **Nested edits:** nested edits and in-place list mutation change the fingerprint of the top-level entry that holds them. T-083 adds fingerprints per nested node.
- **Probe:** every top-level entry of the 34 corpus files serialises with plain `json.dumps` (0 failures), in about 0.25 s for all files together.
- **Collisions** (128 bit) are negligible.
- **Hidden mutation:** anything that mutates an entry while it is only read would show up as "modified". The corpus test (target 0) catches that.

**3. What is written** (for each key, in `__dict__` order):
- **Unmodified** (fingerprint equal, group complete): gap + source text, verbatim.
- **Modified:** gap + today's `toString()` for that entry, with its trailing blank lines stripped (the gaps own blank lines now).
  - In T-020a a change anywhere inside a top-level sub-dict regenerates that whole top-level entry, as every write does today.
  - T-083 keeps that sub-dict's braces and untouched children.
- **Deleted:** its gap and text are gone. A group that lost a member regenerates its other members.
- **New key** (no record): today's separator (one blank line before it at the top level) + standard style, appended after the last entry and before `tail`, as today.
- **Reordered** (deleted and re-added): a key with a record writes its text at its new position if unmodified. The values are right; only the blank lines may differ.
- **Interactions:**
  - T-019 keeps owning the blank lines after FoamFile.
  - T-055's `_comment_keyword` and T-071's `_srcText`/`_srcReprs` are part of the fingerprint, and regeneration uses them as today.
  - T-046: an unedited `#include "f";` keeps its `;` verbatim. An edited or new one uses T-046's writer.
  - The header (T-006) is unchanged.

**4. The single "regenerate" hook for T-050.**
- Both writers call one private function, e.g. `_layoutText(container, key, value, preserve) -> Optional[str]`. It returns the source text, or None for "regenerate".
- `ofDictFile.toString(ofRep=True, *, _preserve=True)` passes `preserve` down. `_preserve=False` gives today's writer for every entry. T-050 makes it public as `format=`.
- T-050 must also clear `_srcLayout` after a format write. Otherwise the next default write would bring the old layout back.

**5. Memory.**
- Each source line is in exactly one record, so the text costs about the file size once, plus ~200 B per record (list, key, fingerprint, gap).
- Largest corpus file, `bendJunction.blockMeshDict` (16.8 KB): about 250 KB stays allocated after load (tracemalloc). T-020a adds about 20 KB (~8 %).
- At `dict_filesize_limit` (10 MB): about +10 MB against ~150 MB of parsed objects at the same ratio (~7 %). Files that large are mostly one list, so one record.
- No new limit is needed.

**6. Tickets that shrink to "regenerated entries only"** (the planner edits them when T-020a merges):
- **T-031:** unedited block comments come back verbatim. What is left: the load failure (`potentialFoam-cylinder`) and multi-line comments inside regenerated entries.
- **T-032:** number spelling changes only in regenerated entries (until T-083, also their siblings in the same top-level block).
- **T-033:** `#codeStream` growth only on regenerated entries. Its load parts are unchanged.
- **T-056:** trailing `//` comments are kept for unedited entries but still dropped silently when the entry is regenerated. It stays a silent-loss ticket, smaller.
- **T-057:** the same for list-item comments. The `SandiaD_LTS` load failure part is unchanged.
- **T-045:** `( "lib.so")` no longer appears on unedited writes. The type change on regenerated lists and the `domains (10);` load failure remain.
- **T-029:** `#includeModel` quoting only on regenerated entries. The `#includeConstraint` load failure remains.

**7. Size verdict: more than M.** The whole ticket would cover parser spans and line groups, fingerprints, partial preservation in two writers, the cache and a 34-file corpus with regenerated goldens.
- **The split by entry kind does not work.** Every corpus file has lists or sub-dicts, so a "scalars and words" part (T-020a) would reach 0 changed lines on none of them.
- **Split by depth (approved by the maintainer, 2026-11-08):**
  - **T-020a** (this ticket, M): records for the top level, the FoamFile block and the tail. Every top-level entry of any kind is atomic. All 34 loading files reach 0.
  - **T-083 / T-020b** (#111, M): partial preservation inside an edited sub-dict at any depth.
- **Lists stay atomic in both.** Keeping the untouched items of an edited list is deferred.

## Scope (T-020a)
- `DictFileParser.readDictFile` (the top-level loop) and the line-map bookkeeping of `_joinIncludeFunc`/`_splitEntries`: spans, gaps, line groups, FoamFile record, tail, fingerprints.
- `ofDictFile.toString`: preserve-or-regenerate per top-level entry through the single hook. `_srcLayout` goes in `_CLASS_VARS`.
- The `.params` cache keeps `_srcLayout` (see design note). Documented in the docstring of `ofDictFile.toString` and in the commit body.
- Goldens regenerated (they become equal to the source).

## Out of scope
- Formatting of edited entries (keeps today's style)
- Header (T-006). Blank lines after the FoamFile block stay with T-019; the block's padding is in scope (Gap note 2).
- Partial preservation inside an edited sub-dict (T-083) or list (deferred)
- The `unnamed_1` keyword on a regenerated bare top-level list (T-084) and on-disk line ends (T-085) (Gap notes 3 and 4)

## Acceptance criteria
- [ ] **Corpus:** every file in `tests/releases/` that loads on main, and every dictionary in `tests/fixtures/pitzDaily`, round-trips byte-identically when unedited (`toString()` == source text read with universal newlines). That is all 34 files in the Gap table. The 16 files that do not load yet are listed in the test with the ticket that blocks them (list above), and are picked up automatically once they load.
- [ ] For each corpus file, a test reports the number of changed lines on an unedited write; the target is 0 for all of them.
- [ ] Editing one **top-level** entry changes only that entry's lines. Diff tests on real fixtures check this:
  - pitzDaily `system/controlDict` `endTime`: 1 line;
  - one member of a shared line (`helmholtzResonance` `x3`): only that source line, written as one line per member;
  - a deleted entry: only its lines and its gap;
  - a new entry: appended before the tail.
- [ ] An edit inside a top-level sub-dict regenerates that block only; all other top-level entries stay byte-identical.
- [ ] A missed edit cannot write stale text. A test mutates nested and in-place (`case.a.b.c = x`, `lst.value.append(...)`, `groups[i][j] = …`) without going through any setter that could set a flag, and the change is written.
- [ ] `toString(_preserve=False)` gives today's output for every corpus file (T-050's hook).
- [ ] `test_repeated_writes_converge` still passes. Goldens are regenerated, and their diffs are reviewed as "now equal to source".
- [ ] Cache: on pitzDaily, `save` → `load` → write is byte-identical to the source for every dictionary, and an edit after `load` is written. This is documented.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline. There is a `fix:` commit whose body describes the user-visible change.

## Risks
- **Overlap with open writer tickets:** keeping the source text of unedited entries also keeps their comments (T-056, T-057), block comments (T-031), number spelling (T-032) and `#codeStream` text (T-033). The design note says which of these become "edited entries only" after this ticket, so the planner can shrink them; this ticket does not close them.
- **Size:** the corpus covers more entry kinds than T-007's pitzDaily set would have. The depth split (T-083) was approved by the maintainer on 2026-11-08, so this ticket stays M.
- **Memory:** about +8 % on the largest corpus file (design note, point 5); well within `dict_filesize_limit`.
- **Modified detection:** only fingerprints decide. Nested edits change the top-level entry's fingerprint, so they cannot be missed. Anything that mutates an entry on read would show as "modified" (regenerated, never stale); the corpus test catches it.
- **Output change:** users who relied on FoamKit normalizing formatting will see that stop. Say so in the commit body (the `fix:` commit).
