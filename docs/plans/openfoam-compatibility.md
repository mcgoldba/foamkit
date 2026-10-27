# Plan: OpenFOAM multi-distribution support

## Support levels (maintainer decision, 2026-10-18)
- **Tested:** the four latest releases of each distribution. Each has a fixture in CI.
  - Foundation (openfoam.org): **11, 12, 13, 14**
  - ESI (openfoam.com): **v2412, v2506, v2512, v2606**
- **Best-effort, untested:** older releases (for example Foundation 7-10, ESI v2006-v2406) and anything newer than the tested set.
- **foam-extend (third distribution, added 2026-10-19):** 4.1 and 5.0 are **"headers tested (4.1, 5.0), otherwise best-effort"** (label approved 2026-10-19):
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
| B5 | Value and list parsing in `foamkit/types/__init__.py` | Unit-annotated values (forms guessed from the CFD Direct note; T-013 confirms the real syntax): `1.5e-05 [m^2/s]` becomes a plain string (not numeric); `(10 0 0) [m/s]` is **corrupted**, with the unit written inside the list; `uniform (10 0 0) [m/s]` **fails to parse** (`ValueError`). | Tested (Foundation 13/14 make input units standard) → T-013. *Real files, 2026-10-19:* no `[m/s]`-style forms in Foundation 13/14 pitzDaily; still unverified. |
| B11 (*real file*, 2026-10-19) | Dimension parsing | Foundation 14 `0/U` `dimensions [velocity];` (a named dimension set) parses as `ofStr('[velocity]')`, not as a dimension type. Foundation 13 `[0 1 -1 0 0 0 0]` is fine. | Foundation 14 → T-013 |
| B6 | `ofNamedDimension` parsing | `nu nu [0 2 -1 0 0 0 0] 1.5e-05;` is written as `nu [0 2 -1 0 0 0 0];`, so **the value is lost**. | Best-effort only (older `transportProperties`) → T-014 |
| B7 (re-inventoried 2026-10-21) | Directive dispatch and `_parseVerbatimEntry` in `foamkit/types/__init__.py` | Many directives fail to load. See **Directive inventory** below for per-release counts and the ticket that owns each. | Tested → T-016 (framework and single-line), T-026 (conditionals), T-027 (`#calc`/`#neg`), T-028 (next-line brace), T-029 (`#includeModel`/`#includeConstraint`) |
| B8 | `ofIncludeFunc` | `#includeFunc f(U)` is written quoted. `#includeFunc f(U, name=s)` fails to parse. | Tested. *Real file, 2026-10-19:* Foundation 11 `controlDict` `#includeFunc patchAverage(patch=inlet, fields=(p U))` fails, so **stock Foundation 11 pitzDaily cannot load**. → T-015 |
| B9 (*real file*, 2026-10-19) | Dict-file writer | An unedited read → write of the real ESI v2606 `controlDict` adds a trailing space after `;`, re-aligns key/value padding and adds a blank line after the FoamFile block. | All → T-019 (whitespace), T-020 (padding/layout) |
| B10 (2026-10-19) | `FoamFile` block parsing in `DictFileParser` | A one-line `FoamFile { ... }` block: with entries after it, `IndexError` (whole case fails); alone, written back as `FoamFile\n{\n}\n`, so its entries are **lost**. Header-less files with a one-line block, content after `{` on its line, `}` not at the start of its line, or content after `}` on its line are skipped for now (T-005 rule). A related issue: a same-line `FoamFile {` is stored as an ordinary entry (`_foamFile` is `None`), so the first two writes differ by a blank line. | All → T-021 (one-line form), T-006 (same-line form) |
| B12 (2026-10-19, T-015 review) | `_parseLineLenTwo` `foamkit/types/__init__.py:4143` | A one-line sub-dict (`p { type probes; }`) raises `IndexError` at top level, inside `functions {}`, and after `#include`, so `pf.init` fails for the whole case. | All → T-022 |
| B13 (*real files*, 2026-10-21) | `$` reference validation (`ofVar`) | Scoped references `$/a/b`, `$file!a/b` and `$../file!a/b` raise `ValueError: ... is not a valid key` (ESI freePiston `0/U:21`, Foundation 14 cylinder `fvSolution:55`, floatingBeam `blockMeshDict:17`). | → T-030 |
| B14 (*real files*, 2026-10-21) | Block-comment parsing and writing | Multi-line `/* … */` comments lose their newlines on write (ESI bendJunction `blockMeshDict`). ESI potentialFoam/cylinder `blockMeshDict` fails with "Could not find end of commented block". | → T-031 |
| B15 (2026-10-21) | Number printing | `5e-4` is written as `0.0005`: the source token is not kept. | → T-032 (related to T-020) |
| B16 (*real files*, 2026-10-21) | `ofCodeStream` writer | It writes `vertices #codeStream{` and adds a blank line per code line on **every** write (F14 floatingBeam, ESI potentialFoam/cylinder `blockMeshDict`). | → T-033 |
| B17 (2026-10-25, T-016 review on PR #46; pre-existing) | `_findDictOrListEndLine` (`foamkit/types/__init__.py:4852`) and the related end scan | Braces inside quoted strings, `//` and `/* */` comments and `#{ #}` code are counted. With `d { e { note "a } b"; inner 2; } mid 3; }`, `inner` moves into `d` and `mid` moves to the top level, and the structure shifts on every write. A `{` gives "Could not locate end of dict". None of the 18 `tests/releases/` files hit it. | All → T-035 (before T-031) |
| B18 (2026-10-26, T-035 tester; pre-existing) | Line-comment stripping in the entry and line parser | `//` inside a quoted string starts a "comment": `note "http://x";` fails with "Cannot handle single line entry" (top level and sub-dict), and a list item `"a//b"` is **silently truncated** to `"a`. `/*` inside a string is fine in the entry parser. There are 0 occurrences in Foundation 11-14 tutorials (ESI not re-checked). | All → T-036 (before T-031) |
| B19 (2026-10-26, found implementing T-035; pre-existing; widened by the T-037 tester) | `_parseList` `line.endswith(');')` check on a line with its trailing newline | Lists read back with an extra empty `ofStr` item: one-line lists (`x ( 1 );`, `x ( ")" );`) after a write → read cycle, **and multi-line lists on first read**. The damage compounds per cycle. 7 golden/case outputs encode the bug. | All → T-037 |
| B20 (2026-10-26, found implementing T-035; pre-existing) | `_parseListValues` | `delimiters.append(" ")` mutates the module-level `BRACKET_CHARS['list']`, which grows on every call (state leaks between parses). T-035 works around it with `[:2]`. | All → T-038 |
| B21 (2026-10-26, T-037 tester; pre-existing) | Tokenizing a keyword glued to `{` or `(` | `x(1);` raises `AttributeError`. `fields(p U);` is mis-split. One-line `x{ a 1; }` loses its `}` on write. Multi-line `x{` gives "Invalid syntax". Real Foundation 11 `multiphaseEuler/*/constant/phaseProperties` (6 files; e.g. `bubblePipe:65` `f10{dSph 10e-3; value 0.0;}`) fail with `IndexError`. Foundation 12-14 have 0 glued forms in dictionaries. | F11 → T-039 + T-022 |
| B22 (2026-10-27, T-037 review on PR #53; pre-existing) | One-line list items that are dicts (`_parseList`/`_parseListValues`) | `x ( a { v 1; } b { v 2; } );` hung for the reviewer (killed at 30 s). On an extracted `origin/main` (bc4af32) the planner saw no hang, but the list was written as `x ( );`: **every item silently lost**. Multi-line lists of one-line dicts lose the dict entries. | All → T-040 (proposed: fold in T-022) |
| B23 (2026-10-27, T-037 review on PR #53; pre-existing) | Line/entry parser | Entries after the first `;` on a line are silently dropped: `x 1; y 2;`, `a 1; sub { b 2; }`, `a 1; #include "f"`, `a 1; #print`. Real: 2-3 `blockMeshDict` files per Foundation release (F14 `fluid/helmholtzResonance:144-145`, `incompressibleVoF/rotatingCube:76-80`, `mesh/refineMesh/sector:32-38`). | All → T-041 |

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

## Directive inventory (real tutorial trees, 2026-10-21)
This is the reference for T-016, T-026..T-029, T-018 and `OF_DIRECTIVES`.
- **Counts:** dictionary files that use the directive, per release; "F" is Foundation 11/12/13/14, "E" is ESI v2412-v2606.
- **Gathered by:** the T-016 tester. The method is described below.

| Directive | Releases (count) | Example (real file) | Status today | Owner |
|---|---|---|---|---|
| `#include`, `#includeEtc`, `#includeFunc` | F, E | many | OK (T-004, T-015) | done |
| `#includeIfPresent` | F only, 1 per release | — | loads; written quoted | T-029 |
| `#sinclude` | E only, 3 | — | loads in 2 of 3 | T-029 tester checks the third; record it |
| `#includeModel` | F 4/4/7/7 | F14 `fluid/roomHeating/constant/fvModels:17` | loads; written quoted | T-029 |
| `#includeConstraint` | F 7/9/11/13 | F14 `XiFluid/engine2Valve2D/system/fvConstraints:17` `limitLowPressure(min=1e4)` | fails ("bracket type") | T-029 |
| `#calc` (value position) | F ~15/36/133/133; E 2 (IO test dict only) | F14 `incompressibleFluid/cylinder/system/blockMeshDict:27` | fails (`ofCalc` TypeError) | T-027 |
| `#neg` | F ~102/119/135/135 | same file `:29` `cylMin #neg $cylMax;` | fails ("bracket type") | T-027 |
| `#eval` | E only, ~330 | — | OK (`ofEval`) | done |
| `#codeStream` | F 1/1/1/4; E 14 | F14 `floatingBeam/system/blockMeshDict:21` | loads; writer unstable | T-033 |
| `#print` | F14 only, 25 uses / 24 files | F14 pitzDaily `constant/momentumTransport` | fails | T-016 |
| `#remove` | E only, 41-48 | E `basic/potentialFoam/cylinder/system/blockMeshDict:87` | fails | T-016 |
| `#if` | E only, 16 | E `IO/dictionary/good-if1.dict:21` (nested) | fails | T-026 |
| `#ifeq`, `#else`, `#endif` | F13, F14, E | F14 `incompressibleFluid/cylinder/system/fvSchemes:39` | fails | T-026 |
| `#inputMode` | E only, 1 | — | fails | T-016 |
| `#calcInclude` | F11-F13 only, 1 | F13 `fluid/aerofoilNACA0012Steady/0/U:21` | fails | T-016 |
| `#codeBlock`, `#endCodeBlock`, `#codeInclude` | F14 only, 7/7/1 | F14 `fluid/aerofoilNACA0012Steady/0/U:20-26` | fails | T-016 |
| `#codeDict` | F14 only, 2 | F14 `trayedPipe` `createZonesDict:24` (`{` on the next line) | fails | T-028 |
| `#message` | E, 4 | E `IO/dictionary/good-word-expand.dict:18,21,24` | fails | T-016 |
| `#word` | E, 3 | same file `:29,34,42` (`{` on the next line at `:34`) | fails | T-028 |

Notes:
- **Conditional blocks** can be nested (`good-if1.dict`), and dead branches can contain unbalanced braces (`good-if3.dict`), so the capture must be textual, up to the matching `#endif`.
- **`#codeDict` and `#word`** have their `{` on the next line, which breaks T-016's "bracket opened on the directive line" rule. Hence T-028.
- **A top-level `#calc "1+2"`** occurs in no tutorial.
- **The first real `value [unit]` form:** F14 `fluid/aerofoilNACA0012Steady/0/U:18` `angleOfAttack 0 [deg];` (T-013).
- **Test copies:** byte-exact copies of the cited files are in `tests/releases/` (added by the T-016 tester).

**Method.** Shallow, sparse (`tutorials/` only) clones:
- `git clone --depth 1 --filter=blob:none --sparse https://github.com/OpenFOAM/OpenFOAM-{11,12,13,14}`, default branch `master`. At gathering time OF14 was at `a4867fc` (2026-10-08).
- `git clone --depth 1 --filter=blob:none --sparse --branch OpenFOAM-v{2412,2506,2512,2606} https://gitlab.com/openfoam/core/openfoam`.
- Then `git sparse-checkout set tutorials`. Grep for `^\s*#[A-Za-z]\w*` (and value-position `\s#[A-Za-z]`) over dictionary files, and count files per directive per release.
- The working copies were in the session scratchpad (`clones/`, with a `count.py` tally script). They are not committed, so re-create them with the commands above.

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
| — | Done: T-002, T-004, T-005, T-006, T-015, T-017 (PR #34), T-025 (5c10d41) | | | |
| 1 | T-016 verbatim directive framework + single-line directives. **In progress** | tester → implementer | M | T-004, T-017, T-025 |
| 1a | T-035 brace scan skips strings, comments and `#{ #}` (#47); removes T-016's guard | tester → implementer | M | T-016 |
| 1a' | T-037 one-line list gains an empty item; reviewed golden regeneration (#49) | tester → implementer | S | T-035 |
| 1b | T-036 `//` inside quoted strings is not a comment (#48) | tester → implementer | S | T-035 |
| 1c | T-038 stop mutating `BRACKET_CHARS` (#50) | tester → implementer | S | — |
| 1a'' | T-040 one-line list of dicts: hang or silent emptying (#54) | tester → implementer | S (M with T-022) | — |
| 1b'' | T-041 second entry on a line silently dropped (#55) | tester → implementer | S | — (reuse T-035 scanner) |
| 1d | T-022 one-line sub-dicts (#29), moved up on the Foundation 11 `phaseProperties` evidence | tester → implementer | S | T-021 (shared tokenizing; optional) |
| 1e | T-039 keyword glued to `{`/`(` (#52) | tester → implementer | S | T-022 |
| 2 | T-027 value-position `#calc`/`#neg` (#38) | tester → implementer | S | T-016 |
| 3 | T-026 conditional blocks (#37) | tester → implementer | M | T-016 |
| 4 | T-030 scoped `$` references (#41) | tester → implementer | S | — |
| 5 | T-029 `#includeModel`/`#includeConstraint` (#40) | tester → implementer | S | T-015 |
| 6 | T-023 CLI user errors without traceback (#32) | tester → implementer | S | T-017, T-025 |
| 7 | T-031 block comments (#42) | tester → implementer | S | T-035, T-036 |
| 8 | T-033 `#codeStream` writer (#44) | tester → implementer | S | — |
| 9 | T-019 no trailing space / extra blank line (B9) | tester → implementer | S | T-006 |
| 10 | T-021 one-line `FoamFile { ... }` (B10) | tester → implementer | S | T-006 |
| 11 | T-022 one-line sub-dictionaries (B12) | tester → implementer | S | T-021 |
| 12 | T-013 named dimension sets (B11) + unit annotations (B5; `0 [deg]` now confirmed) | tester → implementer | M | T-002 |
| 13 | T-034 `userMsg` C1/bidi escaping, `str(FoamKitError)` (#45) | tester → implementer | S | T-025 |
| 14 | T-032 number formatting kept (#43) | tester → implementer | S | — (overlaps T-020) |
| 15 | T-028 `#codeDict`/`#word` next-line brace (#39) | tester → implementer | S | T-016 |
| 16 | T-003 README | docs-writer | S | — |
| 17 | T-024 remove `_interpretUnitsAndConvert` (approved) | implementer | S | T-017 |
| 18 | T-001 Sphinx site + Quickstart | docs-writer | M | — |
| 19 | T-007 tested-release fixtures + fact-check table | tester | M | the load-failure tickets above |
| 20 | T-020 preserve padding/layout of unedited entries | tester → implementer | M | T-019, T-007 |
| 21 | T-018 Directive support page | docs-writer | S | T-001, T-016 |
| 22 | T-008 → T-010 → T-009 → T-011 → T-012 → T-014 | as before | | |

**Deferred:**
- write-side canonical helpers
- converting cases between distributions
- CI against real OpenFOAM containers
- modelling ESI `#if/#ifeq` as structured entries
- renaming the console's `pf`/`pt` aliases to `fkf`/`fkt` (needs a deprecation path)
- foam-extend name mapping in T-010, and full foam-extend case fixtures

## Known gaps (not ticketed yet)
- **One-line `vertices 10;` reported by the T-016 tester:** the planner could **not** reproduce it at top level on 2026-10-21 (`vertices 10;` round-trips). If the tester has the file and line, add it to T-022 (one-line forms), or open a ticket.
- **Bare `except:` blocks swallow errors** (found during T-017, 2026-10-20). There are 13:
  - `foamkit/types/__init__.py` ×9 (`:452, 4866, 4891, 4898, 4904, 4910, 4937, 5646, 5685` as of the T-017 audit; the line numbers drift);
  - `foamkit/functions/dictUtil.py` ×3 (`:224, 282, 504`);
  - `foamkit/functions/_unitDecoder.py:63`.

  They catch everything, including `FoamKitError`, `KeyboardInterrupt` and real bugs, and often turn them into `None` or a fallback parse. T-017 leaves them alone.
- **Proposal:** yes, one ticket, but **after T-016 and T-022**. Those tickets rewrite the same parser paths in `types/__init__.py`, so narrowing the handlers first would churn twice.
  - Shape: tester-first, one test per site showing what each handler is meant to catch, then narrow it to that exception (usually `ValueError`/`KeyError`/`TypeError`). No behaviour change for valid input.
  - Size: S/M, split by file if needed (`types` vs `functions`).
  - Not opened as an issue yet. The planner writes it when T-022 lands.

## References: real-file sources (fetch with `curl -sfL` when exact bytes matter)
- **ESI (openfoam.com), GitLab raw:**
  - `https://gitlab.com/openfoam/core/openfoam/-/raw/master/tutorials/incompressible/simpleFoam/pitzDaily/system/controlDict` (master was v2606 on 2026-10-18/19).
  - For a specific release, replace `master` with that release's branch or tag after checking the repository's refs.
- **foam-extend, SourceForge raw:**
  - `https://sourceforge.net/p/foam-extend/foam-extend-5.0/ci/master/tree/tutorials/<path>?format=raw`
  - `https://sourceforge.net/p/foam-extend/foam-extend-4.1/ci/master/tree/tutorials/<path>?format=raw`
- **Foundation (openfoam.org):**
  - GitHub repositories `OpenFOAM/OpenFOAM-<N>`, raw files at `https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-<N>/master/tutorials/<path>`.
  - **Verified 2026-10-19 for 11-14:** `https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-{11,12,13,14}/master/tutorials/incompressibleFluid/pitzDaily/<file>`. Foundation 12/13/14 `controlDict` headers round-trip byte-identically after T-006.
