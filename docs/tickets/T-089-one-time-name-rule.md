# T-089: one shared rule decides which directory names are times (`cloneCase`, the case parser, `ofProbe`), so a case with a `1e-05` or `-180` time directory loads

- **Issue:** [#123](https://github.com/mcgoldba/foamkit/issues/123)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (the T-063 rule moves to one module; four call sites swap a one-line test for it; one test table covers all sites)
- **Related:** T-063 (#83; added `_isTime`, `listTimes`, `latestTime`, `latestTimeName` in `foamkit/functions/_paths.py`), T-075 (#102; `1_0` is a word, not a number, in entries too), T-035 (#47) / T-020a (#27): not affected (folder attribute names are not written to any file; each folder is written back to its own path).
- **Depends on:** nothing. T-063 has merged.
- **Requested by:** the maintainer (2026-11-10): "Lets move the time directory code to a helper."

## Goal
Every place in FoamKit that asks "is this directory name a time?" uses the one T-063 rule, so cases with `1e-05`, `-1` or `-180` time directories load instead of crashing with a bare `TypeError`, and `cloneCase` no longer silently skips directories such as `nan` or `1_0` that are not times.

## Today (planner, reproduced on 401bb6c = `origin/main`, 2026-11-10)
The T-063 rule (`_isTime`): a finite decimal or exponent number, optionally signed; not `nan`/`inf`/underscores/hex/hidden names. Other sites use their own rule. Probe: each name added as a directory (with a `U` file in it) to a copy of `tests/fixtures/pitzDaily`, then `fkf.init` and `fkf.cloneCase`.

| Site (401bb6c) | Rule | Differs from `_isTime` on | Effect |
|---|---|---|---|
| `functions/cloneCase.py:72-78` (skip time dirs other than `0`) | `float(name)` succeeds | `nan`, `inf`, `infinity`, `1_0`, `1e999`, `١` (Arabic-Indic 1), `' 1'` count as times | **those directories are silently not copied** (not times, so they are case data); odd names, 0 tutorial dirs |
| `types/__init__.py:1215-1219` (directories at the case root) | `name.replace('.', '_')`, then `t_` if `split('_')[0].isdigit()` | `1e-05`, `-1`, `-180`, `1e999`, `1g`, `' 1'` get no prefix | **`init` crashes with a bare `TypeError: Field names must be valid identifiers: '1e-05'`** (also `-1`, `1g`, `1e999`); `nan`/`inf` load as `nan`/`inf` at the root but `t_nan`/`t_inf` inside a folder |
| `types/__init__.py:489` (`_parseNameTag`, used by the folder parser at 627, folder `__getitem__` at 574, dict keys at 2399/2415, monitor header keys at 4210) | `float(name.rstrip('.orig'))` succeeds (strips the *characters* `.orig`, not the suffix) | `nan`, `inf`, `1_0`, `1e999` count as times; `1g` and `0.o` too (`rstrip` removes `g`/`.o`) | non-times get a `t_` prefix (`t_nan`, `t_1g`); the names stay valid, so this is cosmetic. `1e-05` → `t_1e_05`, `-1` → `t__1`, `0.orig` → `t_0_orig` are right |
| `types/__init__.py:628` (folder parser, after `_parseNameTag`) | `t_` if `split('_')[0].isdigit()` | never fires after `_parseNameTag`, except digit-led non-numbers such as `2D`, which it misses (→ bare `TypeError`) | redundant second rule |
| `types/__init__.py:4007-4012` (`ofProbe.startTime` from `postProcessing/<name>/<time>/`) | `float(dirName)` succeeds | `nan`, `inf`, `1_0`, `1e999` set `startTime` | odd names only; `startTime` is not read inside FoamKit |
| `tests/test_underscore_tokens.py:24` | docstring listing `float(itemName.rstrip('.orig'))` at line 485 | — | update the listing when the call goes |

`5.` cannot be created on Windows (it becomes `5`); on Linux it behaves like `0.5` at every site. No site differs on `0`, `0.5`, `0.0`, `1.orig`, `0.orig`.

Real tutorials (`git ls-files`, path components that are time-like):

| Release | Root time dirs other than `0` | Time-named dirs elsewhere |
|---|---|---|
| Foundation 11 (9cbf94f) | `-180` (`XiFluid/kivaTest`, its only time dir, 13 files); `0.orig` in 3 cases | none |
| Foundation 14 (3155431) | `-180` (`kivaTest`); `0.orig` in 2 cases | `system/meshes/0.0015`, `0.003` (`incompressibleFluid/movingCone`), `1e-05`, `2e-05` (`shockFluid/movingCone`): folder parser, load as `t_1e_05` today and after |
| ESI v2606 | not checked (no clone available) | |

Run output is the larger source: OpenFOAM names time directories with its time format, so small write intervals give `1e-05`-style names (as the `movingCone` mesh directories show), and `fk init` on such a run case crashes today.

## Design (planner, 2026-11-10)
- **Where the helper lives:** a new private module **`foamkit/_times.py`**. Import graph: `foamkit/__init__.py` imports no subpackage; `foamkit/types/__init__.py` imports `from foamkit import ...` and its own `_isDictFile`/`_isCase`; `foamkit/functions/__init__.py` imports `foamkit.types`. So `foamkit.types` cannot import `foamkit.functions._paths` (circular), but both can import a root module that imports only `foamkit` (for `userMsg`), `os`, `re`, `math`. A root module, rather than `foamkit/types/_times.py`, keeps the rule independent of the parser module.
- **What moves:** `_TIME_NAME` → `TIME_NAME`, `_isTime` → `isTimeName`, and `listTimes`, `latestTime`, `latestTimeName` (all the time-directory code). The module is private, so its names drop the underscore without becoming public API; nothing is added to `fkf`/`fkt`.
- **`foamkit/functions/_paths.py` keeps its names** by importing them: `from foamkit._times import TIME_NAME as _TIME_NAME, isTimeName as _isTime, listTimes, latestTime, latestTimeName`. Private names, so plain aliases, no deprecation warning. T-063's tests and callers (`getLatestTime`, `getMonitor`, `getProbe`, `timeDirs`) do not change; `monkeypatch.setattr("foamkit.functions._paths.os.scandir", ...)` still works (it patches the shared `os` module).
- **The sites:**
  - `cloneCase`: skip a top-level directory when `isTimeName(name) and name != "0"`.
  - `_parseNameTag`: prefix `t_` when the name is a time, or a time followed by exactly one `.orig` suffix (`0.orig` → `t_0_orig`, as today), **or** its first character is a digit (`str.isdigit`), so digit-led non-times (`1_0` → `t_1_0`, `1g` → `t_1g`, `2D` → `t_2D`) stay valid attribute names as today. Only `nan`, `inf`, `infinity` and signed forms lose the prefix (they are valid names already).
  - Folder parser (628): drop the second `isdigit` rule; `_parseNameTag` decides alone.
  - Case root (1215-1219): use `_parseNameTag` like the folder parser, so the root and folders agree: `1e-05` → `t_1e_05`, `-180` → `t__180`, `1g` → `t_1g`.
  - Any folder name that still cannot be an attribute raises `FoamKitError` naming the directory, instead of a bare `TypeError` from `make_dataclass`.
  - `ofProbe`: set `startTime` only when `isTimeName(dirName)`.

## Scope
- New `foamkit/_times.py`; `foamkit/functions/_paths.py` (re-export); `foamkit/functions/cloneCase.py`; `foamkit/types/__init__.py` (`_parseNameTag`, `FolderParser.makeOFFolder`, `CaseParser.makeOFCase`, `ofProbe.__post_init__`); the listing in `tests/test_underscore_tokens.py`.
- Tests: a new `tests/test_time_names.py`, one table over the names `0`, `nan`, `inf`, `infinity`, `1_0`, `1e-05`, `0.5`, `-1`, `-180`, `5.` (Linux only), `1.orig`, `0.orig`, `0.o`, `1g`, `1e999`, `0.0`, `١`, for every site. Put a file in every test directory (see Out of scope).

## Out of scope (findings for the maintainer, not fixed here)
- `isCase`/`_isCase` require a `0` or `0.orig` directory, so stock `kivaTest` (start time `-180`) is not a case: `cloneCase` refuses it and `init` prints an INFO line and goes on. Whether "a case" means "a time directory" is a separate decision.
- `cloneCase` keeps only `0`, so a case starting at `-180` is cloned with no start-time directory.
- An **empty** folder anywhere in a case crashes `init` with a bare `UnboundLocalError` (`internalNames` is set inside the loop at `types/__init__.py:612` and read at 667).
- `case['0.5']` on the case object uses the raw attribute name (`ofCase.__getitem__` is `getattr`); folders map through `_parseNameTag`.
- Renaming the `t_` attributes, or making `isTimeName` public.

## Acceptance criteria
- [ ] **Failing tests first:** the `1e-05`, `-1`, `-180`, `1g`, `1e999` root rows (bare `TypeError` today), and the `cloneCase` rows for `nan`, `inf`, `infinity`, `1_0`, `1e999` (dropped today).
- [ ] `foamkit/_times.py` holds the only time-name rule; `grep -nE "float\((obj\.name|time_|itemName)|split\('_'\)\[0\]\.isdigit" foamkit/` finds nothing.
- [ ] `from foamkit.functions._paths import _isTime, _TIME_NAME, listTimes, latestTime, latestTimeName` works, and `tests/test_time_directories.py` passes unchanged.
- [ ] `fkf.init` on pitzDaily plus `1e-05/U`, `-1/U` or `-180/U` loads, with attributes `t_1e_05`, `t__1`, `t__180`; `case.t_1e_05.U` reads the file, and `case.write()` writes it back to `1e-05/U`.
- [ ] Attribute names at the root and inside folders are the same for every name in the table; `0` → `t_0`, `0.5` → `t_0_5`, `0.orig` → `t_0_orig`, `1_0` → `t_1_0`, `nan` → `nan` (pinned).
- [ ] `fkf.cloneCase` copies `nan`, `inf`, `1_0`, `1e999`, `1g`, `0.orig`, `1.orig` and skips `0.5`, `1e-05`, `-1`, `100`, `0.0`; `0` is copied.
- [ ] `ofProbe` on `postProcessing/probes/0.5/U` has `startTime == '0.5'`; on `postProcessing/probes/nan/U` it sets no `startTime`.
- [ ] A folder name that cannot become an attribute raises `FoamKitError` naming its path; no bare `TypeError`.
- [ ] Existing tests that use `t_0` (`tests/test_case.py`, `tests/test_preserve_layout.py`) pass unchanged.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): one time-name rule, so cases with 1e-05 or -180 time directories load (T-089)`; the commit body names the attribute names that change (`nan`/`inf` folder items lose `t_`) and the directories `cloneCase` now copies.

## Risks
- **Attribute-name change:** folder items and dict keys named `nan`, `inf`, `infinity` (and `-inf` etc.) lose the `t_` prefix. Python-assigned dict keys go through `_parseNameTag` too (`d['inf'] = 1`), so pin one dict-key row. Old `.params` caches keep their stored names.
- **`cloneCase` copies more:** directories named like `nan` or `1_0` are now copied; they are not time output.
- **Versions:** the rule is OpenFOAM's time-name format and the same for Foundation and ESI; `-180`-style negative start times come from the Foundation engine tutorials.
