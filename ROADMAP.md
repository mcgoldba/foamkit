# FoamKit Roadmap

## Questions for the maintainer
1. **foam-extend tier:** confirm the proposed label "headers tested (4.1, 5.0), otherwise best-effort" for the Supported versions page (T-012). Release detection is tested; name mapping is deferred.

## Decisions (2026-10-18, 2026-10-19)
- **Approved by maintainer:** the ranked order, the T-010 canonical name table and the `case.canonical(...)` accessor.
- **T-013 unit API:** parsed units go on a new `.units` attribute. Unit-annotated values come back typed instead of as strings; this is treated as a bug fix and gets a CHANGELOG note.
- **`FoamKitError`:** becomes an `Exception` subclass. For one release it inherits from both `SystemExit` and `Exception`, with a CHANGELOG deprecation notice; a runtime warning "when caught as SystemExit" is not possible in Python. The `fk` CLI keeps its message and exit code (T-017).
- **T-015:** option A, true original quoting. Only the 4 golden lines and 1 test expectation pinned in the ticket may change.
- **T-016:** unknown directives are kept verbatim with a one-time warning, tracked in `foamkit.types` and documented on a Sphinx page (T-018). Public names approved: `ofVerbatimDirective`, `OF_DIRECTIVES`, `DirectiveInfo`, `iterDirectives`.
- **T-005 rescoped (real-file check, 2026-10-19):**
  - Boxed ESI and foam-extend banners are already recognised, so they are pinned as characterization tests.
  - The bug part is only header-less `FoamFile` files.
  - Skipped files stay silent (no warning).
- **T-006:** promoted to right after T-005. Headers are preserved byte-for-byte for Foundation, ESI and foam-extend, using real-file fixtures.
- **Writer formatting churn:** an unedited read → write must reproduce the file. Split into T-019 (whitespace) and T-020 (padding/layout).
- **foam-extend:** a third distribution, handled at the header and detection level. Name mapping is deferred.
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
- **Fixtures** come from real files only. Source URLs are in `docs/plans/openfoam-compatibility.md`, under References.
- **`bin/` scripts:** deleted by the maintainer.

## Done
- **T-002** ruff + mypy config and baseline (ad4c34c)
- **T-004** `#sinclude` / `#includeIfPresent` / other include keywords kept on write (cdfd3c6)

## Current state
- The core init → cache → load → edit → write path is tested on Linux and Windows CI. The ruff/mypy baseline exists.
- Real ESI v2606 and foam-extend 4.1/5.0 files are read correctly.
- Gaps that lose data, change files or make them fail to load:
  - header-less `FoamFile` files are dropped (T-005);
  - writing strips boxed-banner borders (T-006) and adds whitespace churn (T-019, T-020);
  - `#calc` / `#remove` / `#if` / unknown directives raise (T-016);
  - `#includeFunc` with arguments (T-015);
  - unit-annotated values (T-013).
- Parse errors are `SystemExit`, so they end callers' processes (T-017).
- There is no docs site, and the README has broken examples.

## Next (ranked)
1. **T-005** header-less `FoamFile` files, with real banners pinned (S): files silently missing from cases.
2. **T-006** byte-for-byte header write (S): every ESI and foam-extend file is changed on write today.
3. **T-019** no trailing `; ` or extra blank line (S): cheap; it must precede T-007's byte-identical checks.
4. **T-017** `FoamKitError` → `Exception` (S): fixes the error contract before T-016 and T-015 add raise paths.
5. **T-016** other directives, verbatim type and registry (M): one common directive makes a whole file fail to load.
6. **T-015** `#includeFunc` arguments, option A (S): ready, and the xfail tests exist.
7. **T-013** unit-annotated values (M): Foundation 13/14 inputs corrupt or fail to parse.

After these, the order is T-003 → T-001 → T-007 → T-020 → T-018 → T-008 → T-010 → T-009 → T-011 → T-012 → T-014 (see `docs/plans/openfoam-compatibility.md`). T-020 comes after T-007 on purpose: T-007 marks the remaining layout differences as xfail, and its fixtures then serve as T-020's test corpus.

## Deferred
- **Removing `SystemExit` from `FoamKitError`:** the release after T-017 ships.
- **Rewriting bare `except:` handlers** (13 places, listed in T-017): after T-017.
- **foam-extend name mapping (T-010) and full foam-extend case fixtures:** only if users need them.
- **API reference:** after T-010 stabilises the API. Use autodoc2 or an env-clean autodoc (see T-001 risks).
- **Repo-wide `ruff format`, lint in CI:** after the bug-fix tickets above, as one dedicated diff.
- **Console aliases `pf`/`pt` → `fkf`/`fkt`:** a code ticket with a deprecation path, after T-003.
- **Real-OpenFOAM CI, write-side canonical helpers, case conversion, interpreting verbatim directives (backlog on the T-018 page), tutorials, hosting, versioned docs:** these need the work above first.
