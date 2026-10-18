# T-004: Keep `#sinclude`, `#includeIfPresent` and other include variants intact on write

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Plan:** docs/plans/openfoam-compatibility.md, bug B1

## Goal
Reading and writing a dictionary that contains `#sinclude "x"` or `#includeIfPresent "x"` writes back the same directive. Today it is silently changed to `#include "x"`, which makes a missing optional file fatal in OpenFOAM.

## Scope
- `foamkit/types/__init__.py`:
  - the dispatch at `:3962-3964` (`'include' in lineList[0]`);
  - `_parseIncludes` at `:4686-4697`;
  - the `ofInclude` family at `:2780-2818`.
- Tests in `tests/test_regressions.py` or a new `tests/test_directives.py`, with a fixture dict under `tests/fixtures/dicts/`.

## Out of scope
- Modelling `#if/#ifeq/#else/#endif`, `#calc`, `#remove`, `#includeModel` as structured types. They only need to round-trip, which they may already do via the verbatim path; the tester confirms.
- Resolving or reading the included files.

## Acceptance criteria
- [ ] A new failing test shows that `#sinclude "a"` and `#includeIfPresent "b"` both become `#include` after `DictFileParser(...).readDictFile().toString()`. Reproduction steps are in the plan doc.
- [ ] After the fix, both directives are written back with their original keyword. `#include`, `#includeEtc` and `#includeFunc` output is unchanged (existing golden tests pass unmodified).
- [ ] Any other `#include*` keyword the parser does not know is kept verbatim, never changed to `#include`.
- [ ] A `#includeFunc` with arguments (for example `#includeFunc streamlines(U)`) round-trips unchanged. If it does not, the tester adds it as a test marked `xfail` with a reason, plus a note in this ticket.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- If a new type for these directives is exposed (for example `ofSInclude`), it is public API. Prefer a `keyword` attribute on `ofInclude` over new classes.
- The test fixture's syntax must be valid on both distributions. Check that `#includeIfPresent` is still accepted by Foundation 11+ before relying on it in docs.
