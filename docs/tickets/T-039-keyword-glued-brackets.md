# T-039: Keyword glued to its bracket: `x{ … }`, `x(1);`, `fields(p U);`

- **Issue:** [#52](https://github.com/mcgoldba/foamkit/issues/52)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-022 (one-line sub-dicts). The real Foundation 11 files below are glued **and** one-line, so they load only after both tickets.
- **Found by:** the T-037 tester (2026-10-26). It is pre-existing on main.

## Goal
A keyword written directly against its `{` or `(`, with no space, is read the way OpenFOAM reads it and written back unchanged. Anything still unsupported raises `FoamKitError` with file and line, never `AttributeError` or `IndexError`.

## Reproduction (planner, 2026-10-26, on the T-037 branch)
| Input | Today |
|---|---|
| `x(1);` | **fails:** `AttributeError: 'ofWord' object has no attribute '_name'` (whole file) |
| `fields(p U);` | loads, but **mis-structured**: written as `fields(p    U);`, so the tokens are split wrongly |
| `x{ a 1; }` (one line) | written as `x{          a 1;` with the **closing `}` lost**, so the output is corrupt |
| `x{` + newline + `a 1;` + newline + `}` | **fails:** "Invalid syntax on line …" |
| `g { f10{dSph 10e-3; value 0.0;} }` (real F11 form) | **fails:** `IndexError: list index out of range` |
| `y uniform(0 0 0);` | round-trips unchanged |

## How common (real tutorial clones, 2026-10-26; `git grep -I` over `tutorials/`)
- **Glued dict `name{…}`: Foundation 11 has 6 files, 67 lines; Foundation 12-14 have 0.** All are `constant/phaseProperties` in `multiphaseEuler`:
  - `bubblePipe/constant/phaseProperties:65` `f10{dSph 10e-3; value 0.0;}`;
  - `pipeBend`, `titaniaSynthesis`, `titaniaSynthesisSurface`, `wallBoilingPolydisperse`, `wallBoilingPolydisperseTwoGroups`.

  Foundation 11 is a tested release, so 6 tested-release files fail to load.
- **Glued list `name(…);`: 0 dictionary entries in Foundation 11-14.** Every regex hit was C++ inside `#codeStream`/`#{ #}` blocks (`makeBlock(...)` in `resources/blockMesh/rotor2D`, `mkDir(dir);` in `moodyChart/system/frictionFactor:52`), which T-016/T-035 already keep verbatim.
- **ESI: not checked.** The scratchpad ESI clones no longer have `tutorials/` checked out.

## OpenFOAM semantics: verify before implementing
OpenFOAM word tokens may contain balanced parentheses (scheme keywords such as `div(phi,U)`). So `x(1);` may tokenize as the single **word `x(1)`**, not as keyword `x` plus list `(1)`, and `fields(p U);` may tokenize as the word `fields(p` (unbalanced). Step 1 for the tester is to read the word-token rule in `ISstream.C` (OpenFOAM-14 `src/OpenFOAM/db/IOstreams/Sstreams/`, and ESI's equivalent) and record what each input above means:
- if OpenFOAM reads `x(1)` as one word, the correct FoamKit behaviour is a verbatim round trip of that keyword, **not** a list parse;
- `{` always ends a word, so `x{…}` is a keyword followed by a dict in both distributions. Confirm this from the same source.

## Scope
- Tokenizing in `DictFileParser`:
  - `name{` splits into keyword + dict;
  - `name(` follows the OpenFOAM rule found in Step 1.
- Every glued form round-trips unchanged.
- Unsupported glued forms raise `FoamKitError` (file, line) instead of `AttributeError`/`IndexError`.

## Out of scope
- One-line sub-dict parsing in general (T-022)
- Layout (T-020)

## Acceptance criteria
- [ ] The Step 1 finding (OpenFOAM's reading of each input) is recorded in this ticket with source file and line.
- [ ] **Failing tests first:** each row of the reproduction table at top level, inside a sub-dict and (for `(`) as a list item.
- [ ] After the fix (with T-022 landed), the real Foundation 11 `multiphaseEuler/bubblePipe/constant/phaseProperties` loads. Copy it byte-exact into `tests/releases/` with its source recorded, then `g.f10.dSph` reads `10e-3` and the file round-trips with write 1 == write 2.
- [ ] `x{ a 1; }` keeps its closing `}`. No glued form loses or reorders tokens.
- [ ] No input in the table raises anything other than `FoamKitError`.
- [ ] No golden file changes. All other `tests/releases/` files behave as before.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Scheme keywords must stay single words:** splitting `name(` naively would break `div(phi,U)`, `laplacian(nuEff,U)` and other `fvSchemes` keywords. The existing `fvSchemes` goldens guard against that; add one explicit test.

## Ranking rationale
After T-022, which it depends on, in the follow-on list.
- **The glued dict blocks 6 tested-release files,** but only in Foundation 11, the oldest tested release.
- **The glued list form does not occur in tutorial dictionaries.**
- **The silent corruption cases matter even without tutorial evidence:** `x{ a 1; }` loses its `}`, and `fields(p U)` is mis-split. Hence it ranks above the formatting-only tickets.
