# T-020: Preserve key/value padding and layout of unedited entries on write

- **Issue:** [#27](https://github.com/mcgoldba/foamkit/issues/27)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M. The first step is a short design note in this ticket. If that note shows more than M, split by entry kind: T-020a scalars and words, T-020b lists and sub-dictionaries.
- **Plan:** docs/plans/openfoam-compatibility.md, bug B9
- **Depends on:** T-019. Should land after T-007, which provides the real-file corpus.
- **Followed by:** T-050 (#67, `fk format` and `format_on_write`).

## Maintainer decision (2026-10-30)
"lets keep the original layout as default, and have a format command the reformats the whole file. Lets also add a user specifiable option to reformat files on write by default."
- **Preserving the layout of unedited entries is the default write behaviour** (this ticket). Edited and new entries are written in the standard style.
- Reformatting a whole file is T-050 (#67): `fk format`, `fkf.formatDictFile`/`fkf.formatCase`, and an opt-in `format_on_write` config key plus a `case.write(format=...)` argument. When that option is on, it **bypasses** this ticket's preservation and regenerates every entry in the canonical style. T-050 lands after this ticket and builds on its preserve-or-regenerate split, so this ticket needs no format option. Its write path should keep "regenerate this entry" as one call that T-050 can force for every entry.
- T-050 also changes the standard style for edited entries: keyword column 16 instead of 12, and no tab after long keywords. Until T-050 lands, this ticket keeps today's style for edited entries.

## Goal
An unedited read → write reproduces each entry's original spacing and layout. Only entries the user changed are re-formatted.

## Today
- The writer re-aligns key/value padding (`TAB_SIZE`-based columns).
- It re-flows some lists: `tests/test_golden.py:36-42` notes that `libs ("lib.so");` becomes a multi-line list.
  - That one-element example is split out to T-045 (2026-10-30): `libs ("lib.so");` is written `( "lib.so")`, which re-reads as a different list type, and `domains (10);` fails to load. T-020 keeps the general layout work.
- Goldens record this normalized output.

## Scope
- **Design note:** retain each entry's source text (or its whitespace tokens) at parse time, keep a "modified" flag set by assignment, and write the source text for unmodified entries.
- The parser and writer in `foamkit/types/__init__.py`
- The JSON cache (`case.save` / `pf.load`): decide whether source text is cached. If it is not, document that a cache round trip normalizes formatting.

## Out of scope
- Formatting of edited entries (keeps today's style)
- Header (T-006) and FoamFile-block whitespace (T-019)

## Acceptance criteria
- [ ] Every T-007 fixture round-trips byte-identically when unedited. The `xfail` markers T-007 added for T-020 are removed.
- [ ] Editing one entry changes only that entry's lines. A diff test on a real fixture checks this.
- [ ] `test_repeated_writes_converge` still passes. Goldens are regenerated, and their diffs are reviewed as "now equal to source".
- [ ] The cache behaviour is documented and tested.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline. There is a `fix:` commit whose body describes the user-visible change.

## Risks
- **Memory:** keeping source text per entry costs memory on large dictionaries; check against `dict_filesize_limit`.
- **Modified flags:** nested edits (`case.a.b.c = x`) must mark the right node as modified.
- **Output change:** users who relied on FoamKit normalizing formatting will see that stop. Say so in the commit body (the `fix:` commit).
