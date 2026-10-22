# T-028: Directives with `{` on the next line: `#codeDict` and `#word`

- **Issue:** [#39](https://github.com/mcgoldba/foamkit/issues/39)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-016
- **Split from:** T-016, 2026-10-21 (maintainer-approved)

## Goal
Files using `#codeDict` or a `#word`-generated key with its `{` on the next line load, and are written back unchanged.

## Evidence (real tutorial trees, 2026-10-21)
- **`#codeDict`:** Foundation 14 only, 2 files. Example: `tests/releases/foundation-14.trayedPipe.createZonesDict:24-26`, where `#codeDict` is followed by a block on the next lines (`{`, then `code`).
- **`#word`:** ESI only, 3 uses in `IO/dictionary/good-word-expand.dict` (`tests/releases/esi-v2606.good-word-expand.dict`). There are three forms:
  - value position: `foamApi using #word "_ ${FOAM_API:-unset}" version;` (`:29`);
  - a key followed by a block on the next line: `#word "dict1entry_ ${FOAM_API:-unset}"`, then `{ value1 10; ... }` (`:34-36`);
  - a same-line block: `#word { dict2entry_ ... }` (`:42`).
- **Why T-016's rule does not cover this:** the `{` opens on the **next** line, so T-016's "balanced bracket opened on the directive line" boundary stops at the end of the directive line, leaving a stray `{ ... }` behind.

## Scope
- Extend the capture: when a directive line in the registry has `next_line_block=True` (`codeDict`, `word`) and the next non-blank line starts with `{`, capture through the matching `}`.
- Handle `#word` in value position as a verbatim value.
- Update the `OF_DIRECTIVES` rows.

## Out of scope
- Interpreting `#word` expansion or the code in `#codeDict`

## Acceptance criteria
- [ ] **Failing tests first** with both real fixtures.
- [ ] After the fix, both load, and every `#codeDict`/`#word` use is written back unchanged.
- [ ] Entries after the captured block parse normally.
- [ ] An unterminated next-line block raises `FoamKitError` with the file and line.
- [ ] A directive not flagged `next_line_block` followed by a `{` line keeps T-016 behaviour: the `{` is not swallowed.
- [ ] All existing golden files are unchanged. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- The flag must be per directive, never inferred, so ordinary entries are not swallowed.

## Ranking rationale
Low: only 2 Foundation 14 files and 1 ESI test dictionary are affected.
