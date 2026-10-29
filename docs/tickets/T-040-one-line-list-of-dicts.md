# T-040: One-line `{ … }` blocks: sub-dicts (`p { type probes; }`) and lists of dicts (`x ( a { v 1; } );`); confirmed hangs on real files

- **Issue:** [#54](https://github.com/mcgoldba/foamkit/issues/54)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M. T-022 (one-line sub-dicts) was merged into this ticket by maintainer decision on 2026-10-27. If keeping the layout unchanged needs T-020's source-text mechanism, do only the "keep every entry" part here and leave layout to T-020.
- **Absorbs:** T-022 (#29, closed as not planned). Its scope, evidence and acceptance criteria are below.
- **Related:** T-021 (one-line `FoamFile { ... }`), T-039 (#52, keyword glued to its bracket, which depends on this ticket), T-041 (#55, further entries after the first on a line).
- **Found by:** the T-037 reviewer (PR #53) for lists of dicts, and the T-015 reviewer for one-line sub-dicts. Both are pre-existing on main.

## Goal
A `{ … }` block that opens and closes on one line loads with every entry kept, whether it is a sub-dict (`p { type probes; }`) or a list item (`x ( a { v 1; } b { v 2; } );`), and is written back the way it was. Unsupported input raises `FoamKitError`. Parsing never hangs and never silently drops data. Case files are untrusted input, so a hang is a denial of service.

## Confirmed hangs on real tutorial files (T-037 reviewer, PR #53, 2026-10-27)
The hang is **confirmed**, not hypothetical:
- Foundation 11 `incompressibleFluid/rotorDisk/system/snappyHexMeshDict` and `multiRegion/CHT/heatedDuct/system/snappyHexMeshDict` do **not finish within 25 s**, both on main and on the T-037 branch. The cause is one-line sub-dicts in this ticket's scope.
- Foundation 11 `incompressibleFluid/impeller/system/createNonConformalCouplesDict` **hangs on main**. Since T-037 it raises `FoamKitError` immediately (second entry on a line), so it no longer hangs; loading it fully needs this ticket and/or T-041.

Copy the two `snappyHexMeshDict` files byte-exact into `tests/releases/`, with their sources, and use them as timeout-guarded acceptance tests (below).

## Reproduction
### Lists of dicts
- **Reviewer (PR #53):** `x ( a { v 1; } b { v 2; } );` never finished; it was killed after 30 s. The same happened on main.
- **Planner, 2026-10-27, on an extracted copy of `origin/main` (bc4af32, includes T-035):**

  | Input | Result |
  |---|---|
  | `x ( a { v 1; } b { v 2; } );` | no hang here; finished in about 10 s, which is mostly the slow interpreter start on this machine. **Every item silently lost:** written as `x ( );` |
  | `x ( { v 1; } );` | written as `x ( );`, items lost. One of four runs hit a 15 s timeout, which was **not** reproduced at 40 s |
  | `x ( a { v 1; } );` | written as `x ( );`, items lost |
  | multi-line `x (` / `a { v 1; }` / `);` | written as `x ( a { } … )`: `v 1` lost, plus spurious empty items (also B19/T-037) |

So in this environment the input loses data silently rather than hanging. The reviewer's hang may depend on the T-037 branch state or the environment. **Step 1 for the tester:** reproduce on current main and on the T-037 result with a hard timeout, and record which inputs hang and which empty the list. Both outcomes are in scope.

### One-line sub-dicts (from T-022)
- **Before T-035** (T-015 reviewer, 2026-10-19): `p { type probes; }` raised `IndexError` at `lineList[1][-1]` in `_parseLineLenTwo`, at top level, inside `functions { }`, and after a `#include` line. `pf.init` failed for the whole case.
- **Regression after T-035** (`origin/main` bc4af32, 2026-10-27): the failure is now **silent**. `d { a 1; } e 2;` is written as `d { }`, so `a` (and `e`) are dropped with no error. This ticket fixes that regression.

### Real-file evidence (from T-022, 2026-10-26)
- One-line sub-dicts occur in a tested release, glued to their keyword: Foundation 11 `multiphaseEuler/bubblePipe/constant/phaseProperties:65` `f10{dSph 10e-3; value 0.0;}`.
- That is 6 `phaseProperties` files (67 lines) in Foundation 11, and 0 in Foundation 12-14. They fail today.
- The glued `name{` part is T-039, which builds on this ticket's one-line parsing. Here, test the **spaced** form `f10 { dSph 10e-3; value 0.0; }`.

## Scope
- One-line `{…}` handling in `DictFileParser` (`foamkit/types/__init__.py`): the line-classification path (`_parseLineLenTwo` and its caller), and the list-item handling in `_parseList` / `_parseListValues`. Recognise `name { ... }` and anonymous `{ ... }` that open and close on one line, as entries and as list items. Parse their entries like a multi-line sub-dict.
- Find the bracket ends with T-035's quote-, comment- and code-block-aware scanner.
- Bound every loop by input length. Each pass must make progress or raise.
- Writing:
  - an unedited one-line block is written back on one line, unchanged;
  - if that needs T-020, write it multi-line but keep every entry and value, and add a strict xfail for byte-identity that references T-020;
  - edited one-line blocks may be written multi-line, which is today's style for edited entries.
- **Entries after the block on the same line** (`d { a 1; } e 2;`): these are T-041's general case. If T-041 has not landed, this ticket must make that input raise `FoamKitError` instead of dropping `e`. Never a silent drop.
- **Possible addition (from T-022, unverified):** multi-line `#includeFunc` arguments (`#includeFunc foo(a,\n b)`) fail cleanly with `FoamKitError` today, after T-015. The tester checks whether OpenFOAM accepts this form (Foundation 11-14 / ESI v2412+ sources or tutorials; see the plan's References). If it does, add a round-trip test and the fix here. If not, record "rejected by OpenFOAM, current FoamKitError is correct" and drop it.

## Out of scope
- Keyword glued to its bracket, `a{…}` (T-039)
- The one-line `FoamFile { ... }` block (T-021)
- One-line lists of scalars and re-flow (T-037, T-020)
- Layout (T-020)

## Acceptance criteria
- [ ] **Timeout-guarded tests first** (run each parse in a subprocess, or with `pytest-timeout` if the maintainer adds it, at ≤ 10 s each).
  - Lists: every input in the list table above, plus nesting (`x ( a { b { v 1; } } );`) and a 10^4-item one-line list of dicts.
  - Sub-dicts: `p { type probes; }` at top level, inside `functions { }`, and after a `#include` line, plus a `pf.init` case test with such a `controlDict`.
  - The regression `d { a 1; } e 2;`.
  - The spaced Foundation 11 form `g { f10 { dSph 10e-3; value 0.0; } }`.
- [ ] After the fix, every input finishes within the bound, and every item and entry is kept:
  - `x[0].v == 1`;
  - `d.p.type.value == "probes"`, or the equivalent attribute access;
  - `g.f10.dSph` reads `10e-3`;
  - `pf.init` succeeds.
- [ ] The real Foundation 11 `rotorDisk` and `heatedDuct` `snappyHexMeshDict` files load within the timeout bound, with every entry kept, and round-trip with write 1 == write 2. Today they hang.
- [ ] Multiple entries (`p { type probes; fields (p U); }`), an empty sub-dict (`p { }`) and a nested one-line sub-dict (`a { b { c 1; } }`) parse correctly.
- [ ] `d { a 1; } e 2;` keeps `a`. `e` is either kept (if T-041 has landed) or the input raises `FoamKitError`; it is never silently dropped.
- [ ] An unedited write is byte-identical to the source. Or, if T-020 is needed, every entry and value is kept, with a strict xfail that references T-020. The PR states which. Write 1 == write 2 == write 3.
- [ ] Malformed input (`p { type probes;`, unterminated) raises `FoamKitError` with the file and line, never `IndexError`, never a hang, and does not swallow the rest of the file. A silent empty list or dict is never acceptable.
- [ ] A `#{ ... #}` block on one line is unaffected (regression test).
- [ ] The multi-line `#includeFunc` "possible addition" is resolved and recorded either way.
- [ ] No golden file changes. All `tests/releases/` files behave as before.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Classification:** a line such as `name { ... }` could also be a value containing braces, for example inside `#codeStream` or `#{ #}` blocks. Verbatim code blocks must keep their current handling; this is covered by the regression test above.
- **Untrusted input:** loops must be bounded. Pathological nesting must not hit the recursion limit; cover it with the large-input test.

## Ranking rationale
**Second, right after T-037.**
- It covers **confirmed hangs on real Foundation 11 tutorials** (`rotorDisk`, `heatedDuct`), an untrusted-input denial of service, and the silent loss of every list item (reproduced).
- It also fixes the post-T-035 regression where one-line sub-dicts silently lose their entries.
- Both are worse than loud load failures.
- T-039 (Foundation 11 `phaseProperties`) depends on it.

## Completion notes (implementer, 2026-10-29)

**What changed.** `DictFileParser._splitEntries` (foamkit/types/__init__.py) now opens out every one-line `{ ... }` block (sub-dict `p { type probes; }` or list item `x ( a { v 1; } );`, also nested, empty or anonymous) into the multi-line form the line parser already reads (`p {`, one line per entry, `}`), using T-035's `_lex` for the bracket ends, so strings holding `}`, comments, `#{ #}` blocks and `#codeStream`/`#eval`/`${ }` bodies are untouched. `_lineMap` keeps the physical line for every error. The pass is linear (a 10^4-item one-line list loads in about 1.6 s; 4x10^4 items scale linearly). New: `_joinIncludeFunc` (multi-line `#includeFunc`), `MAX_NESTING = 100`, `_isFoamFileKeyword`.

**User-visible effect.**
- One-line blocks load with every entry, as sub-dicts and as list items. `d { a 1; } e 2;` keeps `a` and `e`. The multi-line named list of dicts that hung now loads. Foundation 11 `rotorDisk` and `heatedDuct` `snappyHexMeshDict` load (about 15 ms) with every entry; they hung before.
- Unterminated input (`p { type probes;`, `x ( { v 1; );`, `p { a { b 1; }`) raises `FoamKitError` naming the file and the physical line of the `{` (was `IndexError`).
- Text the parser cannot place next to a one-line block raises `FoamKitError` with file and line, never a partial load: a list item that is not `name {` / `{` (`x ( 1 2 { v 1; } )`, `x ( { v 1; } 1 2 )`, `x ( ( 1 2 ) { v 1; } )`), a lone word inside the block (`d { a 1; b }`).
- `#eval{ ... }` / `#eval { ... }` inside a list (`origin (#eval{0.5 * $S} 0 0);`) raises `FoamKitError` with file and line (it used to load an empty or wrong list; the real value is T-044).
- Nesting deeper than 100 levels of `(`/`{` raises `FoamKitError` (it was `RecursionError` after 10-30 s).
- Multi-line `#includeFunc foo(a,\n b)` and `#includeFunc foo\n(a, b)` load and round-trip as `#includeFunc foo(a, b)` (see below).
- Entries after `{` in a list-of-dicts item, e.g. `v 1; w 2;` on one line inside a multi-line list item, are now split too (the `;` rule is now relative to the innermost `{`, so `(` outside a `{` no longer blocks it).

**Markers removed.** All `T-040` strict xfails in tests/test_one_line_blocks.py (including `XF_MALFORMED` and `XF_INCLUDE_FUNC`) and `XF_T040` in tests/test_entries_per_line.py. `GUARDED_ELSEWHERE` removed from tests/test_brace_scan.py; `rotorDisk` and `heatedDuct` are in `REAL_OUTCOMES` (both load).

**Markers kept.** T-020 byte-identity (3 tests, `..._written_on_one_line_byte_identical`): still xfail, so the block is written multi-line with every entry kept (the fallback). T-044 (`#eval{` list item values, 3 tests): still xfail; the loud error above is the interim. One new strict xfail, `rotor` in `test_real_snappyHexMeshDict_write_1_equals_write_2`, is NOT caused by T-040: see Deviations.

**#includeFunc.** Foundation 11-14 accept both forms (`functionEntry::readFuncNameArgs`), so it is implemented: lines of an `#includeFunc` whose `(` is still open (or whose next line starts with `(`) are joined before parsing. A span containing a comment, or one never closed, is left as is, so the existing `FoamKitError` still applies. ESI v2412 does not accept it; foamkit now reads it anyway.

**Impeller.** Foundation 11 `impeller/system/createNonConformalCouplesDict` (`name { $other; rotationAngle 60; }`) now loads in full: all 24 couples, every `$nonConformalCoupleIn30;` kept as a variable and written back with its `;`, write 1 == 2 == 3. No error is needed: nothing is dropped. A small inline test (`test_macro_inside_a_one_line_block_is_kept_not_dropped`) covers the shape; the file itself is not added as a fixture.

**One-line FoamFile.** Left alone: a one-line `FoamFile { ... }` is still not expanded (T-021), so its error and the T-021 strict xfails are unchanged. Without this guard it would have started to load as a side effect.

**Deviations from the tester's tests (all fixes of wrong expectations, none weakens a check).**
- `brace_in_string` expected the unquoted `a}b`; string values keep their quotes everywhere in the tree (`'"a}b"'`), so the expectation was changed to that.
- `after_include` / `in_functions_after_include` expected a tree without the `#include` entry (`include0` / `unnamed_1`); the expectation now includes it.
- `_source_keys` counted the words of the multi-line `writeFlags ( ... )` list as top-level keywords; it now skips words inside parentheses.
- `test_real_snappyHexMeshDict_write_1_equals_write_2[rotor]` is split: `write 2 == write 3` and the trees are asserted for both files; `write 1 == write 2` is asserted for `duct` and is a strict xfail for `rotor`. Cause: `inGroups (fixed);` (a one-line, one-element list) is written `inGroups    ( fixed);` (golden-pinned, e.g. `libs ( "libsampling.so");`) and that text is read back as a multi-line list. Identical on main with no `{ }` involved. It belongs with T-037/T-020 (re-flow); fixing it would change goldens.
- tests/test_entries_per_line.py: the two tests that pinned the interim T-040 error were rewritten (entries load; a lone word in a block still raises naming the line), `test_one_line_block_alone_on_its_line_is_unchanged` asserts `sub.b == 2`.
- tests/test_brace_scan.py and tests/probe_runner.py had CRLF line endings; converted to LF.
- New tests: pathological nesting (10^4 deep braces, list items, lists, unclosed), `$macro;` inside one-line blocks.
