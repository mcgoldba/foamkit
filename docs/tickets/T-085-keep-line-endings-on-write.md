# T-085: `case.write()` keeps each file's line endings (LF stays LF on Windows, CRLF stays CRLF on Linux)

- **Issue:** [#113](https://github.com/mcgoldba/foamkit/issues/113)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (one read-side detection, one write call, one cached attribute)
- **Related:** T-020 (#27, T-020a; design note 4 left on-disk line ends out), T-083 (#111), T-050 (#67, `fk format` must keep the same rule).
- **Depends on:** T-020 (#27). Both touch `DictFileParser.__init__`/`ofDictFile` attributes and the cache, and T-020a's byte-identical criterion is on `toString()`; this ticket carries it to disk.
- **Maintainer decision to confirm at approval:** a file whose lines mix endings (0 tutorial files, see below). (A, recommended) The write raises `FoamKitError` naming the file and the first line whose ending differs from line 1, and that file is not written. (B) The file is written with the ending of its first line, with a one-time warning naming the file.

## Goal
Writing a case changes no line ending: a dictionary read with LF endings is written with LF, one read with CRLF is written with CRLF, on every OS, and a new file is written with LF (the OpenFOAM norm).

## Today (planner, reproduced on 839663c = `origin/main`, Windows 11, Python 3.12, 2026-11-08)
A pitzDaily copy whose `system/*` files were set to LF or CRLF, then `pf.init(path)` → `case.write()`; bytes of `system/controlDict` before and after:

| Source | `toString()` | On disk after `case.write()` (Windows) | Linux (code reading, not run) |
|---|---|---|---|
| LF (0 CR, 72 lines) | no CR | **CRLF on all 87 lines** | LF |
| CRLF (72 CR) | no CR | CRLF (87 lines) | **LF**: the CRLF is lost |

- Cause: `DictFileParser` reads with `open(filepath, 'r')` (universal newlines, so the ending is lost on read), and `ofCase.write` writes with `loc_.write_text(obj.toString())` (text mode, so `\n` becomes `os.linesep`). `fk write` calls `case.write()`.
- The cache (`.params/_case.json`, written by `case.save`/`writeCase` in text mode) holds no line-ending information, so a `save` → `load` → `write` cannot keep it either. The JSON file itself is CRLF on Windows; JSON reads either way.
- **Why it matters on Windows:** Git for Windows installs with `core.autocrlf=true` (system gitconfig on this machine), so a cloned case is CRLF while files from a tarball, WSL or a Linux cluster are LF. Every write of an LF case on Windows rewrites every line, so even after T-020a an unedited `case.write()` is not byte-identical on disk on Windows, and a `git diff` of the case shows every line changed.

Real files: the Foundation 11 and 14 tutorial repositories contain no CR in `HEAD` (`git grep -P '\r' HEAD -- tutorials`: 0 files). Checked out on this machine with `autocrlf=true`, 4727 (Foundation 11) and 5546 (Foundation 14) tutorial files are CRLF in the working tree, and 0 mix endings. The extracted ESI v2606 tutorial tree (no git conversion) has 212 files containing a CR; they were not split into CRLF and mixed (the scan timed out on this machine).

## Scope
- `foamkit/types/__init__.py`:
  - `DictFileParser.__init__` detects the file's ending from its bytes (`\r\n` or `\n`; mixed per the decision above) and stores it on the `ofDictFile` (e.g. `_newline`, listed in `_CLASS_VARS` like `_blank_lines_after`).
  - `ofCase.write`'s `_writeCaseObj` writes `toString()` with that ending and no translation: `open(path, 'w', newline='')` (or bytes) after replacing `\n`. `Path.write_text(newline=...)` needs Python 3.10, so it cannot be used (3.9 is supported).
  - A new `ofDictFile` (no source) gets `\n`.
- The cache: `_newline` goes out through `attrDict()` and back in `_parseCaseDict`, as `_blank_lines_after` does. A cache written before this ticket (no `_newline`) gives `\n` for every file, documented in the commit body.
- Tests: a new `tests/test_line_endings.py` that builds LF and CRLF copies of `tests/fixtures/pitzDaily` in `tmp_path` and compares **bytes**, so it checks the same thing on Linux and Windows CI.

## Out of scope
- The `.params` JSON cache's own line endings, and `fk setConfig`'s config file (FoamKit's own files, read only by FoamKit).
- The legacy line editors in `foamkit/functions` (`replaceEntry`, `appendEntry`, `removeEntry`, `removeBlockEntries` through `dictUtil`), which also rewrite case files in text mode. They are not on the `case.write()` path; listed here so they are not forgotten.
- Lone `\r` (classic Mac) endings: treated as "mixed" by the decision above.
- Text encoding: reading and writing use the locale default (no `encoding=`), a separate question.

## Acceptance criteria
- [ ] **Failing tests first**, comparing bytes on every OS: an LF case and a CRLF case, each through `init` → `case.write()` and through `init` → `save` → `load` → `case.write()`.
- [ ] Every written dictionary has the same ending on every line as its source: no `\r` in an LF file, every `\n` preceded by `\r` in a CRLF file.
- [ ] An edited entry and a new entry in a CRLF file are written with CRLF too; a new file is LF.
- [ ] A mixed-ending file behaves as decided at approval (A: `FoamKitError` with file and line, file not written; B: written with line 1's ending and a warning).
- [ ] Once T-020a has landed: an unedited `case.write()` of the pitzDaily fixture is byte-identical on disk to the source, on Linux and Windows CI, for both LF and CRLF copies.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): keep each file's line endings on write (T-085)`.

## Risks
- **Behaviour change:** on Windows, LF cases stop being converted to CRLF; on Linux, CRLF files stop being converted to LF. Users who relied on the conversion see it stop; say so in the commit body.
- **Interaction with T-020a:** its source text is read with universal newlines, so it holds no `\r`; the ending is applied once at write time to source and regenerated text alike. If T-020a's records are ever read with `newline=''`, the writer must not apply the ending a second time (no `\r\r\n`); a test pins this.
- **OpenFOAM versions:** none; line endings are a platform matter. Whether a given OpenFOAM build reads CRLF dictionaries was not checked; the fix keeps whatever the user had.
- **Old caches:** files loaded from a cache written before this ticket get LF.
