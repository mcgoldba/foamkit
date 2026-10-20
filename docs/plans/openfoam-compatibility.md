# Plan: OpenFOAM multi-distribution support

## Support levels (maintainer decision, 2026-10-18)
- **Tested:** the four latest releases of each distribution. Each has a fixture in CI.
  - Foundation (openfoam.org): **11, 12, 13, 14**
  - ESI (openfoam.com): **v2412, v2506, v2512, v2606**
- **Best-effort, untested:** older releases (for example Foundation 7-10, ESI v2006-v2406) and anything newer than the tested set.
- **foam-extend (third distribution, added 2026-10-19):** 4.1 and 5.0 are "headers tested, otherwise best-effort":
  - header recognition and byte-for-byte header write are tested with real-file fixtures (T-005, T-006);
  - release detection covers foam-extend (T-008);
  - name mapping (T-010) is deferred;
  - full-case fixtures are optional and later (T-007 note).
- **Python:** 3.9+, tested on 3.9 and 3.12.

The version-specific facts below were written from memory unless marked *real file*. On 2026-10-19 a memory-based claim (B2 for boxed banners) turned out to be wrong when checked against real files. T-007's fact-check table, built from real release files (see References), is the source of truth and overrides this document. Fixture text must always be fetched from real files.

## 1. Inventory: what FoamKit actually touches

FoamKit's core is a generic dictionary parser and writer. It hard-codes very few physics file names. Most of the risk is in **file format details** (banners, directives, value syntax) and the **post-processing layout**.

### Verified bugs
Reproduced on 2026-10-18 with scratch files; no code was changed.

| # | Where | What happens | Affects |
|---|---|---|---|
| B1 | `foamkit/types/__init__.py:3962-3964` → `_parseIncludes` `:4686-4697` | `#sinclude "a"` and `#includeIfPresent "b"` are **written back as `#include`**, so an optional include becomes mandatory. | Tested (ESI `#sinclude`; both) → T-004 |
| B2 (corrected 2026-10-19) | `foamkit/types/_isDictFile.py:12-13`, used at `types/__init__.py:607` | **Header-less** files (first line `FoamFile`) are not recognised, so `pf.init` silently drops them. *Correction:* boxed banners are **not** dropped. Real ESI v2606 and foam-extend 4.1/5.0 files are recognised and fully read. The earlier claim came from a probe written from memory with single backslashes. | Header-less files (all distributions) → T-005 (bug); real banners pinned as characterization in T-005 |
| B3 (*real file*, 2026-10-19) | `foamkit/types/__init__.py:362-376` | Writing the real ESI v2606 `controlDict` strips the `\|` borders from the boxed banner (column slicing `[29:]`). foam-extend uses the same boxed layout. | ESI, foam-extend → T-006 |
| B4 | `foamkit/types/__init__.py:378-383` | Header truncation uses `'line'+str(i)` with `i` starting at 0, an off-by-one. | all → T-006 |
| B5 | Value and list parsing in `foamkit/types/__init__.py` | Unit-annotated values (forms guessed from the CFD Direct note; T-013 confirms the real syntax): `1.5e-05 [m^2/s]` becomes a plain string (not numeric); `(10 0 0) [m/s]` is **corrupted**, with the unit written inside the list; `uniform (10 0 0) [m/s]` **fails to parse** (`ValueError`). | Tested (Foundation 13/14 make input units standard) → T-013 |
| B6 | `ofNamedDimension` parsing | `nu nu [0 2 -1 0 0 0 0] 1.5e-05;` is written as `nu [0 2 -1 0 0 0 0];`, so **the value is lost**. | Best-effort only (older `transportProperties`) → T-014 |
| B7 | Directive dispatch `foamkit/types/__init__.py:3962-3967`, `_parseVerbatimEntry` `:5339-5341` | `#remove`, `#if/#else/#endif`, `#inputMode` and unknown `#word` lines raise, so the whole file fails to load. `#calc "1+2"` raises `TypeError` (`ofCalc` constructor). | Tested (`#calc`, `#remove`, ESI `#if`; to be inventoried) → T-016 |
| B8 | `ofIncludeFunc` | `#includeFunc f(U)` is written quoted. `#includeFunc f(U, name=s)` fails to parse. | Tested (Foundation function-object arguments) → T-015 |
| B9 (*real file*, 2026-10-19) | Dict-file writer | An unedited read → write of the real ESI v2606 `controlDict` adds a trailing space after `;`, re-aligns key/value padding and adds a blank line after the FoamFile block. | All → T-019 (whitespace), T-020 (padding/layout) |
| B10 (2026-10-19) | `FoamFile` block parsing in `DictFileParser` | A one-line `FoamFile { ... }` block: with entries after it, `IndexError` (whole case fails); alone, written back as `FoamFile\n{\n}\n`, so its entries are **lost**. Header-less files with a one-line block, content after `{` on its line, `}` not at the start of its line, or content after `}` on its line are skipped for now (T-005 rule). A related issue: a same-line `FoamFile {` is stored as an ordinary entry (`_foamFile` is `None`), so the first two writes differ by a blank line. | All → T-021 (one-line form), T-006 (same-line form) |

### Version-sensitive assumptions (no failure observed yet)

| Where | Assumption |
|---|---|
| `foamkit/__init__.py:15` | The release is read only from `WM_PROJECT_VERSION`, at import. `FOAM_API` and `WM_PROJECT_DIR` are ignored. |
| `foamkit/functions/foamVersion.py:1-4` | Returns the raw string (`"v2606"`, `"14"`, `"dev"`, `""`). |
| `foamkit/types/__init__.py:370-374`, `:44-49` | The default header for new files is decided at import time, from whether the version string starts with `v`. The ESI wording is unverified. |
| `foamkit/types/_isCase.py:12-14` | A case is a folder with `system/controlDict` and a `0` or `0.orig` folder. |
| `foamkit/types/__init__.py:2808-2818, 2889` | Modelled directives: `#include`, `#includeEtc`, `#includeFunc`, `#eval`, `#codeStream`, `#{ #}`. All other directives go through the verbatim path; T-004 verifies them. |
| `foamkit/types/__init__.py:3757-3758` | `ofStudy` restart uses `log.<application>`. That gives `log.foamRun` on Foundation 11+, which is fine, but the `solver` entry is ignored. |
| `foamkit/functions/getMonitor.py:47-48`, `getProbe.py:42-43`, `types/__init__.py:3172` | Assume the layout `postProcessing/<name>/<startTime>/<file>` and tab-separated column headers. |
| `foamkit/commandline/__init__.py:193` | `fk plot` defaults to `residuals`; ESI's equivalent is usually `solverInfo`. |
| Names | `turbulenceProperties`/`momentumTransport`, `RASModel`/`model`, `transportProperties`/`physicalProperties`, `fvOptions`/`fvModels`+`fvConstraints`, `simpleFoam`/`foamRun`+`solver`. These appear only in docs and user code; they are handled by the T-010 canonical mapping. |

The `bin/` shell scripts were removed by the maintainer on 2026-10-18 and are no longer in scope.

## 2. Architecture

1. **Lossless reading and writing first (no new API):** T-004, T-005, T-006, T-019, T-013, T-015, T-016, then T-020 (T-014 for best-effort). The goal is "write it back the way it was": original banners, directives, unit annotations and formatting of unedited entries.
2. **Release detection:** `foamkit/release.py` (T-008), with
   ```python
   FoamRelease(distribution, version, major, source)  # distribution: esi | foundation | foam-extend | unknown
   ```
   **Approved precedence:** explicit override or config, then the case banner, then the environment, then `unknown`. It never raises.
3. **Canonical names:** `foamkit/compat.py` (T-010).
   - The canonical base is **Foundation 14**. ESI and older-Foundation names are mapped onto it in **one data table** (`same`/`renamed`/`split`/`translated`/`none`), read by thin generic accessors.
   - The non-rename cases are handled explicitly:
     - ESI `fvOptions` → `fvModels` + `fvConstraints` (`split`);
     - `simpleFoam`/`pimpleFoam` → `foamRun` + `solver incompressibleFluid` (`translated`, via a lookup table).
   - When there is no equivalent, a `NoEquivalentError` is raised; the code never guesses.
   - Writes always keep the case's native names.
4. **Public API:**
   - Purely additive: `fkf.foamRelease()`, `case.release`, `case.canonical(...)`, `foamkit.compat.resolve`.
   - `FOAM_VERSION` and `foamVersion()` are unchanged.
   - Any later rename keeps the old name as an alias with a `DeprecationWarning`, as CLAUDE.md requires.

## 3. Testing (no OpenFOAM install)
- **Fixtures:** `tests/fixtures/releases/<family>/` for the eight tested releases. These are trimmed real tutorial files with LF line endings, plus a fact-check table (T-007). The licence is fine: both projects are GPLv3.
- **Parametrized round-trip tests** check presence of all files, byte-identical write, and one edit.
- **Best-effort behaviour** is covered only by small synthetic dicts in bug-specific tests (T-014, T-010 best-effort rows).
- **`@pytest.mark.openfoam`** is registered and skipped by default. CI against real containers is deferred.

## 4. Documentation
T-012 adds the Supported versions page. It depends on T-001 and T-007. It lists the tested and best-effort releases, the "four latest" update policy, and per-distribution notes taken from the fact-check table. Examples use `fkf`/`fkt`.

## 5. Ticket sequence (one at a time)

| Order | Ticket | Owner | Size | Depends on |
|---|---|---|---|---|
| — | T-004 include directives kept verbatim (B1). **Done** (cdfd3c6) | tester → implementer | S | T-002 |
| 1 | T-005 header-less `FoamFile` files recognised (B2); real banners pinned | tester → implementer | S | T-002 |
| 2 | T-006 header preserved byte-for-byte: Foundation, ESI, foam-extend (B3, B4); same-line `FoamFile {` (B10) | tester → implementer | S | T-005 |
| 3 | T-019 no trailing space after `;`, no extra blank line after FoamFile (B9) | tester → implementer | S | T-006 |
| 3a | T-021 one-line `FoamFile { ... }` block parsed and kept (B10) | tester → implementer | S | T-006 |
| 4 | T-017 `FoamKitError` becomes `Exception` (dual-base transition) | tester → implementer | S | T-002 |
| 5 | T-016 other directives; `ofVerbatimDirective`, `OF_DIRECTIVES` (names approved) (B7) | tester → implementer | M (may split) | T-004, T-017 |
| 6 | T-015 `#includeFunc` arguments, original quoting (option A approved) (B8) | tester → implementer | S | T-004, T-017 |
| 7 | T-013 unit-annotated values (B5) | tester → implementer | M | T-002 |
| 7a | T-003 README, T-001 Sphinx site (docs track; see ROADMAP) | docs-writer | S / M | — |
| 8 | T-007 tested-release fixtures + fact-check table | tester | M | T-004, T-005, T-006, T-013, T-015, T-016, T-019, T-021 |
| 8a | T-020 preserve padding/layout of unedited entries (B9) | tester → implementer | M (may split) | T-019, T-007 (corpus) |
| 6 | T-008 `FoamRelease` detection | tester → implementer | M | T-007 |
| 7 | T-010 canonical (Foundation 14) mapping table | tester → implementer | M (may split) | T-008 |
| 8 | T-009 new-file header from `detect()` | tester → implementer | S | T-008, T-006 |
| 9 | T-011 residuals/`solverInfo` and monitors | tester → implementer | S | T-007, T-010 |
| 10 | T-012 Supported versions page | docs-writer | S | T-001, T-007 |
| 10a | T-018 Directive support page, drift-tested against `OF_DIRECTIVES` | docs-writer | S | T-001, T-016 |
| 11 | T-014 legacy named dimensioned value loss (B6, best-effort) | tester → implementer | S | T-002 |

**Deferred:**
- write-side canonical helpers
- converting cases between distributions
- CI against real OpenFOAM containers
- modelling ESI `#if/#ifeq` as structured entries
- renaming the console's `pf`/`pt` aliases to `fkf`/`fkt` (needs a deprecation path)
- foam-extend name mapping in T-010, and full foam-extend case fixtures

## References: real-file sources (fetch with `curl -sfL` when exact bytes matter)
- **ESI (openfoam.com), GitLab raw:**
  - `https://gitlab.com/openfoam/core/openfoam/-/raw/master/tutorials/incompressible/simpleFoam/pitzDaily/system/controlDict` (master was v2606 on 2026-10-18/19).
  - For a specific release, replace `master` with that release's branch or tag after checking the repository's refs.
- **foam-extend, SourceForge raw:**
  - `https://sourceforge.net/p/foam-extend/foam-extend-5.0/ci/master/tree/tutorials/<path>?format=raw`
  - `https://sourceforge.net/p/foam-extend/foam-extend-4.1/ci/master/tree/tutorials/<path>?format=raw`
- **Foundation (openfoam.org):**
  - GitHub repositories `OpenFOAM/OpenFOAM-<N>`, raw files at `https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-<N>/master/tutorials/<path>`.
  - These are not yet fetched or checked by this plan; the T-007 tester confirms the URL pattern.
