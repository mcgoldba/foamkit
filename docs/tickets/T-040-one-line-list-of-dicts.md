# T-040: One-line list of dicts `x ( a { v 1; } b { v 2; } );` hangs or silently empties the list

- **Issue:** [#54](https://github.com/mcgoldba/foamkit/issues/54)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S. Becomes M if T-022 is folded in (see "Relation to T-022 and T-039").
- **Found by:** the T-037 reviewer (review on PR #53). It is pre-existing on main.

## Goal
A one-line list whose items are dicts is parsed correctly (every item and entry kept) or rejected with `FoamKitError`. It never hangs, and it never silently drops data. Case files are untrusted input, so a hang is a denial of service.

## Reproduction
- **Reviewer (PR #53):** `x ( a { v 1; } b { v 2; } );` never finished; it was killed after 30 s. The same happened on main.
- **Planner, 2026-10-27, on an extracted copy of `origin/main` (bc4af32, includes T-035):**

  | Input | Result |
  |---|---|
  | `x ( a { v 1; } b { v 2; } );` | no hang here; finished in about 10 s, which is mostly the slow interpreter start on this machine. **Every item silently lost:** written as `x ( );` |
  | `x ( { v 1; } );` | written as `x ( );`, items lost. One of four runs hit a 15 s timeout, which was **not** reproduced at 40 s |
  | `x ( a { v 1; } );` | written as `x ( );`, items lost |
  | multi-line `x (` / `a { v 1; }` / `);` | written as `x ( a { } … )`: `v 1` lost, plus spurious empty items (also B19/T-037) |

So in this environment the input loses data silently rather than hanging. The reviewer's hang may depend on the T-037 branch state or the environment. **Step 1 for the tester:** reproduce on current main and on the PR #53 branch with a hard timeout, and record which inputs hang and which empty the list. Both outcomes are in scope.

## Scope
- Find the loop and list-item handling in `_parseList` / `_parseListValues` and the one-line `{…}` handling (`foamkit/types/__init__.py`).
- Make one-line list items that are dicts (named `a { … }` and anonymous `{ … }`) parse into the list, in order, with all entries.
- Anything unsupported raises `FoamKitError` with file and line.
- Bound every loop by input length. Each pass must make progress or raise.

## Out of scope
- Glued `a{…}` (T-039)
- Layout (T-020)

## Acceptance criteria
- [ ] **Timeout-guarded tests first** (run each parse in a subprocess, or with `pytest-timeout` if the maintainer adds it, at ≤ 10 s each). Cover every input in the table above, plus nesting (`x ( a { b { v 1; } } );`) and a 10^4-item one-line list of dicts.
- [ ] After the fix, every input finishes within the bound, every item and entry is kept (`x[0].v == 1`, …), and write 1 == write 2 == write 3. Inputs that are still unsupported raise `FoamKitError`; a silent empty list is never acceptable.
- [ ] No golden file changes. All `tests/releases/` files behave as before.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Relation to T-022 and T-039
- **T-022** (one-line sub-dicts, `p { type probes; }`) very likely shares the cause: one-line `{…}` handling. On `origin/main`, `d { a 1; } e 2;` is written as `d { }`, so `a` and `e` are silently dropped. That is no longer the `IndexError` T-022 recorded before T-035.
- **Proposal: fold T-022 into this ticket (size M).** The fix is one piece of code, and this ticket's priority (untrusted-input DoS or silent loss) is higher. This needs maintainer approval, because T-022 (#29) is already approved. If not folded, T-040 lands first and T-022 reuses its one-line `{…}` parsing.
- **T-039** (glued `name{`) builds on whichever lands. It stays separate.

## Ranking rationale
**Second, right after T-037.** It is either an untrusted-input hang (reported) or a silent loss of every list item (reproduced). Both are worse than loud load failures.
