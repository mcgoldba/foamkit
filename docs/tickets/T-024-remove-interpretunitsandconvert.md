# T-024: Remove the never-working `_interpretUnitsAndConvert`

- **Issue:** [#33](https://github.com/mcgoldba/foamkit/issues/33)
- **Type:** code (owner: `implementer`; the tester only updates the T-017 source-check test, see below)
- **Size:** S
- **Depends on:** T-017. T-017's `tests/test_foamkit_error.py` lists this module in `test_library_module_does_not_call_sys_exit`.

## Goal
The package no longer ships a function that fails on every call. This removes dead code before T-013 adds real unit handling.

## Findings (2026-10-20)
- `foamkit/functions/_interpretUnitsAndConvert.py` can never run successfully:
  - the body starts with `pass`, then references `UnitRegistry`, which is never imported, so **every call raises `NameError`**;
  - `loopContents(v)` calls `iterateIterable(obj, v, k=None)`, but `iterateIterable(obj)` takes one argument, and `obj` is undefined in that scope;
  - `iterateIterable` calls `loopContents` with 2-3 arguments, but it takes 1;
  - the result `convertedDict` is never filled.

  The T-017 tester confirmed the `sys.exit()` branch (around line 60) is unreachable for these reasons.
- **Callers:** none. Its only reference is the re-export `from ._interpretUnitsAndConvert import _interpretUnitsAndConvert` in `foamkit/functions/__init__.py:25`, plus T-017's source-level test (`tests/test_foamkit_error.py`, parametrized over module paths). No module, CLI command or other test calls it.
- **Not to be confused with `_unitDecoder`.** `_unitDecoder` is a separate, working module used by `fkf.readInputs` (`readInputs.py:5, 30`) as a JSON `object_hook` with `pint`. It is **not** part of this ticket.

## Decision: delete, without a deprecation alias (approved by the maintainer, 2026-10-20)
- CLAUDE.md's deprecation rule protects public API that works. This name is underscore-prefixed, so private by convention, and it has never worked: any caller already gets `NameError`. A deprecation alias would only replace one error with another.
- **Approved by the maintainer in chat, 2026-10-20:** delete it, with no alias and no stub. The issue labels are handled by the maintainer.

## Relation to T-013
- **T-013 should not own this.** T-013 parses unit-annotated values from case files into `.value` + `.units` and does not convert units. This function tried to convert free-form strings to SI floats with `pint`, which is a separate, unrequested feature.
- If conversion is wanted later, it should be a new ticket built on T-013's `.units`, not a revival of this code.
- Removing it first means the T-013 implementer does not mistake it for existing unit support.

## Scope
- Delete `foamkit/functions/_interpretUnitsAndConvert.py` and its re-export line in `foamkit/functions/__init__.py`.
- In `tests/test_foamkit_error.py`, drop `functions/_interpretUnitsAndConvert.py` from the `test_library_module_does_not_call_sys_exit` parametrization, along with its explanatory comment.

## Out of scope
- `_unitDecoder` and `readInputs`
- Adding unit conversion

## Acceptance criteria
- [ ] Check first: `grep -rn "_interpretUnitsAndConvert\|interpretUnitsAndConvert"` over `foamkit/`, `tests/`, `README.md` and `docs/` finds only the module, the re-export and the T-017 test entry. If anything else turns up, stop and report back.
- [ ] After the change, that grep finds no hits outside `docs/tickets/` and `docs/plans/`.
- [ ] `import foamkit.functions` still works, and `fkf.readInputs` / `_unitDecoder` tests pass unchanged.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings, and the CI ratchet baseline is lowered in `ci.yml` if the removal drops findings.
- [ ] A `refactor:` commit whose body states that the function was removed and never worked.

## Risks
- **Overlap with T-017:** T-017's working tree also edits `_interpretUnitsAndConvert.py` (the unreachable `sys.exit()`). Start from merged main after T-017, and re-run the first acceptance grep before deleting.
- **External imports:** someone importing `foamkit.functions._interpretUnitsAndConvert` gets `ImportError` instead of `NameError` on call. Both are failures, and the old one only showed up later. This is acceptable for a private, never-working name.

## Ranking rationale
Low. It is dead code that no user can successfully reach, so it carries no user-facing risk. It goes right after T-013, so the cleanup is done before any later unit work, though it could be picked up any time after T-017 as a quick filler.
