# T-036: `//` inside a quoted string is not a comment (entry and line parser)

- **Issue:** [#48](https://github.com/mcgoldba/foamkit/issues/48)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-035. It reuses T-035's quote-aware scanner where possible.
- **Found by:** the T-035 tester (2026-10-26). It is pre-existing on main and separate from T-035, which made only the dict/list **end scan** string-aware.

## Goal
An entry or list item whose quoted string contains `//` (for example a URL) loads, and is written back unchanged.

## Bug (planner reproduction, 2026-10-26)
| Input | Today |
|---|---|
| `note "http://x";` at top level | **fails:** `Cannot handle single line entry '['note', '"http:']'` |
| `url "http://example.com";` inside a sub-dict | **fails**, same error |
| list item `"a//b"` in `l ( "a//b" );` | **silently truncated**: written as `"a` (data loss, no error) |
| `note "a /* b";` and `note "a /* b */ c";` | OK: round-trips today. `/*` inside a string is not mis-stripped by the entry parser |

**Cause:** the entry and line parser strip `//` comments without tracking quoted strings.

## How common (real tutorials, 2026-10-26)
- Foundation 11-14: **0** files with `//` inside a single quoted token. Apparent hits were a string followed by a `//` comment, for example `separator " "; // Optional`. This was checked with `git grep -I` in the inventory clones.
- ESI v2412-v2606: **not re-checked.** The scratchpad clones no longer have `tutorials/` checked out; re-run the grep after `git sparse-checkout set tutorials` (method in the plan's Directive inventory).
- The likely real-world source is user-written text: URLs or paths in `note`/description entries, `#message` strings, or file paths in function objects.

## Scope
- Line-comment stripping in the entry and line parser (`DictFileParser`, wherever `//` is located on a line) skips quoted strings, honouring `\"` escapes. Reuse T-035's scanner where possible.
- Confirm that `/*` inside strings stays correct, including multi-line cases, and add tests. Do not change block-comment preservation; that is T-031.

## Out of scope
- Keeping or re-formatting comment text (T-031)
- The dict/list end scan (T-035)

## Acceptance criteria
- [ ] **Failing tests first:** `//` inside a string as a top-level entry, an entry in a sub-dict, and a list item (the truncation case). Also `"a\" // b"` (escaped quote, then `//` still inside the string), and `x "a"; // real comment` (a real comment after a string still works).
- [ ] Tests for `/*` and `*/` inside strings in the same three positions, passing before and after.
- [ ] After the fix, all of these load, round-trip unchanged, and write 1 == write 2.
- [ ] No golden file changes. All `tests/releases/` files behave as before.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.
- [ ] Cosmetic line numbers in the shared scanner (T-035 review on PR #51): an unterminated string in an extra-line directive (`_scanDirective` with `canContinue=False`) reports "line 1" instead of the file line; a stray `#}` without `#{` is reported at the enclosing dict's closing line instead of the `#}` line. Both already raise; fix the reported line.

## Risks
- **Unterminated quote on a line:** decide whether it is an error or literal text. Follow T-035's rule (`FoamKitError` with file and line) for consistency.
- **Shared scanner:** keep T-035's tests green.

## Relation to T-031 (block comments)
Both touch comment-stripping code. **T-036 lands first.**
- It is smaller.
- It fixes silent truncation.
- It makes the line-comment stripper quote-aware, which T-031 then builds on for `/* */` preservation.

T-031 already depends on T-035; add T-036 to its dependencies.

## Ranking rationale
Right after the top-7 list, ahead of T-031.
- **Silent data loss:** a list item is truncated with no error, which is serious.
- **Rare in tutorials:** the form occurs in **zero** Foundation 11-14 tutorial files (ESI not re-checked), so it does not outrank the real-file load failures T-027, T-026, T-030 and T-029.
