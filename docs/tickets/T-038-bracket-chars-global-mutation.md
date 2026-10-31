# T-038: `_parseListValues` mutates the module-level `BRACKET_CHARS['list']`

- **Issue:** [#50](https://github.com/mcgoldba/foamkit/issues/50)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Found by:** the T-035 implementer (2026-10-26). It is pre-existing on main.

## Goal
Parsing a file has no side effects on module-level state, so results never depend on what was parsed before.

## Bug
- `_parseListValues` (`foamkit/types/__init__.py`, about `:4660` on the T-035 branch) takes `delimiters` from the module-level `BRACKET_CHARS['list']` (`:56`) and calls `delimiters.append(" ")` (about `:4699`).
- So the global list **grows by one `" "` on every call**, and the state leaks between parses and files.
- T-035 worked around it by slicing `BRACKET_CHARS['list'][:2]` where it reads the brackets. That hides the symptom but not the leak.
- **Measured cost (T-048 review round 2, note 4):** the `in delimiters` scan in `_parseListValues` gets slower with every parse in a session. Re-parsing `tests/releases/foundation-14.concentricCylinders.blockMeshDict.orig` takes 0.03 s the first time and 0.37 s the 80th, the same on main and after T-048. This likely explains the flaky timing tests `test_big_one_line_list_of_dicts_*` in `tests/test_one_line_blocks.py` and the sweep timeouts. Since T-048, no reader depends on the appended spaces, so the fix can be `delimiters = BRACKET_CHARS['list'] + [" "]`.

## Scope
- Use a local copy in `_parseListValues` (`list(BRACKET_CHARS['list']) + [" "]`), or make `BRACKET_CHARS` immutable (tuples). Do the latter only if the tester confirms nothing else mutates it on purpose.
- Remove T-035's `[:2]` workaround once it is no longer needed.

## Out of scope
- Other parser refactoring

## Acceptance criteria
- [ ] **Failing test first:** snapshot `BRACKET_CHARS` (deep copy), parse a file containing a list twice, and assert the global equals the snapshot. Today it fails, because the list grew.
- [ ] After the fix, that test passes, and parsing the same file twice gives identical `toString()` output.
- [ ] T-035's `[:2]` slice is removed, or kept with a comment explaining why. All tests still pass.
- [ ] No golden file changes.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the change.

## Risks
- **Hidden reliance on the grown list:** some code may rely on `" "` being in `BRACKET_CHARS['list']` because of the growth. The tester greps every reader of `BRACKET_CHARS`.

## Ranking rationale
Low-medium. No user-visible failure is known: T-035 works around it. It is a latent cross-file state leak, so the cheap fix goes early in the follow-on list, next to T-037, which touches the same list-parsing code.
