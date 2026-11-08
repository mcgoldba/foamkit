# T-075: tokens with `_` (`1_0`) are words, written back as read

- **Issue:** [#102](https://github.com/mcgoldba/foamkit/issues/102)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (one number test shared by every typed-value path, plus tests for each shape)
- **Related:** T-071 (#92, PR #101, list groups keep their number text), T-032 (number spelling), T-014 (dimensioned values that lose their value), T-045 (one-element lists).
- **Depends on:** none. Ranked ahead of T-020 (maintainer, 2026-11-08); T-020's branch rebases onto it, because both change `foamkit/types/__init__.py`.
- **Maintainer decision (2026-11-08, issue #102):** `1_0` is not a valid OpenFOAM number, so FoamKit must not load it as one. **Any token containing `_` is a word everywhere, and is written back exactly as read.** This replaces the earlier reading (load as 10, write without `_`).

## Goal
A token such as `1_0`, `1_000.5` or `-2_5e1_0` is never read as a number: it loads as a word wherever it appears, and an unedited write gives back the same text, so FoamKit no longer turns an OpenFOAM word into a different number.

## Today (planner, reproduced on f8590d8, 2026-11-08)
Every path accepts `_` because it uses Python `int()`/`float()` (`_parseValue`, ~6101-6240; the dimension-set `int()` calls, ~6937-6945; the counted-list length, ~5243). The `_` is then silently dropped on write, except in list groups since T-071.

| Input (top level and in a sub-dict) | Loads as | Written as |
|---|---|---|
| `x 1_0;`, `x +1_0;` | `ofInt` 10 | `10` |
| `x 1_000.5;`, `x 1.5_0;` | `ofFloat` 1000.5, 1.5 | `1000.5`, `1.5` |
| `x -2_5e1_0;`, `x 1_0e5;` | `ofFloat` | `-250000000000.0`, `1000000.0` |
| `l (1_0 2 3_0.5);`, `v (1_0 0 0);`, multi-line `x` / `(` / `1_0` / `2` / `);` | `ofSplitList` 10, 2, 30.5 | `10`, `2`, `30.5` |
| `v uniform 1_0;`, `v uniform (1_0 0 0);` | `ofUniformField` (`ofInt` 10, `ofVector`) | `uniform 10;`, `uniform (10.0 0.0 0.0);` |
| `nu [0 2 -1 0 0 0 0] 1_0;` | `ofDimensionedScalar` 10.0 | `10.0` |
| `nu [0 2 -1_0 0 0 0 0] 1;` | `ofDimensionedScalar`, dimension -10 | `[0 2 -10 0 0 0 0] 1.0` |
| `box (1_0 0 0) (1 1 1);` | `ofBoundBox`, `.value[0][0] == 10.0` | `(1_0 0 0) (1 1 1)` (T-071 keeps the text) |
| `c (1_0 2) (3 4);` | `ofListGroups`, `ofInt` 10 | `(1_0 2) (3 4)` |
| `t` / `1_0` / `(` / `a` / `b` / `);` (count on its own line) | `ofSplitList` of `a`, `b`; `1_0` taken as the count | `t` / `(` / `a` / `b` / `);` (the `1_0` is gone) |

Already words today, and unchanged by this ticket: `x 1__0;`, `x _10;`, `x 10_;`, `x 1_e5;`, `x 0x10;` (`ofStr`, written as read), `x 1_0 2;` and `t 1_0(a b);` (`ofStr`), `nu nu [0 2 -1 0 0 0 0] 1_0;` (`ofStr`), `internalField nonuniform List<scalar> 3(1_0 2 3);` (`ofStr`). `1e5` and `1E5` both load as `ofFloat` 100000.0 and stay numbers. `nan`, `inf` and `-Infinity` stay `ofFloat`.

How a plain word loads in the same positions today (the shape `1_0` gets after this ticket, unless the ticket says otherwise): `x abc;` is `ofStr`; `l (abc 2);` is an `ofSplitList` with an `ofStr` item; `box (a 0 0) (1 1 1);` is a plain `ofListGroups`, written as read. **But** `v uniform abc;` raises a bare `ValueError`, and `nu [0 2 -1 0 0 0 0] abc;` loads as `ofNamedDimension` and is **written without `abc`** (the T-014 family). `_` tokens must not be routed into either.

No file in `tests/golden`, `tests/releases` or `tests/fixtures` has a `_` between digits (`git grep -nE '[0-9]_[0-9]' -- tests` matches only Python literals in test code). Real tutorials: 0 tokens in Foundation 11 and 14 dictionaries; ESI v2606 has 1 match, in a `README.md` (`5(2_3_4)` in a citation).

## Scope
- `foamkit/types/__init__.py`: one number test (for example a helper that refuses any token containing `_` before calling `int()`/`float()`), used by every place that turns a file token into `ofInt`/`ofFloat`: `_parseValue` (all of its `int()`/`float()` attempts, including the `( … )` tensor branch), list items (`_parseListValues`), list groups (`_parseListGroups`, so `_numberReprs` sees a word), `uniform` values (`_parseUniformField`), dimensioned values and dimension sets (`_parseDimensionedType`, ~6937-6966), and the counted-list length (~5243). The tester lists every call site found with `grep -nE '\b(int|float)\(' foamkit/types/__init__.py` in the test module docstring, with the ones that read file tokens marked.
- Results:
  - scalars, list items and list-group items holding `_` load as the type a word gets there today (`ofStr`), and are written as read;
  - `box (1_0 0 0) (1 1 1);` is a plain `ofListGroups` (T-071's rule: 2 groups of 3 numbers), written as read;
  - `uniform` and dimensioned values, dimension sets and counted-list lengths holding `_`: either the whole value loads as an `ofStr` written as read, or loading raises `FoamKitError` naming the file and line (no traceback). Never a bare exception, and the token is never dropped.
- Tests: a new `tests/test_underscore_tokens.py`.

## Out of scope
- `ofInt(value='1_0')` / `ofFloat(value='1_0.5')` from Python code still give 10 / 10.5 (user input, not file text); recorded for a later decision.
- Other Python-only spellings: `0x10` is already a word; `1e5`/`1E5` are valid OpenFOAM and stay numbers. Number spelling of other paths (`1000000.0`, T-032).
- The pre-existing loss of a word value in a dimensioned entry (`nu [0 2 -1 0 0 0 0] abc;`, `[0 2 a 0 0 0 0]`) and the bare `ValueError` for `uniform abc;`, beyond making sure `_` tokens do not reach them.
- One-element lists such as `x (1_0);` (bare `TypeError` today, also for `x (10);`: T-045).

## Acceptance criteria
- [ ] **Failing tests first**: every input row of the "Today" table, at top level and inside a sub-dict.
- [ ] For each row, the loaded `_` token is the word type (`ofStr`, or the containing value is an `ofStr`), never `ofInt`/`ofFloat`; or, for the `uniform`/dimensioned/dimension-set/count rows only, `FoamKitError` naming the file and line. The tests record which.
- [ ] Every row that loads is written with the source token unchanged (`1_0` stays `1_0`, `-2_5e1_0` stays `-2_5e1_0`), and write 1 == write 2.
- [ ] `box (1_0 0 0) (1 1 1);` loads as `ofListGroups`, not `ofBoundBox`, on both reads.
- [ ] The "already words" rows, `1e5`/`1E5`, `nan`/`inf`, and plain numbers (`x 10;`, `box (0 0 0) (1 1 1);`) are unchanged (pinned).
- [ ] No golden file changes. No other `FoamKitError` test changes.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): read tokens with _ as words and write them as read (T-075)`, whose commit body says that `1_0` no longer loads as the number 10.

## Risks
- **Behaviour change:** code that relied on `1_0` loading as 10 now gets a word (or, for `uniform`/dimensioned values, an error). No deprecation path: the old behaviour silently changed the file, and `1_0` is not a valid OpenFOAM number. The commit body (and so the CHANGELOG) says so.
- **Shared code:** the number test sits on the main parse path; the tests pin the plain-number rows so nothing else changes type.
- **OpenFOAM versions:** none expected. The claim that OpenFOAM reads `1_0` as a word is the maintainer's (2026-11-08); it was not checked against an OpenFOAM build.
