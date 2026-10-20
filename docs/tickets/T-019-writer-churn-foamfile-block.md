# T-019: Writer churn: no trailing space after `;`, no extra blank line after the FoamFile block

- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Plan:** docs/plans/openfoam-compatibility.md, bug B9
- **Depends on:** T-006
- **Split:** this is the mechanical part of the maintainer's "writer formatting churn" ticket. Key/value padding and layout preservation are design work, split off into **T-020**.

## Goal
An unedited read → write no longer adds trailing whitespace or blank lines that were not in the source. This is the first step towards "write it back the way it was".

## Evidence (2026-10-19, real ESI v2606 pitzDaily `controlDict`)
On write:
- a trailing space is added after `;`. Seen at least in the `FoamFile` block, for example `version     2.0; `; the tester lists every place it happens;
- a blank line is added after the `FoamFile` block closing `}`.

## Scope
- The `toString` of the `FoamFile` block / `ofFoamFile` and the dict-file writer in `foamkit/types/__init__.py`, wherever trailing `; ` and the post-FoamFile blank line are produced
- Regenerated goldens (`FOAMKIT_UPDATE_GOLDEN=1`)

## Out of scope
- Key/value column padding, list layout and any other re-alignment (T-020)
- Header banner (T-006)

## Acceptance criteria
- [ ] Failing tests on the real ESI v2606, foam-extend and Foundation pitzDaily fixtures: the written output contains `; \n`, and an extra blank line follows the FoamFile block where the source has none.
- [ ] After the fix:
  - no written line ends in whitespace (asserted over all goldens);
  - the line count between the FoamFile `}` and the next non-blank line equals the source's.
- [ ] **Golden diffs are limited to** removing trailing spaces and the extra blank line. The reviewer checks this with `git diff --stat` and `git diff -w` on `tests/golden/`: `-w` shows only blank-line changes.
- [ ] `test_repeated_writes_converge` still passes.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline. There is a `fix:` commit whose body describes the user-visible change.

## Risks
- Every golden file changes (whitespace only). That is a large but mechanical diff, so review it with `-w`.

## Should it precede T-007?
**Yes.** It is cheap, and without it every T-007 fixture fails byte-identity for a known, uninteresting reason. T-020 does **not** need to precede T-007: T-007 records any remaining padding/layout differences as `xfail(strict=True)` referencing T-020, and those fixtures then become T-020's test corpus.
