# T-016: `#calc`, `#remove`, `#if/#else/#endif`, `#inputMode` and unknown directives

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M. Split if the inventory shows conditional blocks need a block-level parser: **T-016a** for single-line directives, the registry and the verbatim type; **T-016b** for `#if`/`#ifeq`/`#else`/`#endif` blocks.
- **Follows:** T-004, T-017 (error semantics)
- **Docs follow-up:** T-018 (Directive support page). T-001 is ranked after this ticket, so the page is a separate docs ticket rather than part of T-016.

## Goal
A dictionary that uses any directive found in the tested releases' tutorials loads, and is written back unchanged. Directives FoamKit does not interpret can be found from code.

## Current behaviour (reported after T-004)
| Input (top level) | Today |
|---|---|
| `#calc "1+2"` | `TypeError: ofCalc.__init__() got an unexpected keyword argument 'name'` |
| `#remove x` / `#remove (a b)` | FoamKitError "Could not find functionEntry bracket type" |
| `#if ... #else ... #endif` | same |
| `#inputMode merge` | same |
| `#print` (no argument, inside `RAS {}`), from the real Foundation 14 `constant/momentumTransport` | Fails to load. **Stock Foundation 14 pitzDaily cannot be loaded today** (2026-10-19). |
| any other `#word` | FoamKitError "Unknown directive ..." (`_parseVerbatimEntry`, `foamkit/types/__init__.py:5339-5341`) |

## Policy (approved by maintainer, 2026-10-18)
Unknown directives are **kept verbatim, with a one-time WARNING** (once per directive name per file), instead of raising.
- FoamKit never runs directives, so it never changes a file's meaning.
- Raising makes the whole case fail to load.
- The capture is bounded: it runs to the end of the line, or to the matching close of a balanced `(`, `{`, `#{` or `"` that opens on that line. If no boundary is found, raise `FoamKitError` with the file and line. Never consume to the end of the file silently.

## Design: tracked in `foamkit.types`
- **New public type `ofVerbatimDirective`**, with:
  - `keyword` (for example `"if"`) and `text` (the raw source, including any block up to `#endif` for conditionals);
  - `toString()` returns `text` unchanged;
  - a `known` property: `True` if the keyword is in the registry.

  It is used for every directive FoamKit preserves but does not interpret, both registry-listed and unknown ones. Existing interpreted types (`ofInclude*`, `ofEval`, `ofCodeStream`, `ofCalc`) are unchanged.
- **Registry constant `OF_DIRECTIVES`** in `foamkit/types/__init__.py`, plain data:
  ```python
  {keyword: DirectiveInfo(status, distributions, note)}
  ```
  - `status` is `"interpreted"`, `"verbatim"` or `"unsupported"`;
  - `distributions` is the releases where the tester found it, for example `("foundation-11..14", "esi-v2412..v2606")`.

  It is seeded from the inventory below. It sits alongside the existing `OF_FUNCTION_ENTRIES` (`:2962`) and `OF_VERBATIM_CODE_ENTRIES` (`:3101`); do not change those two.
- **Finding them from code:** a generator `iterDirectives(obj, status=None)` in `foamkit.types`. It walks an `ofCase`, folder or dict file and yields `(location, directive)` pairs. `status="verbatim"` lists everything preserved but not interpreted, and unknown keywords are reported as `status="unknown"`.
- **Public names approved by the maintainer (2026-10-19):** `ofVerbatimDirective`, `OF_DIRECTIVES`, `DirectiveInfo`, `iterDirectives`.

## Step 1: inventory (tester, recorded in this ticket)
- Grep the tutorials of the tested releases (Foundation 11-14, ESI v2412-v2606) for `^\s*#[a-zA-Z]` directives, including those inside sub-dictionaries.
- Record each directive, a count, an example file, and the proposed status.
- From memory, expect `#calc`, `#remove`, `#include*`, `#codeStream`, and on ESI `#eval`, `#if`/`#ifeq`/`#else`/`#endif` and `#sinclude`. `#inputMode` is legacy and best-effort. All of this must be confirmed.
- **Must round-trip (confirmed from a real file):** `#print`, argument-less, inside a sub-dictionary. Source: Foundation 14 pitzDaily `constant/momentumTransport` line 25, `https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-14/master/tutorials/incompressibleFluid/pitzDaily/constant/momentumTransport`. Add it to the inventory and `OF_DIRECTIVES`, and add a test that this real file loads and round-trips.
- Every directive found must round-trip. This table seeds `OF_DIRECTIVES`, and through T-018 it is also the **backlog record**: directives marked `verbatim` are the candidates for real interpretation later, if a need comes up.

## Scope
- The directive dispatch (`foamkit/types/__init__.py:3962-3967`), `_parseVerbatimEntry` (`:5339-5341`) and the `ofCalc` constructor
- `ofVerbatimDirective`, `OF_DIRECTIVES`, `DirectiveInfo` and `iterDirectives` in `foamkit/types`
- `tests/test_directives.py` and a fixture dict made of real tutorial lines

## Out of scope
- Evaluating `#calc`/`#eval`, resolving `#remove`, or choosing `#if` branches. Entries inside `#if` blocks are part of the verbatim text and are not editable through attributes; document this in the docstrings.
- `#includeFunc` arguments (T-015)
- The Sphinx page (T-018)

## Acceptance criteria
- [ ] The inventory table is recorded in this ticket with sources, and `OF_DIRECTIVES` contains exactly those rows.
- [ ] Every inventoried directive round-trips byte-identically (after normal whitespace formatting) at top level and inside a sub-dictionary. The tests are parametrized over `OF_DIRECTIVES`.
- [ ] The real Foundation 14 `constant/momentumTransport` (fixture copied byte-exact) loads, and `#print` inside `RAS {}` is written back unchanged.
- [ ] `#calc "1+2"` and `#calc #{ ... #}` parse and round-trip. The `TypeError` is gone.
- [ ] An unknown `#directive`:
  - parses to `ofVerbatimDirective` with `known == False`;
  - is written back byte-for-byte;
  - logs one WARNING per name per file;
  - does not stop the entries after it from parsing.
- [ ] An unbounded unknown directive raises `FoamKitError` with the file and line.
- [ ] `iterDirectives` on a fixture case returns every verbatim and unknown directive with its location. Tested with `status=None`, `"verbatim"` and `"unknown"`.
- [ ] `#includeEtc` and `#includeFunc` inside sub-dictionaries keep their keyword and value: a dedicated test beyond the existing golden coverage (`tests/golden/case/controlDict.written.txt:56-58`, `tests/golden/dicts/pitzDaily/0/p.txt:37`).
- [ ] All existing golden files are unchanged. New public names have type hints and docstrings. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- **Behaviour change:** files that used to raise will now load, so callers who relied on an error for validation lose it. Note it in the CHANGELOG.
- **Conditional blocks:** capture the whole block up to `#endif`. Otherwise the entries inside would look like normal editable entries. If this needs a block parser, use the T-016b split.
- **Version facts:** which release supports which directive is from memory until the inventory is recorded.
