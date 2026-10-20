# T-015: `#includeFunc` with arguments round-trips unchanged

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Follows:** T-004 (criterion 4). The two strict-xfail tests in `tests/test_directives.py` already exist.
- **Status:** ready. **Option A approved by the maintainer (2026-10-19).**

## Goal
Function-object includes, with or without arguments, are written back the way they were read. Today `#includeFunc streamlines(U)` comes back as `#includeFunc "streamlines(U)"`, and `#includeFunc streamlines(U, name=s)` fails to parse.

## Maintainer decision (2026-10-18)
Write each `#includeFunc` back the way it was: every entry keeps its original quoting. Expected results: `writeObjects(kEpsilon:G)` stays unquoted, `streamlines` stays as written today, and no golden file changes.

## Conflict: "the way it was" vs "no golden file changes"
The decision cannot be met as stated. The existing output already differs from the source:

| Source (unquoted) | Written today (quoted) | Pinned by |
|---|---|---|
| `tests/fixtures/pitzDaily/system/controlDict:54` `#includeFunc streamlines` | `#includeFunc	"streamlines"` | `tests/golden/case/controlDict.written.txt:56`, `tests/golden/dicts/pitzDaily/system/controlDict.txt:56`, characterization test `tests/test_directives.py:82` (`"#includeFunc streamlines"` → `'#includeFunc "streamlines"'`) |
| `tests/fixtures/pitzDaily/system/controlDict:55` `#includeFunc writeObjects(kEpsilon:G)` | `#includeFunc	"writeObjects(kEpsilon:G)"` | the same two goldens, line `:58` |

So with per-entry original quoting, both golden lines change (unquoted source gives unquoted output), and `test_directives.py:82` is contradicted. The two strict-xfail tests cannot pass unless argument forms come out unquoted, and the fixture has an unquoted argument form. That means **no option makes the xfail tests pass with zero golden changes**.

Options for the maintainer (planner recommendation: **A**):
- **A. True original quoting.**
  - Lines `:56` and `:58` in both controlDict goldens become unquoted, which matches the fixture source byte for byte. `test_directives.py:82` is updated to expect unquoted output.
  - Quoted input (`#includeFunc "streamlines"`) stays quoted.
  - Gives exactly the byte-identical round trip that T-007 requires. 4 golden lines + 1 test expectation change; user-visible note in the `fix:` commit body.
- **B. Original quoting for argument forms only; argument-less names keep today's forced quotes.**
  - Changes 2 golden lines (`:58` in each file). Keeps `:56` and test `:82`.
  - Unquoted bare names are still rewritten. T-007's byte-identical round trip would need an exception for them.
- **C. No golden changes.** Only possible if the two xfail tests are rewritten to accept quoted argument output. This contradicts the maintainer decision that `writeObjects(kEpsilon:G)` stays unquoted.

**Decision (2026-10-19): option A.** Options B and C are kept above only as a record. The 4 golden lines and the 1 test expectation pinned below are the only allowed golden/test changes.

## Forms to support
These are written from memory. **The tester must confirm each one against real tutorial files** (T-007 fixtures if they exist, otherwise the release sources) and record the source here.
- **Foundation 11-14:**
  - positional: `#includeFunc mag(U)`;
  - named: `#includeFunc patchAverage(patch=inlet, fields=(p U))`;
  - nested parentheses and lists: `#includeFunc graphUniform(funcName=l, start=(0 0 0), end=(1 0 0), nPoints=100, fields=(U))`;
  - `name=` overrides.
- **ESI v2412-v2606:** `#includeFunc name` and `#includeFunc name(args)`. Check whether named and nested arguments behave the same.

## Scope
- `ofIncludeFunc` (store the raw argument text, and whether the input was quoted) and the include dispatch / `_parseIncludes` in `foamkit/types/__init__.py`
- `tests/test_directives.py`
- Golden lines, only as allowed by the chosen option

## Out of scope
- Interpreting arguments (the text is kept verbatim)
- Other directives (T-016)

## Acceptance criteria (option A, approved)
- [ ] Both strict-xfail tests in `tests/test_directives.py` pass with their `xfail` markers removed.
- [ ] Every `#includeFunc` is written with its original quoting. Quoted input stays quoted and unquoted input stays unquoted. This is tested for both a bare name and an argument form, at top level and inside `functions {}`.
- [ ] Golden changes are **exactly** lines `:56` and `:58` of `tests/golden/case/controlDict.written.txt` and `tests/golden/dicts/pitzDaily/system/controlDict.txt`, made unquoted. No other golden line changes. The reviewer checks `git diff --stat -- tests/golden`.
- [ ] `test_directives.py:82` is updated to expect unquoted output, with a comment referencing this ticket.
- [ ] Every confirmed form from "Forms to support" (positional, named, nested, with a trailing comment) round-trips unchanged.
- [ ] Unbalanced parentheses (`#includeFunc mag(U`) raise a clear `FoamKitError` naming the file and line, and never swallow the following entries.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline. There is a `fix:` commit whose body describes the user-visible change (the changelog is generated from commits).

## Risks
- Users who diff written files see `#includeFunc` lines lose their added quotes. Both forms are valid OpenFOAM; the `fix:` commit body covers it.
- **Untrusted input:** argument text is stored and written back, never evaluated. The balanced-bracket scan is bounded by the end of the file.

## Evidence (2026-10-19, real file; no change to acceptance criteria)
- Foundation 11 pitzDaily `system/controlDict` line 55, `#includeFunc patchAverage(patch=inlet, fields=(p U))`, fails to load ("Could not find functionEntry bracket type"). So stock Foundation 11 pitzDaily cannot be loaded until this ticket lands. Source: `https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-11/master/tutorials/incompressibleFluid/pitzDaily/system/controlDict`.

## Completion notes (implementer)
- `ofIncludeFunc` gained `quoted` (field `_quoted`, default True, so code-built entries keep today's quoted output). `DictFileParser._parseIncludeFunc` scans the single directive line (linear, bounded by the line) with a parenthesis depth counter; argument text is stored verbatim. Trailing `//` and `/* */` comments are not part of the arguments (and are still dropped on read). Unbalanced parentheses raise `FoamKitError` naming file and 1-based line; following entries are not consumed. Lines not of the form `#includeFunc <token> [comment]` fall back to the old generic path.
- Goldens changed: lines 56 and 58 of `tests/golden/case/controlDict.written.txt` and `tests/golden/dicts/pitzDaily/system/controlDict.txt`.
- **Blocker for the maintainer:** `tests/golden/dicts/headers/esi-v2606.controlDict.txt:50` (`#includeFunc streamlines`) is a fifth golden line that also loses its quotes. It is outside the pinned list, so it was NOT regenerated and `test_golden.py[headers/esi-v2606.controlDict]` fails until it is approved.
- Not fixed here: IndexError in `_parseLineLenTwo` for unquoted `#includeFunc` lines followed by a one-line `p {type probes;}` in `functions {}`; still reproduces.
- Follow-up: the argument scan skips `"..."` spans (with `\"` escapes) inside parentheses, so brackets and `//` there are data; an unterminated quote raises `FoamKitError` naming file and line. The hand-added CHANGELOG section was removed (commitizen generates it); the user-visible note goes in the commit body.
- The ESI golden `tests/golden/dicts/headers/esi-v2606.controlDict.txt:50` was regenerated by the coordinator after review.
