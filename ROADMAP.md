# FoamKit Roadmap

## Questions for the maintainer
1. **T-015 quoting conflict:** "write it back the way it was" and "no golden file changes" cannot both hold. The fixture source is unquoted (`#includeFunc streamlines`, `#includeFunc writeObjects(kEpsilon:G)`), but today's goldens and `tests/test_directives.py:82` record quoted output. Pick one:
   - **A** (recommended): true original quoting; 4 golden lines and 1 test expectation change.
   - **B**: original quoting only for argument forms; 2 golden lines change.
   - **C**: no golden change; the xfail tests are relaxed, which contradicts the decision on `writeObjects`.

   Details are in T-015.
2. **T-016 public names:** confirm `ofVerbatimDirective`, `OF_DIRECTIVES`, `DirectiveInfo` and `iterDirectives` at ticket approval.

## Decisions (2026-10-18)
- **Approved by maintainer:** the ranked order, the T-010 canonical name table and the `case.canonical(...)` accessor.
- **T-013 unit API:** parsed units go on a new `.units` attribute. Unit-annotated values come back typed instead of as strings; this is treated as a bug fix and gets a CHANGELOG note.
- **`FoamKitError`:** becomes an `Exception` subclass. For one release it inherits from both `SystemExit` and `Exception`, with a CHANGELOG deprecation notice; a runtime warning "when caught as SystemExit" is not possible in Python. The `fk` CLI keeps its message and exit code (T-017).
- **T-015:** each `#includeFunc` keeps its original quoting (subject to question 1).
- **T-016:** unknown directives are kept verbatim with a one-time warning, tracked in `foamkit.types` and documented on a Sphinx page (T-018).
- **Docs:**
  - Sphinx + MyST + Furo; the strict build is `sphinx-build -W --keep-going -b html docs docs/_build/html`.
  - Doc and README examples use `import foamkit.functions as fkf` / `import foamkit.types as fkt`.
- **Checks:** `mypy foamkit/`. The ruff/mypy baseline is recorded in T-002.
- **Python:** 3.9+, verified on 3.9.23 and 3.14; CI tests 3.9 and 3.12.
- **Release tags:** `v` prefix. Commitizen `tag_format = "v$version"` already matches; only the README needs fixing (T-003).
- **OpenFOAM support:**
  - Tested: Foundation 11-14 and ESI v2412, v2506, v2512, v2606.
  - Older releases are best-effort.
  - Detection order: override, then case banner, then environment.
  - Canonical names follow Foundation 14, mapped through one data table; writes keep the case's native names.
- **`bin/` scripts:** deleted by the maintainer.

## Done
- **T-002** ruff + mypy config and baseline (ad4c34c)
- **T-004** `#sinclude` / `#includeIfPresent` / other include keywords kept on write (cdfd3c6)

## Current state
- The core init → cache → load → edit → write path is tested on Linux and Windows CI. The ruff/mypy baseline exists.
- Verified gaps that lose data or make files fail to load:
  - boxed-banner and bannerless files are silently dropped (T-005);
  - `#calc` / `#remove` / `#if` / unknown directives raise (T-016);
  - `#includeFunc` with arguments (T-015);
  - unit-annotated values (T-013).
- Parse errors are `SystemExit`, so they end callers' processes. Three library paths call `sys.exit()` with status 0 on error (T-017).
- There is no docs site, and the README has broken examples.

## Next (ranked)
1. **T-005** recognise boxed and bannerless files (S): files silently missing from cases.
2. **T-017** `FoamKitError` → `Exception`, CLI exit pinned (S): T-016 and T-015 add raise paths, so fix the error contract first.
3. **T-016** other directives, verbatim type and registry (M): one common directive makes a whole file fail to load.
4. **T-015** `#includeFunc` arguments (S): the xfail tests are ready. It is blocked on question 1; if that is unanswered, take T-013 first.
5. **T-013** unit-annotated values (M): Foundation 13/14 inputs corrupt or fail to parse.
6. **T-003** README corrections (S): the PyPI page has code that does not run.
7. **T-001** Sphinx site + Quickstart (M): needed by T-012 and T-018.

After these, the order is T-006 → T-007 → T-018 → T-008 → T-010 → T-009 → T-011 → T-012 → T-014 (see `docs/plans/openfoam-compatibility.md`).

## Deferred
- **Removing `SystemExit` from `FoamKitError`:** the release after T-017 ships.
- **Rewriting bare `except:` handlers** (13 places, listed in T-017): after T-017.
- **API reference:** after T-010 stabilises the API. Use autodoc2 or an env-clean autodoc (see T-001 risks).
- **Repo-wide `ruff format`, lint in CI:** after the bug-fix tickets above, as one dedicated diff.
- **Console aliases `pf`/`pt` → `fkf`/`fkt`:** a code ticket with a deprecation path, after T-003.
- **Real-OpenFOAM CI, write-side canonical helpers, case conversion, interpreting verbatim directives (backlog on the T-018 page), tutorials, hosting, versioned docs:** these need the work above first.
