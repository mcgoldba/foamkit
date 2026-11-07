# T-067: Optional dev test comparing parsed values with foamlib on the real-file corpus

- **Issue:** [#87](https://github.com/mcgoldba/foamkit/issues/87)
- **Type:** code, tests only (owner: `tester`)
- **Size:** S
- **Depends on:** T-020 (so the comparison covers written output too)

## Goal
A contributor with foamlib installed can run one test module that reports, for every file in `tests/releases/` and `tests/fixtures/pitzDaily`, whether FoamKit and foamlib load it and whether the values they read agree, so parser regressions and gaps show up against an independent reader.

## Scope
- `tests/test_foamlib_comparison.py`:
  - `pytest.importorskip("foamlib")` at the top, so the module is skipped wherever foamlib is not installed (foamlib needs Python 3.12+, and CI also runs 3.9).
  - For each corpus file: load with FoamKit and with foamlib; when both load, compare keys and plain values (numbers, words, lists of numbers) entry by entry; when only one loads, record which.
  - The current known differences are listed in a table in the test module, each as `xfail(strict=True)` with the FoamKit ticket that closes it, so a new difference fails and a fixed one is noticed.
- A short note in `tests/releases/README.md` (or the test module docstring) on how to run it.

## Out of scope
- Adding foamlib to `dependencies`, any extra, `environment.yml` or CI. It stays a manual, opt-in check.
- Any use of foamlib code inside `foamkit/`.

## Acceptance criteria
- [ ] Without foamlib, `pytest -q` reports the module as skipped on 3.9 and 3.12.
- [ ] With foamlib installed (Python 3.12+), the module runs, and every difference is either an `xfail` naming a ticket or a pass.
- [ ] No change under `foamkit/`, `pyproject.toml`, `environment.yml` or `.github/`.
- [ ] `ruff` shows no new findings compared with the CI ratchet baseline.

## Risks
- The two readers represent values differently (for example dimensioned values and directives); compare only plain values and list everything else as "not compared" rather than forcing a mapping.
- foamlib's API may change between versions; record the version the table was made with.
