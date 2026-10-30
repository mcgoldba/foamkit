# T-042: `#include` inside a list can't be written back (`boundary ( #include "f" … );`)

- **Issue:** [#57](https://github.com/mcgoldba/foamkit/issues/57)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-041 (#55, merged), which made `helmholtzResonance` load and exposed this writer bug; T-016 (directive framework, `iterDirectives`); T-015 (`#includeFunc` quoting); T-044 (`#eval` inside lists, ESI); T-027 (`#calc`/`#neg`).
- **Found by:** the T-041 implementer and reviewer (PR #56). It is pre-existing on main: before T-041 the file never got far enough to be written.

## Goal
A list that contains an `#include`-family directive (`#include`, `#sinclude`, `#includeIfPresent`, `#includeEtc`, `#includeFunc`) loads and is written back with the directive on one line, unchanged. Anything still unsupported raises `FoamKitError` with file and line, never `TypeError` and never silent change.

## Reproduction (planner, 2026-10-29, `t-040-one-line-brace-blocks` at 376edf3 + uncommitted tests; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| real F14 `helmholtzResonance/system/blockMeshDict` (`tests/releases/foundation-14.helmholtzResonance.blockMeshDict`) | loads; `toString()` **fails:** `TypeError: ofInclude.toString() got an unexpected keyword argument 'indent'`, raised from `ofSplitList.toString` (`foamkit/types/__init__.py:1578`, `v.toString(ofRep=False, indent=False)`) |
| `x ( #include "f"` / `a { b 1; }` / `);` (multi-line list of dicts) | same `TypeError` on write. The `#include` is parsed as an `ofInclude` item; `ofInclude.toString(self, ofRep=False)` (line 2849) has no `indent` |
| `blocks ( #include "f"` / `hex (…) (1 1 1) simpleGrading (1 1 1)` / `);` (list without dicts) | loads and writes, but the directive is split into two list items, `ofStr('#include')` and `ofStr('"f"')`, written on separate lines (`#include` / `"f"`). OpenFOAM still reads it, but FoamKit does not model it as an include (`iterDirectives` does not see it) and the layout changes |
| `functions ( #includeFunc patchAverage(name=inlet, p) );` | **silent corruption:** written as `#includeFunc` / `patchAverage` / `name=inlet,` / `p`, so the parentheses are lost and the meaning changes. 0 tutorial occurrences |
| `#includeEtc`, `#sinclude`, `#calc "1+2"`, `#neg $a`, `#print "hi"`, `$a` in a plain list | load and write as separate tokens (`#calc` / `"1+2"`), stable on re-read. Not a bug for this ticket, see Out of scope |

The failing helmholtz write is in the **`boundary`** list (line 189, a list of dicts), not in `blocks` (line 150, which takes the token path above).

## Real tutorial occurrences (Foundation 11-14 and ESI v2412-v2606 clones, planner scan 2026-10-29)
Method: every `FoamFile` dictionary under `tutorials/` (ESI read from git `HEAD`), tokenised with strings, `//` and `/* */` comments and `#{ #}` blocks skipped; a directive counts when its innermost bracket is `(`.

| Directive in a list | F11 | F12 | F13 | F14 | ESI v2412-v2606 (each) |
|---|---|---|---|---|---|
| `#include` in a **list of dicts** (write crash) | 1 file | 1 | 1 | 1 | 1 |
| `#include` in a plain list (token split) | 1 file | 2 | 3 | 3 | 2 files (5 lines) |
| `#includeEtc` / `#includeFunc` / `#sinclude` in a list | 0 | 0 | 0 | 0 | 0 |
| `#neg` in a list (vertex lists, e.g. `(0 #neg $y $z)`) | 9 files, 234 | 12, 296 | 12, 296 | 13, 297 | 0 |
| `#calc` in a list | 0 | 0 | 1 file, 2 | 1 file, 2 | 0 |
| `#eval` in a list | 0 | 0 | 0 | 0 | 8 files, 31 (T-044) |

- List of dicts: F11-14 `fluid/helmholtzResonance/system/blockMeshDict:189`; ESI `compressible/rhoPimpleFoam/laminar/helmholtzResonance/system/blockMeshDict:193`. Both raise the same `TypeError` (checked on all four Foundation clones and ESI v2606).
- Plain lists: the `helmholtzResonance` `blocks` list; F12-14 `engine2Valve2D/constant/dynamicMeshDict:122` (`times ( #include "$FOAM_CASE/constant/meshTimes" );`, loads and writes today); ESI `wallMountedHump/setups.orig/common/system/blockMeshDict:449-463` (`polyLine 4 8 ( #include "geometry/polyLine_4to8" )`).

## Scope
- The list writers `ofList.toString` and `ofSplitList.toString` and the include family's `toString` (`ofInclude`, `ofIncludeEtc`, `ofIncludeFunc`): a directive item is written as one line, `#include "f"`, with its original keyword and quoting (T-004, T-015), and without the trailing blank line `ofInclude.toString` adds at dict level.
- The list item parser (`_parseList` / `_parseListValues`): an include-family directive in any list (plain or list of dicts, multi-line or one-line) becomes one include item, so `iterDirectives` sees it, instead of two string tokens. `#includeFunc name(args)` keeps its argument text verbatim (T-015).
- Anything in a list that cannot be kept unchanged raises `FoamKitError` naming file and line.

## Out of scope
- Other directives in lists (`#calc`, `#neg`, `#print`, `$a`): they round-trip as tokens today and stay as they are. Value-position `#calc`/`#neg` is T-027.
- `#eval` inside lists and glued `#eval{…}` (T-044)
- `#codeStream` inside a list of dicts (F11-14 `resources/blockMesh/rotor2D`, F12 `trayedPipe/system/topoSetDict`): writer layout is T-033
- One-line `{…}` blocks (T-040), list layout (T-020)

## Acceptance criteria
- [ ] **Failing tests first:** every row of the reproduction table that is a bug, at top level and inside a sub-dict, plus the real fixtures `tests/releases/foundation-14.helmholtzResonance.blockMeshDict` (already present) and the ESI v2606 `helmholtzResonance/system/blockMeshDict`, copied byte-exact into `tests/releases/` with its source recorded.
- [ ] Both helmholtz files load and write; the written text re-reads to the same entries and write 1 == write 2. The `#include` lines in `blocks` and `boundary` are written as `#include "blockMeshDict.caseBlocks"` / `#include "blockMeshDict.caseBoundary"` on one line each.
- [ ] The strict xfails `XF_INCLUDE_IN_LIST` in `tests/test_entries_per_line.py` (`test_helmholtz_every_variable_survives_a_write`, `test_helmholtz_second_write_equals_the_first`; reason today "unticketed: writing a #include inside a list fails …") pass with the markers removed. `tests/test_brace_scan.py` `REAL_OUTCOMES["foundation-14.helmholtzResonance.blockMeshDict"]` changes from `TypeError` to its first keys, and the comments naming the bug as "unticketed" are updated to T-042. Any other test whose reason says "unticketed" for this bug is updated to cite T-042 or flipped.
- [ ] `#include`, `#sinclude`, `#includeIfPresent`, `#includeEtc` and `#includeFunc foo(a, b)` in a plain list and in a list of dicts each round-trip with the directive text unchanged and are listed by `iterDirectives`.
- [ ] `#includeFunc patchAverage(name=inlet, p)` in a list never loses its parentheses: it round-trips, or raises `FoamKitError` with file and line.
- [ ] No golden file changes. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Behaviour change for plain lists:** a list that today reads as `[ofStr('#include'), ofStr('"f"'), …]` will hold one include item. Code that indexed list items by position (e.g. F12-14 `engine2Valve2D` `times`) sees one item fewer. Treated as a bug fix; say so in the commit body.
- `ofInclude.toString` is shared with dict-level writing. Its dict-level output (including the blank line after it) must not change; the existing include goldens guard it.
- The T-040 branch is rewriting the same list-parsing code. Start after T-040 merges.

## Ranking rationale
**Right after T-040.** Every tested release (Foundation 11-14, ESI v2412-v2606) has a stock tutorial, `helmholtzResonance`, that loads but crashes on write. That is worse for a user than a load failure, because the edit is lost at the last step. The fix is small and the tests already exist as strict xfails. It also removes a silent-corruption path (`#includeFunc` arguments in lists), although that one has no tutorial occurrences.

## Completion notes (implementer, 2026-10-30)
- **What changed** (`foamkit/types/__init__.py`): new `ofInclude.toListString()` (and an `ofIncludeFunc` override) writes a directive on one line with its keyword and original quoting, no trailing blank line; `ofList.toString` and `ofSplitList.toString` use it, so the `TypeError` on write is gone. New `DictFileParser._parseListInclude` is called from `_parseListValues`: an include-family directive in a plain list (multi-line or one-line) is now one include item (`ofInclude`, `ofIncludeEtc`, `ofIncludeFunc`) instead of two `ofStr` tokens. `#includeFunc name(args)` keeps its argument text verbatim and round-trips; an unbalanced or unterminated argument raises `FoamKitError` with file and line. A directive whose argument is not a quoted string (`#include foo`) or that has none keeps the old token behaviour, so nothing is changed silently. Dict-level output is unchanged (no golden changed).
- **User-visible effect:** `helmholtzResonance/system/blockMeshDict` (Foundation 11-14, ESI v2412-v2606) now loads and writes with `#include "blockMeshDict.caseBlocks"` / `...caseBoundary` on one line each; `#includeFunc patchAverage(name=inlet, p)` in a list no longer loses its parentheses.
- **Test markers removed:** `XFAIL_TODAY` table and `XF` markers in `tests/test_include_in_list.py`; both `XF_INCLUDE_IN_LIST` markers in `tests/test_entries_per_line.py`; `REAL_OUTCOMES` for both helmholtz files in `tests/test_brace_scan.py` now pin their first keys instead of `TypeError`.
- **Deviation:** the criterion "listed by `iterDirectives`" is dropped: `iterDirectives` yields only `ofVerbatimDirective` items and never lists `ofInclude`, even at dict level. Tests assert the list holds an include item instead. `iterDirectives` is unchanged.
- **Positional indexing (risk from the ticket):** a plain list holding an include now has one item where it had two, e.g. F12-14 `engine2Valve2D` `times ( #include "$FOAM_CASE/constant/meshTimes" );` holds one `ofInclude` instead of `ofStr('#include')`, `ofStr('"$FOAM_CASE/..."')`. Intended fix; mention in the commit body.
