# T-041: A second entry on the same line is silently dropped (`x 1; y 2;`)

- **Issue:** [#55](https://github.com/mcgoldba/foamkit/issues/55)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-037 makes the list case (`x ( 1 ); y ( 2 );`, `x ( 1 ); y 2;`) stop being silent; this ticket covers everything else. T-040/T-022 cover one-line `{…}`.
- **Found by:** the T-037 review (PR #53). It is pre-existing on main.

## Goal
Every entry on a line is parsed, in order, or the file is rejected with `FoamKitError`. A trailing entry is never silently dropped.

## Reproduction (planner, 2026-10-27, extracted `origin/main` bc4af32)
| Input | Written as |
|---|---|
| `x 1; y 2;` | `x 1;`, so **`y` is lost** |
| `a 1; sub { b 2; }` | `a 1;`, so **`sub` is lost** |
| `a 1; #include "f"` | `a 1;`, so **the include is lost** |
| `a 1; #print` | `a 1;`, so **the directive is lost** |
| `d { a 1; } e 2;` | `d { }`, so `a` and `e` are lost (this overlaps T-040/T-022) |

## Real tutorial occurrences (Foundation clones, `git grep -I`, 2026-10-27)
These are dictionary lines with two or more `;`-terminated entries. C++ inside code blocks was excluded.

| Release | Files | Lines |
|---|---|---|
| F11 | 2 | 8 |
| F12 | 3 | 13 |
| F13 | 3 | 13 |
| F14 | 3 | 13 |

Foundation 14 examples:
- `fluid/helmholtzResonance/system/blockMeshDict:144-145`: `x1 14; x2 6; x3 20; x4 6; x5 4;` and `yc 6; ys 12; zc $yc; zs $ys;`;
- `incompressibleVoF/rotatingCube/system/blockMeshDict:76-80`: `nIn 7; fIn 0.4;`;
- `mesh/refineMesh/sector/system/blockMeshDict:32-38`: `Ax 0.438912; Ay 0.000000;`.

These are `blockMeshDict` variables that later lines reference (`$yc`). Dropping them changes the mesh, or breaks references when OpenFOAM reads the written file. ESI was not checked (its clone has no checked-out tutorials).

## Scope
- The line/entry parser in `DictFileParser`: after one entry ends with `;` (outside strings, comments and brackets, using T-035's scanner), parse the rest of the line as further entries, at top level and in sub-dicts. This covers ordinary entries, sub-dicts and directives.
- Anything that cannot be parsed raises `FoamKitError` with file and line.
- Writing keeps entries in order. Keeping them on one line is T-020's concern; separate lines are acceptable here, but say so in the PR.

## Out of scope
- One-line `{…}` parsing itself (T-040/T-022)
- List cases (T-037)

## Acceptance criteria
- [ ] **Failing tests first:** every row of the reproduction table, plus the three real Foundation 14 `blockMeshDict` files copied byte-exact into `tests/releases/` with their sources.
- [ ] After the fix, every entry is present with the right value (`d.yc`, `d.zs` …). Written files re-read to the same entries, and write 1 == write 2.
- [ ] `x 1; y` (an incomplete trailing entry) raises `FoamKitError` naming the file and line.
- [ ] No golden file changes. Any golden that turns out to encode a dropped entry is listed and regenerated deliberately.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **`;` inside `#{ #}` code or strings must not split entries.** Reuse T-035's scanner, and test it.

## Ranking rationale
**Third, right after T-040.** It silently loses data in real `blockMeshDict` files of every tested Foundation release. That outranks the loud load failures (T-027 …), which users at least notice.
