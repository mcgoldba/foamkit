# T-016: Verbatim directive framework and single-line directives (`#print`, `#remove`, …)

- **Issue:** [#23](https://github.com/mcgoldba/foamkit/issues/23)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M
- **Follows:** T-004, T-017 (error semantics), T-025 (`userMsg` prints untrusted text literally)
- **Narrowed 2026-10-21 (maintainer-approved)** after the tester's real-tutorial inventory. The other directive work moved to:
  - T-026: `#if`/`#ifeq`/`#else`/`#endif`
  - T-027: value-position `#calc`/`#neg`
  - T-028: next-line-brace `#codeDict`/`#word`
  - T-029: `#includeModel`/`#includeConstraint`
- **Docs follow-up:** T-018 (Directive support page).

## Goal
**Stock Foundation 14 pitzDaily loads.** Today its `constant/momentumTransport` fails on an argument-less `#print` inside `RAS {}`. More generally, directives FoamKit does not interpret are kept verbatim, can be found from code, and are written back unchanged.

## Policy (approved by maintainer, 2026-10-18)
Unknown directives are **kept verbatim, with a one-time WARNING** (once per directive name per file, via `userMsg`, which prints literally since T-025), instead of raising.
- FoamKit never runs directives, so it never changes a file's meaning.
- Raising makes the whole case fail to load.

**Line-level capture boundary (this ticket):** a single-line directive is captured from `#` to the end of its line. A balanced `(`, `{` or `"` that opens on the directive line extends the capture to its matching close, which may be on a later line.
- If the close is never found, raise `FoamKitError` with the file and line. Never consume to the end of the file silently.
- Directives whose `{` is on the **next** line (`#codeDict`, `#word`) do not fit this rule and are T-028.
- Block directives (`#if` … `#endif`) are T-026.

## Design: tracked in `foamkit.types` (public names approved 2026-10-19)
- **`ofVerbatimDirective`:**
  - `keyword` and `text` (raw source); `toString()` returns `text` unchanged;
  - a `known` property: `True` if the keyword is in `OF_DIRECTIVES`.
- **`OF_DIRECTIVES`:** `{keyword: DirectiveInfo(status, distributions, note)}`.
  - `status` is `"interpreted"`, `"verbatim"` or `"unsupported"`.
  - It is seeded from the inventory in `docs/plans/openfoam-compatibility.md` (section "Directive inventory"). **All** inventoried directives get a row, including those handled by other tickets; those are marked `"unsupported"` with a note naming the ticket until that ticket lands.
  - It sits next to `OF_FUNCTION_ENTRIES` and `OF_VERBATIM_CODE_ENTRIES`; do not change those two.
- **`iterDirectives(obj, status=None)`:** walks an `ofCase`, folder or dict file and yields `(location, directive)` pairs. `status` may be `"verbatim"`, `"unknown"`, … .

## Directives handled here (from the real-tutorial inventory, 2026-10-21)
| Directive | Where (real files) | Form |
|---|---|---|
| `#print` | Foundation 14 only, 25 uses in 24 files: pitzDaily `constant/momentumTransport`, `fluid/cavity/constant/thermophysicalTransport:23`, `XiFluid/1D/constant/combustionProperties:53` | argument-less, inside a sub-dict |
| `#remove` | ESI only, 41-48 files: `basic/potentialFoam/cylinder/system/blockMeshDict:87` `#remove ( "r(Inner\|Outer).*" "[xy](min\|max)" )`, `coldEngineFoam/freePiston/0/U:51` `#remove (wall piston)` | word or same-line list |
| `#inputMode` | ESI only, 1 file | word |
| `#calcInclude` | Foundation 11-13 only, 1 file (`fluid/aerofoilNACA0012Steady/0/U:21`, `#calcInclude "transform.H"`) | quoted string |
| `#message` | ESI, 4 (`IO/dictionary/good-word-expand.dict:18,21,24`) | word, quoted string, or same-line `{ ... }` |
| `#codeBlock`, `#endCodeBlock`, `#codeInclude` | Foundation 14 only, 7/7/1 (`fluid/aerofoilNACA0012Steady/0/U:20-26`) | marker lines; `#codeInclude "transform.H"` |

`#codeBlock`/`#endCodeBlock` enclose ordinary entries that use value-position `#calc` (T-027). Here they are captured as single marker lines, and the entries between them are parsed normally. The tester confirms that the F14 aerofoil `0/U` gets past both markers; full load of that file also needs T-027 and T-013 (`angleOfAttack 0 [deg];`).

## Scope
- Directive dispatch and `_parseVerbatimEntry` in `foamkit/types/__init__.py`. Unknown directives go to `ofVerbatimDirective` instead of raising "Unknown directive".
- `ofVerbatimDirective`, `OF_DIRECTIVES`, `DirectiveInfo`, `iterDirectives`
- Tests, using the tester's real-file fixtures under `tests/releases/`

## Out of scope
- `#if`/`#ifeq`/`#else`/`#endif` (T-026)
- value-position `#calc` and `#neg`, and the `ofCalc` TypeError (T-027)
- `#codeDict`, `#word` with `{` on the next line (T-028)
- `#includeModel`, `#includeConstraint` (T-029)
- `#codeStream` writer instability (T-033)
- Evaluating anything
- The Sphinx page (T-018)

## Acceptance criteria
- [ ] **Stock Foundation 14 pitzDaily loads.** The real `constant/momentumTransport` (`tests/releases/foundation-14.pitzDaily.momentumTransport`) parses, and `#print` inside `RAS {}` is written back unchanged.
- [ ] Every directive in the table above round-trips unchanged (after normal whitespace formatting) at top level and inside a sub-dict. Use the real-file lines quoted above as test inputs.
- [ ] `OF_DIRECTIVES` has a row for every directive in the plan's inventory, with the correct status and distributions. Directives deferred to T-026..T-029 are marked `"unsupported"` with the ticket in `note`.
- [ ] An unknown `#directive`:
  - parses to `ofVerbatimDirective` with `known == False`;
  - is written back byte-for-byte;
  - logs exactly one WARNING per name per file;
  - does not stop later entries from parsing.
- [ ] A directive whose same-line bracket is never closed raises `FoamKitError` with the file and line.
- [ ] `iterDirectives` returns every verbatim and unknown directive with its location. Tested with `status=None`, `"verbatim"` and `"unknown"`.
- [ ] `#includeEtc` and `#includeFunc` inside sub-dicts keep their keyword and value: a dedicated test.
- [ ] All existing golden files are unchanged. New public names have type hints and docstrings. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Behaviour change:** files that used to raise now load. Describe it in the commit body.
- **Unknown-directive warnings could hide real typos.** The once-per-name warning and `iterDirectives` make them discoverable.
- **Untrusted text in warnings:** the directive text from case files goes through `userMsg`, which prints it literally since T-025.

## Completion notes (implementer, 2026-10-21)
- **Done:**
  - `ofVerbatimDirective`, `DirectiveInfo`, `OF_DIRECTIVES` (all 25 inventoried directives) and `iterDirectives` are in `foamkit/types/__init__.py`.
  - Registered "verbatim" directives and unregistered `#word` directives at the start of a line go to `DictFileParser._parseVerbatimDirective`.
  - The real Foundation 14 pitzDaily `momentumTransport` loads, writes `#print` back unchanged, and `pf.init` works.
- **Statuses:**
  - interpreted: the include family, `eval`, `codeStream`.
  - verbatim: `print`, `remove`, `inputMode`, `calcInclude`, `message`, `codeBlock`, `endCodeBlock`, `codeInclude`.
  - unsupported (ticket in `note`): `includeModel`/`includeConstraint` T-029, `calc`/`neg` T-027, `if`/`ifeq`/`else`/`endif` T-026, `codeDict`/`word` T-028.
  - Unsupported directives keep today's behaviour.
- **Capture:** one linear pass from the `#` to the end of the line. `(`, `{`, `"` and `#{` extend it to the matching close (`#}` for `#{`).
  - Inside a string only the closing quote counts (with `\"` escapes); inside `#{ ... #}` only `#}` counts.
  - Outside them `//` ends the scan of the line.
  - An unclosed opener raises `FoamKitError` naming the file and the directive's physical line.
- **Warning:** only unknown directives warn, once per name per file (`DictFileParser._warnedDirectives`).
- **`text`:** the raw source from the `#`. Continuation lines lose the directive's own indentation; the writer adds the nesting indentation back. Reads and writes at the same level therefore keep every character, and they stay stable in nested dicts.
- **`iterDirectives`:**
  - "verbatim" and "unknown" are disjoint; `None` returns both.
  - `location` is the `/`-joined attribute path starting with the name of the object passed in (e.g. `pitzDaily/constant/momentumTransport/RAS/unnamed_1`).
- **Fixed:** `#codeInclude "transform.H"` no longer raises `IndexError`.
- **Tests believed wrong (not edited):**
  - `test_entries_inside_captured_braces_are_not_attributes`: `ofDict.__getattr__ = dict.get`, so `hasattr(d, anything)` is always True. The same `not hasattr` pattern is in three strict-xfail T-026 tests, which therefore can never flip. Suggested fix: `assert first.inner is None`.
  - `test_real_file_second_write_is_stable[esi-v2606.bendJunction.blockMeshDict]`: fails on the T-031 block-comment bug. A single-line `/* ... */` is read back with its `/*` kept, so each write prepends another `/*`. Suggest a T-031 xfail for this file.
  - `test_iterDirectives_locations_say_where_each_directive_is`: asserts at least 4 distinct locations, but the case has exactly 3 directives (another test requires exactly 3).
- **Checks:** pytest passes except those three tests (see the report). ruff 190, ruff format 55, mypy 127: no change from the baselines.

### Round 2 (implementer, 2026-10-25)
- **`OF_DIRECTIVES`** is now `types.MappingProxyType(_OF_DIRECTIVES)`: a `Mapping`, not a `MutableMapping`. Item assignment and deletion, `clear`, `update`, `pop`, `popitem` and `setdefault` raise.
- **`ofVerbatimDirective`:**
  - `dataclass(init=False)` with a custom `__init__(self, *, keyword=None, text=None, value=None, _comment=None)`. It works on Python 3.9, where `dataclass(kw_only=True)` does not exist.
  - Positional arguments raise `TypeError`.
  - The no-argument constructor followed by `setattr` (the `load.py` JSON reload) still works.
- **`DirectiveInfo.status`** is annotated `Literal["interpreted", "verbatim", "unsupported"]`. It is not checked at run time.
- **Interim brace guard** (removed by T-035, issue #47):
  - `_findDictOrListEndLine('dict')` calls `_checkDirectiveBraces` on each directive line it passes. That is where the wrong end line was chosen.
  - The guard scans the directive with the capture rules, plus `/* */` skipped as a comment. It sums `{` minus `}` per captured line.
  - If the running sum ever goes negative, or does not end at 0, it raises `FoamKitError` (via `userMsg`) with the file and the directive's physical line.
  - Balanced braces such as `${FOAM_API:-unset}` in a string (the real `#message`) stay harmless.
  - Top-level directives are not guarded, so they keep loading verbatim. The top-level `#fooBar /* { */` still raises "Unclosed '{'".
- **Conflicting test:** `test_registry_is_a_dict_of_directive_info` asserts `isinstance(OF_DIRECTIVES, dict)`. A `dict` is a `MutableMapping`, so it cannot hold together with the new read-only tests. Not edited; it needs to become `isinstance(..., Mapping)`.
- **Checks:** pytest on conda and on py39: only that test fails. ruff 190, ruff format 55, mypy 127: no change from the baselines.

### Round 3 (coordinator, after the round-2 review)
- The guard now scans each directive with exactly the capture's rules (the `comments=True` option is no longer used by the guard). Before, the guard skipped `/* … */` but the capture did not, so `#fooBar /* ( */` or `#fooBar /* " */ x` followed by `}` lines passed the guard and then mis-scoped silently. Both now raise `FoamKitError` with the file and line (new tests at depths 1–3).
- With that change, `#fooBar /* { */` in a sub-dict is caught by the existing dict-end check instead of the guard; that error now names the file too ("Could not locate end of dict starting on line N of file …").
- The test asserting `isinstance(OF_DIRECTIVES, dict)` was changed by the coordinator to `collections.abc.Mapping`.
- Results: `pytest -q` 1158 passed, 1 skipped, 108 xfailed on Python 3.12 and 3.9; ruff 190, format 55, mypy 127; no golden changes.
