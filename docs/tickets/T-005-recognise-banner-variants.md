# T-005: Recognise boxed-banner and bannerless dictionary files

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Plan:** docs/plans/openfoam-compatibility.md, bug B2

## Goal
`pf.init` loads every OpenFOAM dictionary in a case, whether its header uses the open banner, the boxed `| ... |` banner (common in ESI and older files) or no banner at all (`FoamFile {}` first). Today the last two are silently left out of the case.

## Scope
- `foamkit/types/_isDictFile.py` (banner constants `:12-13` and the detection logic)
- `foamkit/functions/isDictFile.py`, if it duplicates that logic
- `tests/test_isdictfile.py`
- One added case test that runs `pf.init` on a case with a boxed `system/controlDict`

## Out of scope
- Header preservation on write (T-006)
- Release detection (T-008)

## Acceptance criteria
- [ ] New failing tests show that a boxed-banner `controlDict` is missing from `pf.init(...).system`, and that `_isDictFile` returns False for both variants. The plan doc has a reproduction.
- [ ] After the fix:
  - all three header styles are recognised;
  - binary files are still rejected;
  - non-OpenFOAM text files are still rejected;
  - files over `dict_filesize_limit` are still rejected.
- [ ] Every existing case in `tests/test_isdictfile.py` still passes unchanged.
- [ ] The parsed values of a boxed-banner file equal those of the same file with an open banner.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline.

## Risks
- Loosening detection may pull in non-dictionary files, for example `postProcessing` data or scripts, and slow down `init` or make it fail. The tests must include negative cases.
- The fixture banner text must be copied from a real ESI tutorial file, not written from memory.
