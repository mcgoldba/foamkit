# T-022: Parse one-line sub-dictionaries (`p { type probes; }`) instead of raising IndexError

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S. If keeping the layout unchanged needs T-020's source-text mechanism, do only the "keep every entry" part here and leave layout to T-020.
- **Plan:** docs/plans/openfoam-compatibility.md, bug B12
- **Related:** T-021 handles the one-line `FoamFile { ... }` block. This ticket covers every other sub-dictionary. Do whichever lands second on top of the first; share the one-line tokenizing if possible.

## Goal
A dictionary that contains a sub-dictionary written on one line, for example `p { type probes; }`, loads, and is written back the way it was. Today the whole case fails to load.

## Bug on HEAD (confirmed by the T-015 reviewer, 2026-10-19; unrelated to `#includeFunc`)
- `p { type probes; }` raises `IndexError` at `lineList[1][-1]` in `_parseLineLenTwo` (`foamkit/types/__init__.py:4143`; the method starts at `:4132`).
- It happens at top level, inside `functions { }`, and after a `#include` line.
- `pf.init` fails for the whole case, because `IndexError` is not a `FoamKitError`.

## Scope
- The line-classification path in `DictFileParser` (`_parseLineLenTwo` and its caller near `:4116`): recognise `name { ... }` that opens and closes on the same line, and parse its entries like a multi-line sub-dict.
- Writing:
  - an unedited one-line sub-dict is written back on one line, unchanged;
  - if that needs T-020, write it multi-line but keep every entry and value, and add a strict xfail for byte-identity that references T-020;
  - edited one-line sub-dicts may be written multi-line, which is today's style for edited entries.
- Tests in `tests/test_regressions.py` or a new `tests/test_one_line_dicts.py`.

## Possible addition (unverified, decide during Step 1)
- Multi-line `#includeFunc` arguments (`#includeFunc foo(a,\n b)`) fail cleanly with `FoamKitError` today, after T-015.
- **It is not verified that OpenFOAM accepts this form.** The tester checks the Foundation 11-14 / ESI v2412+ sources or tutorials (plan References).
- If OpenFOAM accepts it, add a round-trip test and the fix here. If not, record "rejected by OpenFOAM, current FoamKitError is correct" and drop it.

## Out of scope
- The one-line `FoamFile { ... }` block (T-021)
- One-line lists (`libs ("a.so");`), whose re-flow is already tracked under T-020

## Acceptance criteria
- [ ] **Failing tests first:** `p { type probes; }` raises `IndexError` today at top level, inside `functions { }`, and after a `#include` line. There is also a `pf.init` case test with such a `controlDict`.
- [ ] After the fix, all three positions parse, `d.p.type.value == "probes"` (or the equivalent attribute access), and `pf.init` succeeds.
- [ ] Multiple entries (`p { type probes; fields (p U); }`), an empty sub-dict (`p { }`) and a nested one-line sub-dict (`a { b { c 1; } }`) parse correctly.
- [ ] An unedited write is byte-identical to the source. Or, if T-020 is needed, every entry and value is kept, with a strict xfail that references T-020. The PR states which.
- [ ] Write 1 == write 2.
- [ ] Malformed input (`p { type probes;`, unterminated) raises `FoamKitError` with the file and line, never `IndexError`, and does not swallow the rest of the file.
- [ ] The "Possible addition" is resolved and recorded either way.
- [ ] All existing golden files are unchanged. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Classification:** a line such as `name { ... }` could also be a value containing braces (for example inside `#codeStream` or `#{ #}` blocks). Verbatim code blocks must keep their current handling, so add a test that a `#{ ... #}` block is unaffected.
- **How often the form occurs:** it is probably more common than the one-line `FoamFile`, because hand-written `functions {}` entries often use it. The tester greps the real-file sources and records what it finds.

## Ranking rationale
This ticket goes right after T-021, and before T-013.
- **Severity:** like T-021, it makes a whole case fail to load, and it is S.
- **Order after T-021:** T-021's one-line `FoamFile` tokenizing is the narrower case of the same mechanism, so doing it second reuses that work.
- **Before T-013:** a hard load failure outranks T-013's typed-value improvements.
- **After T-019:** T-019 is cheap and gates T-007, and it affects every file.
