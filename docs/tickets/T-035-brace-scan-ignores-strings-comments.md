# T-035: The dict/list end scan ignores braces inside strings, comments and `#{ … #}` code

- **Issue:** [#47](https://github.com/mcgoldba/foamkit/issues/47)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M. The same scan is used for dicts and lists at several call sites, and T-016's guard must be removed and its tests converted.
- **Depends on:** T-016 (PR #46). Reuse its quote- and comment-aware capture scanner, and remove its interim guard.
- **Approved by the maintainer in chat (2026-10-25)** to be ranked first after T-016.
- **Found by:** the T-016 reviewer (review comment on PR #46). It is pre-existing on main.

## Goal
A `{` or `}` inside a quoted string, a `//` or `/* */` comment, or a `#{ … #}` code block never changes which dictionary or list an entry belongs to.

## Bug (silent change of meaning)
Take `d { e { <line> inner 2; } mid 3; }`, where `<line>` is one of:
- `note "a } b";`
- `// comment }`
- `x ( "}" );`

The file loads with `inner` moved up into `d` and `mid` moved to the top level, and **the structure keeps shifting on each write**. With a `{` in the same positions, loading fails with "Could not locate end of dict".

**Cause:** `_findDictOrListEndLine` (`foamkit/types/__init__.py:4852`, called at `:4502`, `:4803`, `:5052`) and the related end-of-block code count every brace character. They do not skip:
- quoted strings;
- `//` line comments;
- `/* */` block comments;
- `#{ … #}` verbatim code.

None of the 18 real files in `tests/releases/` triggers it. Hand-written comments such as `// close }` are a plausible way to hit it in user cases.

## Interim guard in T-016
T-016 makes **directive** lines inside a sub-dict whose braces in quotes, comments or code blocks do not balance raise `FoamKitError` instead of reaching this bug. Balanced braces (e.g. `#message "… ${FOAM_API:-unset}"`) load. The guard scans with the same rules as the directive capture. This ticket removes that guard once the scan is fixed, and turns the guard's tests into round-trip tests.

## Scope
- Remove the now-unused `comments` parameter of `DictFileParser._scanDirective` (and its unreachable `inBlock` branch and docstring line) when the scanner is made comment-aware for both the capture and the dict-end scan (T-016 round-3 review).
- Make the end scan (`_findDictOrListEndLine` and the related end-of-dict/list code) skip:
  - double-quoted strings, including escaped quotes;
  - `//` to end of line;
  - `/* … */`, which may span lines;
  - `#{ … #}`, which may span lines.

  Reuse T-016's capture scanner, so there is one tokenizer for "where does this bracket close".
- Apply it to ordinary entries and directives, in dicts and lists, at every call site.
- Remove T-016's guard, and convert its tests.

## Out of scope
- Preserving or re-formatting comment text (T-031)
- Other layout (T-020)

## Acceptance criteria
- [ ] **Failing tests first:** each reviewer shape (`note "a } b";`, `// comment }`, `x ( "}" );`) and the `{` variants, for both ordinary entries and directive lines, at nesting depths 1, 2 and 3, in a dict and in a list. Also `/* } */` and `#{ } #}` placed inside a sub-dict, and the directive shapes `#fooBar /* ( */` followed by lines `}` and `)`, and `#fooBar /* " */ x` followed by lines `}` and `"` (from the T-016 round-2 review). Also `#fooBar /* { */` followed later in the same dict by a compensating `// }` or `note "}";` (T-016 round-3 review): today `inner` disappears into the directive text and `mid` moves into the inner dict.
- [ ] After the fix, every entry stays in its own scope: `d.e.inner` exists and `d.mid` exists, with no top-level `mid`. Write 1 == write 2 == write 3.
- [ ] T-016's guard is removed, and its tests now assert a round trip instead of `FoamKitError`.
- [ ] A really unbalanced brace in code (outside strings, comments and code blocks) raises `FoamKitError` naming the file and the line of the unclosed opener.
- [ ] Unterminated `"…`, `/* …` or `#{ …` raise `FoamKitError` naming the file and line, rather than scanning to the end of the file silently.
- [ ] **Bounded and linear:** one pass, with no backtracking regex. A test with a large input (for example 10^5 lines of nested braces in strings) completes within a generous time bound and does not hit the recursion limit.
- [ ] No golden file changes. All 18 `tests/releases/` files behave exactly as before this ticket.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. Lower the baseline in `ci.yml` if findings go down.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Edge cases:**
  - escaped quotes `\"` inside strings;
  - `//` inside a string (not a comment);
  - `/*` inside a string;
  - an apostrophe in a comment.

  Test each one.
- **Shared scanner:** the scanner is shared with T-016's directive capture. Keep T-016's tests green.

## Relation to T-031 (block comments)
They overlap: a `}` inside `/* */` is both this bug and a comment-handling case. **T-035 lands first.**
- **Silent change of meaning:** this bug changes the meaning of a file without any error. T-031 is about losing comment text or failing loudly.
- **Shared scanner:** T-035 builds the comment-aware scanner that T-031 then uses to preserve comment text. T-031's parse failure ("Could not find end of commented block") should be re-checked after T-035, since it may share the cause.

Update T-031's dependency to T-035 when this lands.

## Ranking rationale
**First after T-016** (maintainer, 2026-10-25). A file that loads with entries silently moved to another scope, and keeps shifting on every write, is the worst kind of failure for an editing tool: users get no error. It also lets T-016's interim guard be removed.
