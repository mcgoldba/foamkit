# T-021: Parse the one-line `FoamFile { ... }` block (banner and header-less files)

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Plan:** docs/plans/openfoam-compatibility.md, bug B10
- **Depends on:** T-006, which makes the same-line `FoamFile {` form populate `_foamFile`. This ticket extends that path to blocks that also close on the same line.

## Goal
A dictionary whose `FoamFile` block is written on one line, for example `FoamFile { version 2.0; format ascii; class dictionary; object fvSchemes; }`, loads, and its `FoamFile` entries survive an unedited write. This holds with a banner and without one.

## Bug on HEAD (data loss, found while doing T-005)
- **Banner file, one-line block, entries after it:** `DictFileParser` raises `IndexError`, so `pf.init` fails for the whole case.
- **Banner file, only the one-line block:** it is written back as `FoamFile\n{\n}\n`. `version`, `format`, `class` and `object` are **lost**.
- **Header-less file:** skipped by `_isDictFile` since the T-005 rule decision. The one-line test is a strict xfail pointing here.
- **Related shapes, same parser limitation:** content after `{` on its line (`FoamFile { format ascii;\n    class dictionary;\n}`), `}` not at the start of its line (`FoamFile {\n format ascii; class dictionary; }`), and content after the closing `}` on its line (`FoamFile\n{\n    format ascii;\n    class dictionary;\n} application simpleFoam;`, which loads with a bogus `}` key and is written back with a stray `}`), and whitespace between `}` and `;` (`} ;`, which raises `ValueError: String cannot be converted to a word.`). With a banner they raise `IndexError` or corrupt on write on HEAD; header-less they are skipped by the T-005 rule and have strict xfails pointing here.
- **Direct `DictFileParser` use on a header-less one-line block** (bypassing `_isDictFile`): returns a dict with the `FoamFile` entries lost, where HEAD raised "Invalid OpenFOAM file specified". Normal `pf.init` use is gated by `_isDictFile`.

## Scope
- `FoamFile` block parsing in `DictFileParser` (`foamkit/types/__init__.py`, the `FoamFile` branch near `:3856-3862` and `_parseFoamFile` near `:4672`). Tokenize a block that opens and closes on one line.
- `ofFoamFile.toString()`: an unedited block is written back in its original one-line form, consistent with T-019/T-020's "write it back the way it was". If keeping the layout needs T-020's source-text mechanism and that has not landed, write it multi-line but keep **every** entry (see the acceptance criteria).
- `foamkit/types/_isDictFile.py`: widen the header-less rule back to accept the one-line form. Remove the T-005 multi-line condition.
- Tests: `tests/test_isdictfile.py` (`one_line_block`) and a banner-file regression test in `tests/test_banner_variants.py` or `tests/test_regressions.py`.
- **Residual shapes from the T-005 review (round 5).** These are accepted by the header-less rule but raise a clean `FoamKitError` naming the file and line. Banner files behave the same on HEAD.
  - A non-breaking space (U+00A0) before `}`, after `{`, or between `FoamFile` and `{`. Python's `str.strip()` treats it as whitespace but the parser doesn't, and it isn't valid OpenFOAM. Make the whitespace checks in `_hasHeaderlessFoamFile` ASCII-only (`strip(' \t\r\n\f\v')`) so these are skipped as on HEAD.
  - A lone `}` inside a `/* ... */` block comment within the FoamFile block.
  - `FoamFile{` with no whitespace before the brace. It got through the committed T-005 rule and crashed `pf.init` ("Invalid syntax on line 1"). T-006 now rejects it for header-less files, and it has strict xfails pointing here. With a banner it raises `FoamKitError`, as on HEAD.
  - A short header (a `*/` before line 6, e.g. a `note */` line before the banner) raised `IndexError` in `ofHeader`. T-006 stops the crash: the file loads and `note */` is kept verbatim. But `_findEndOfHeader` stops at the first `*/`, so the real banner after it is parsed as a body comment, flattened onto one line on write, and `FoamFile` becomes an ordinary entry. The written file is valid OpenFOAM but `_isDictFile` no longer recognises it, so it silently drops out of the next `pf.init`, and write 1 ≠ write 2. Fix: make `_findEndOfHeader` end at the `*/` that closes the banner `_isDictFile` located. Then strengthen `test_short_header_loads_and_is_written_back_verbatim` to assert that the output is re-recognised and that write 1 == write 2.
  - `FoamFile {` (NBSP between `FoamFile` and `{`) is still accepted header-less, because `str.isspace()` counts NBSP, and then crashes `pf.init`. This is covered by the ASCII-only whitespace fix above (`head[after] in ' \t\r\n\f\v'`).
  - `ofHeader([])` gives an empty header. The parser never passes an empty list; `isDefault = not rawLineList` would make it fall back to the default.
  - `#inputMode merge` inside the block (directive handling is T-016).
  - A FoamFile block padded so that `}` sits near character 4095. It loads, but the writer's re-padding pushes `}` past the 4096-character window, so the written file is no longer recognised. Contrived (needs a ~4 kB FoamFile block).
  - Add to the T-005 invariant test's generator: brace line `FoamFile\n{ `, closing line ` }`, and an "inner lines" dimension with `    #inputMode merge` and `    /*\n}\n    */`.

## Out of scope
- One-line forms of other sub-dictionaries (`p { type probes; }`): **T-022**
- Header banner handling (T-006)

## Acceptance criteria
- [ ] **Failing tests first.** Banner file plus one-line block plus following entries raises `IndexError` today. Banner file plus one-line block alone loses its `FoamFile` entries on write.
- [ ] After the fix, both banner cases parse, and `_foamFile` holds `version`, `format`, `class` and `object` with their values.
- [ ] An unedited write is **byte-identical** to the source. If T-020 has not landed, it is at least multi-line with every `FoamFile` entry and value kept. State in the PR which of the two was achieved, and if it is the latter, add a strict xfail for byte-identity referencing T-020.
- [ ] `test_repeated_writes_converge`-style check: write 1 == write 2 for both forms.
- [ ] The header-less one-line form and the two related shapes are recognised by `_isDictFile` and loaded by `pf.init`; the T-005 rule is widened back accordingly. The T-005 strict-xfail markers are removed and those tests pass, and the paired T-005 "rejected for now" tests are deleted.
- [ ] The T-005 negatives still reject: no `class`/`format`, unterminated block, BOM, indented banner.
- [ ] All existing golden files are unchanged. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline. There is a `fix:` commit whose body describes the user-visible change.

## Risks
- **How often the form occurs:** OpenFOAM-written files and the tutorials checked so far use the multi-line form, so the one-line form is expected mainly in hand-written or generated files. The tester greps the real-file sources (plan References) and records whether any tutorial uses it.
- **Untrusted input:** the one-line scan must be bounded by the line, or by the closing `}` within T-005's 4096-character window. An unterminated block must not consume the file.

## Ranking rationale
This ticket goes right after T-019, and before T-017.
- **Data loss on HEAD for banner files,** and it can fail a whole case: the same class of bug as T-006 and T-019.
- **It builds on T-006's `FoamFile`-block fix,** and it finishes the header/`FoamFile` part of "write it back the way it was" before T-007 needs byte-identical round trips.
- **It is S,** and the input form is expected to be rare, so it does not jump ahead of T-006 and T-019, which affect every ESI and foam-extend file.
