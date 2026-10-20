# T-005: Recognise header-less `FoamFile` dictionaries; pin real banner recognition

- **Issue:** [#12](https://github.com/mcgoldba/foamkit/issues/12)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Plan:** docs/plans/openfoam-compatibility.md, bug B2 (corrected 2026-10-19)

## Goal
`pf.init` loads dictionary files that start directly with a `FoamFile` block and have no banner; today they are silently left out. The real banner styles (Foundation open, ESI boxed and foam-extend boxed), which are recognised today, are pinned by tests so they stay recognised.

## Correction (2026-10-19)
The earlier claim that boxed ESI files are dropped was **wrong**. It came from a probe file written from memory that had single backslashes (`| \      /  F ield`), whereas real files have `\\`. Real files fetched on 2026-10-19 are all recognised today by `_isDictFile`, and `DictFileParser` reads every entry:
- ESI v2606 pitzDaily `system/controlDict`;
- foam-extend 4.1 and 5.0 pitzDaily `system/controlDict`.

URLs are in the plan's References section.

## Scope
**Bug part.** Header-less dictionaries, in `foamkit/types/_isDictFile.py` (and `foamkit/functions/isDictFile.py` if it duplicates the logic). A file is a header-less dictionary when all of the following hold:
- its first non-blank line is `FoamFile`;
- `{` follows on the same line or the next non-blank line;
- that block contains a `class` or `format` entry;
- **the block is multi-line, in a shape the parser can read:** after `{` the rest of its line is blank, and the closing `}` is the first non-whitespace character on its line, and after `}` the rest of its line is blank or holds only `;` and/or a `//` comment (review rounds 2 and 3, 2026-10-19). Shapes such as `FoamFile { format ascii;\n...\n}`, `FoamFile {\n... }` or `FoamFile\n{\n...\n} application simpleFoam;` are skipped for now, like the one-line form (T-021).

**The one-line form `FoamFile { ... }` is not recognised for now** (maintainer decision, 2026-10-19). It stays skipped, as on HEAD. `DictFileParser` cannot parse it yet:
- with entries after the block it raises `IndexError`, so `pf.init` would fail for the whole case;
- with only the block, it writes back `FoamFile\n{\n}\n`, losing `version`/`format`/`class`.

**T-021** fixes the parser and widens this rule back.

**Characterization part.** Real-header fixtures under `tests/fixtures/headers/`:
- `esi-v2606.controlDict`, `foam-extend-4.1.controlDict`, `foam-extend-5.0.controlDict`, copied byte-for-byte from the real files (trim the body after the header if you want, but leave the header unchanged);
- the existing Foundation open header from `tests/fixtures/pitzDaily`.

Tests in `tests/test_isdictfile.py`, plus one `pf.init` case test with a header-less `system/fvSchemes`.

## Out of scope
- Header preservation on write (T-006) and other writer formatting (T-019, T-020)
- Parsing the one-line `FoamFile { ... }` form (T-021)
- Release detection (T-008)
- Warnings for skipped files. Skipped files stay silent (maintainer decision).

## Acceptance criteria
- [ ] Characterization tests (passing before and after): the ESI v2606, foam-extend 4.1, foam-extend 5.0 and Foundation open headers are recognised, and every entry is read.
- [ ] **Replace** any test fixture holding a from-memory foam-extend banner (for example one with a plain-dash first line) with the real header text. Record the source URL in a comment.
- [ ] A new failing test shows that a header-less `FoamFile { class dictionary; ... }` file is rejected and missing from `pf.init(...)`. After the fix it is recognised and loaded.
- [ ] These existing rejections stay unchanged:
  - `no_banner`, a repeated empty `FoamFile\n{\n}\n` with no `class`/`format`;
  - `indented_banner`;
  - the BOM case;
  - binary files;
  - files over `dict_filesize_limit`.

  All existing parametrized cases in `tests/test_isdictfile.py` pass unmodified.
- [ ] A text file whose first non-blank line is `FoamFile` but which has no `class`/`format` in the block is rejected.
- [ ] A header-less one-line `FoamFile { version 2.0; format ascii; class dictionary; }` is **rejected** (skipped, not loaded). `pf.init` on a case containing one still succeeds without that file. The same holds for the other shapes in the `UNPARSEABLE` test group (content on the `{` line, `}` mid-line, content after `}`). Each has a recognition test marked `xfail(strict=True, reason="T-021: FoamFile block shape not parseable yet")`.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- Loosening detection may pull in non-dictionary files. The `class`/`format` requirement and the negative tests guard against that.
- **Fixture text must come from real files**, fetched with `curl -sfL` so the bytes are exact, never retyped.

## Completion notes (implementer)
- `foamkit/types/_isDictFile.py`: new `_hasHeaderlessFoamFile(text)`, tried only when banner detection fails. It scans at most the first 4096 characters with `str` methods plus one linear regex over the block (no backtracking risk). It requires `FoamFile` at column 0 of the first non-blank line, `{` as the next non-whitespace character, a closing `}` within the window (unterminated blocks are rejected), at least one newline between `{` and `}` (the one-line form is rejected for now, T-021), and `class`/`format` inside the block. Banner detection is unchanged. Size and binary checks run before it, unchanged.
- `DictFileParser.readDictFile` (`foamkit/types/__init__.py`): a file whose first non-blank line is exactly the word `FoamFile` (`re.match(r'FoamFile(?=[\s{]|$)')`) skips `_findEndOfHeader` and sets `_header = None`, so `ofDictFile.toString()` writes no banner (existing `hasattr(self._header, 'toString')` guard). `FoamFileExtra` takes the old path and raises "Invalid OpenFOAM file specified" as on HEAD. Blank lines between `FoamFile` and `{` are skipped.
- Bounds: the blank-skip loops (after the header, and after `FoamFile`) stop at the end of the file and call `userMsg(..., 'ERROR')`, so a file ending in `FoamFile` plus blank lines raises FoamKitError, on both the header-less and the banner path (the latter was a pre-existing IndexError).
- Writing: a header-less file round-trips without gaining a banner. Header preservation for banner files stays with T-006.
- Not fixed, owned by T-021: the one-line `FoamFile { ... }` form is not recognised, so `pf.init` skips it.
- Round 2: besides the newline rule, `_hasHeaderlessFoamFile` now requires the rest of the `{` line to be blank and the first `}` to be the first non-whitespace character on its line. This rejects the parser-crashing shapes `FoamFile { format ascii;` and `... class dictionary; }` on one line. A block with a quoted `}` (e.g. `note "a}b";`) is rejected too; this is intended and fail-safe, with no quote-aware scanning.
- Round 3: after the closing `}`, the rest of its line must be blank or hold only `;` and/or a `//` comment (checked with `str` methods on that one line). `} application simpleFoam;` is rejected; `};` and `} // end of header` are accepted.
- Round 4: the tail after `}` is taken raw from the full text (that one line only, not the 4096-character window). At most one leading `;` is dropped, then the rest is stripped and must be empty or start with `//`. So `} ;`, `}	;` and `} ;// x` are rejected, while `}`, `};`, `}; // x` and `} // x` are accepted.
- Residual, owned by T-021/T-016 (reviewer, round 5): a non-breaking space around the braces, a lone `}` inside a block comment, and `#inputMode` in the block are accepted but raise `FoamKitError`, as they already do with a banner. None of them corrupts a write.
- Results: `pytest -q` 421 passed, 1 skipped, 9 xfailed on both the conda env and the py39 env.
