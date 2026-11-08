# T-083 (T-020b): editing an entry inside a sub-dictionary changes only that entry's lines

- **Issue:** [#111](https://github.com/mcgoldba/foamkit/issues/111)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M
- **Split from:** T-020 (#27), design note of 2026-11-08 (proposed; the maintainer must approve the split). T-020 keeps the top level (T-020a); this ticket is the nested part.
- **Depends on:** T-020 (#27): its `_srcLayout` records, value fingerprints and the single preserve-or-regenerate hook.
- **Followed by:** T-050 (#67), which must force "regenerate" for nested entries too and drop nested layouts after a format write.

## Goal
Editing one entry inside a sub-dictionary at any depth (`case.system.fvSolution.solvers.p.tolerance = 1e-7`, a `boundaryField` patch value, a function object setting) changes only that entry's lines. The sub-dictionary's keyword line, braces, blank lines and untouched sibling entries keep their source text.

## Today (after T-020a)
Every top-level entry is written from source while unedited. An edit anywhere inside a top-level sub-dictionary (`solvers`, `boundaryField`, `functions`) regenerates that whole top-level block in the standard style: all its padding, blank lines and `//` comments (T-056, T-057) are lost, which is no better and no worse than before T-020.

## Scope
- `DictFileParser._parseDict`: give every `ofDict` its own `_srcLayout` record, the same shape as T-020a's top-level record plus `open` (the source lines from the keyword line to the line with `{`), `close` (the gap before the closing `}` and the `}` / `};` line with any trailing text) and the depth it was read at.
- Fingerprints for nested entries, combined bottom-up (a dict's fingerprint is built from its keys, its own non-entry attributes and its children's fingerprints), so the cost stays linear in the file size.
- `ofDict.toString`: use T-020a's preserve-or-regenerate hook for every entry. A modified dict whose layout is usable writes `open`, then each child by the same rule, then `close`. If its name or `_comment_keyword` changed, only the keyword line is regenerated.
- A dict cannot be partly preserved, and is regenerated as a whole when anything inside changes, if:
  - its `{`, an entry or its `}` share an original line (a one-line block `p { type patch; }`, or T-055's `p { d // c`);
  - it is written at a different depth than it was read (the object was moved).
- Line groups (T-041 entries sharing a line) inside sub-dicts, with the same rule as at the top level.
- The `.params` cache keeps the nested records (same mechanism as T-020a).

## Out of scope
- Keeping untouched items of an edited **list** (one vertex of a `vertices` list): lists stay atomic. An edited list is regenerated as a whole.
- The standard style for edited entries (T-050).
- Comments that the parser drops today in regenerated entries (T-056, T-057).

## Acceptance criteria
- [ ] **Failing tests first**, on copies of real fixtures, each asserting the exact unified diff against the source:
  - pitzDaily `system/fvSolution`: `solvers.p.tolerance` edit → 1 changed line;
  - pitzDaily `0/U`: `boundaryField.inlet.value` edit → 1 changed line;
  - pitzDaily `system/controlDict`: `functions.probes.writeInterval` edit → 1 changed line. The `//` comments and blank lines of the block stay;
  - `foundation-11.heatedDuct.snappyHexMeshDict`: an edit inside the one-line block `metalInlet { name metalInlet; }` changes only that source line (written as the standard multi-line block). Its sibling lines stay as read;
  - an added key in a sub-dict is inserted before that dict's `}` in the standard style. Deleting a key removes only its lines and its leading blank lines;
  - renaming a sub-dict (`_name`) changes only its keyword line;
  - a sub-dict assigned to another depth is regenerated as a whole: no text with the old indentation.
- [ ] All T-020 corpus tests still give 0 changed lines when unedited. `test_repeated_writes_converge` passes, and write 1 == write 2 after each edit above.
- [ ] Cache: after `save` → `load`, the nested edits above give the same diffs.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. There is a `fix:` commit whose body describes the user-visible change.

## Risks
- **Parser bookkeeping:** `_parseDict` reads the `{` line through extra lines (`_addExtraLine`) and resets `self.i`. The spans must come from `_lineMap`, never from the working lines, which `_splitEntries` rewrote.
- **Stale text:** only fingerprint comparison decides "unmodified", the same as T-020a. Flags must not be added as a shortcut.
- **Cost:** fingerprints at every depth. The bottom-up combination keeps them linear. The T-020a probe took 0.25 s for all 34 corpus files at the top level.
- **T-050:** `format_on_write` must bypass the nested records too, through the same hook.
