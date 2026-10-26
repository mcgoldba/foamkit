# T-031: `/* … */` block comments: keep them on write, and parse them anywhere

- **Issue:** [#42](https://github.com/mcgoldba/foamkit/issues/42)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S. If the parser needs a tokenizer change, split it: T-031a for loss on write, T-031b for parse failures.
- **Related:** T-020 (keep the layout of unedited entries)
- **Depends on:** T-035 (#47), which makes the brace scan comment-aware. Build on its scanner, and re-check the "Could not find end of commented block" failure after T-035, since it may share the cause.
- **Depends on:** T-036 (#48), which makes line-comment stripping quote-aware. T-036 lands first.

## Goal
Block comments in the body of a dictionary are written back unchanged, and never make a file fail to load.

## Evidence (real files, 2026-10-21)
- **Lost or mangled on write:** ESI v2606 `bendJunction/system/blockMeshDict` (`tests/releases/esi-v2606.bendJunction.blockMeshDict`, 2 block comments).
  - Planner reproduction: `/* block\n comment */` is written as `/* blockcomment */`. The newline is dropped and the words are joined.
  - The file as a whole also fails today, on `#codeStream`/directives.
- **Parse failure:** ESI v2606 `basic/potentialFoam/cylinder/system/blockMeshDict` (`tests/releases/esi-v2606.potentialFoam-cylinder.blockMeshDict`, 20 block comments) fails with "Could not find end of commented block in file …".
- An inline `x /* c */ 1;` round-trips today. Keep it that way.
- **Update (2026-10-26, T-035):** T-035 fixed a separate bug in `_parseComments`: a single-line `/* x */` comment gained another `/*` on every write. With that fix, `bendJunction`'s second write is stable. **Still owned here:**
  - multi-line block comments are joined into one line, losing their newlines;
  - the potentialFoam/cylinder parse failure (re-check it on main after T-035 and T-036).

## Scope
- Block-comment handling in `DictFileParser` (`_parseComments` and the "end of commented block" search) and the comment writer. The single-line `/* x */` growth is already fixed by T-035; keep its regression test green. A comment's text, including its newlines, is kept byte-for-byte. Comments may start mid-line, span lines, or sit inside lists and sub-dicts.

## Out of scope
- Re-formatting entries around comments (T-020)
- `//` line comments, unless the tester finds a failure (record it)

## Acceptance criteria
- [ ] **Failing tests first:**
  - a multi-line block comment round-trip;
  - the potentialFoam-cylinder parse failure, isolated to its comment construct (record which construct);
  - **silent, high priority (T-035 review on PR #51; identical on main):** a block comment after a closing brace on the same line, `d { a 1; } /* c */` followed by `application simpleFoam;`, loads `d = {a, '}'}` with `application` swallowed into `d` (and `e { a 1; } /* c */` + `m 2;` moves `m` into `e`);
  - **silent data loss (same review):** a block comment before an entry on the same line, `/* a */ b 1;` followed by `c 2;`, drops `b` and `c`, because `_parseComments` reads to the next line ending in `*/`.
- [ ] After the fix:
  - multi-line block comments round-trip byte-identically at top level, inside a sub-dict and inside a list;
  - the potentialFoam-cylinder file gets past every comment. Other failures in it (`#codeStream` → T-033, `#remove` → T-016) are recorded, not fixed here.
- [ ] Inline block comments still round-trip.
- [ ] All existing golden files are unchanged. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **`/*` inside strings or `#{ #}` code blocks must not start a comment.** Add a test for each.

## Ranking rationale
Medium: comments are lost (data loss of user annotations) or a load fails, in ESI `blockMeshDict` files. It sits after the directive and reference load failures, which affect more files.
