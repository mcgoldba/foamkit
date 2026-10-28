# T-041: A second entry on the same line is dropped or (since T-037) rejected (`x 1; y 2;`)

- **Issue:** [#55](https://github.com/mcgoldba/foamkit/issues/55)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-037 makes the list case (`x ( 1 ); y ( 2 );`, `x ( 1 ); y 2;`) stop being silent; this ticket covers everything else. T-040 covers one-line `{…}` (it absorbed T-022).
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
| `d { a 1; } e 2;` | `d { }`, so `a` and `e` are lost (this overlaps T-040: T-040 keeps `a`; this ticket keeps `e`) |

## Option (b): a load failure with a clear error, not silent loss (maintainer decision, 2026-10-27)
Since T-037 (PR #53), a second entry on the same line after **any** entry raises `FoamKitError` naming the file and line, instead of being silently dropped, until this ticket lands. These real files fail to load until then:
- Foundation 11-14 `fluid/helmholtzResonance/system/blockMeshDict:144-145`, and the other files in category A below;
- banner files with a one-line `FoamFile { … }` block (the T-021 shape): `pf.init` fails for the whole case.

Checked per file against `origin/main` at bc4af32 (2026-10-28): none of these files loaded on main. helmholtzResonance (F11-14) already raised "Parser made no progress at line 145"; `refineMesh/sector` (F12-14), `refineFieldDirs` (F11), `damBreak` `fvSchemes` (F11) and the one-line `FoamFile` banner raised `IndexError`; `rotatingCube` (F12-14) fails earlier on value-position `#calc` (T-027) on both. So T-037 turns crashes and an unhelpful error into a clear one; it does not break a file that loaded.

The T-037 tester adds characterization tests marked `xfail(strict=True, reason="T-041: second entry on a line")`; this ticket flips them.

## Real tutorial occurrences (Foundation 11-14 clones, planner rescan 2026-10-27)
**Method:** every `FoamFile` dictionary under `tutorials/`, skipping `#{ … #}` code blocks, `/* */` and `//` comments, strings, `polyMesh`, `triSurface`/`geometry` and scripts. A line counts when, after its first `;`, it continues with another word-starting token. The scan script is in the session scratchpad (`second_entry_scan2.py`). The T-037 reviewer's grep reported "95 lines in 31 files" across OF11-14 with a looser pattern; the categories below are the precise split.

**Category A, this ticket (a second entry after a top-level `;`):**

| Release | Files | Lines | Files |
|---|---|---|---|
| F11 | 3 | 9 | `compressibleVoF/damBreak/system/fvSchemes:31` (`div(rhoPhi,U) Gauss linearUpwind grad(U);Gauss upwind;`), `fluid/helmholtzResonance/system/blockMeshDict:144-145`, `mesh/refineMesh/refineFieldDirs/system/blockMeshDict:34…` |
| F12 | 3 | 13 | `fluid/helmholtzResonance/system/blockMeshDict:144-145`, `incompressibleVoF/rotatingCube/system/blockMeshDict:76-80`, `mesh/refineMesh/sector/system/blockMeshDict:32-38` |
| F13 | 3 | 13 | same three as F12 |
| F14 | 3 | 13 | same three as F12 |

In total, 12 file-instances (48 lines) across the four releases. The `damBreak` line's second entry has the keyword `Gauss` and value `upwind`. The tester confirms how OpenFOAM reads it and keeps it verbatim either way.

**Category B, owned by T-040 (several entries inside a one-line `{ … }`, or text after a one-line dict):** 12/9/7/4 files (193/98/96/36 lines) in F11/F12/F13/F14. Examples:
- `incompressibleFluid/impeller/system/createNonConformalCouplesDict:34` (20 lines);
- `multiRegion/CHT/heatedDuct/system/snappyHexMeshDict:65`;
- `incompressibleFluid/rotorDisk/system/snappyHexMeshDict:46` (F11-F13);
- `windAroundBuildings`, `shellAndTubeHeatExchanger` (`snappyHexMeshDict.orig`);
- the `multiphaseEuler/*/constant/phaseProperties` files (`f1 {dSph 1e-3; value 1.0;}`).

Some of these hang (T-040), and others now raise under option (b). Loading them fully needs T-040's one-line `{…}` parsing **plus** this ticket's multi-entry splitting. Coordinate: whichever lands second covers the combination.

## Scope
- The line/entry parser in `DictFileParser`: after one entry ends with `;` (outside strings, comments and brackets, using T-035's scanner), parse the rest of the line as further entries, at top level and in sub-dicts. This covers ordinary entries, sub-dicts and directives.
- Anything that cannot be parsed raises `FoamKitError` with file and line.
- Writing keeps entries in order. Keeping them on one line is T-020's concern; separate lines are acceptable here, but say so in the PR.

## Out of scope
- One-line `{…}` parsing itself (T-040)
- List cases (T-037)

## Acceptance criteria
- [ ] **Failing tests first:** every row of the reproduction table, plus these real files copied byte-exact into `tests/releases/` with their sources:
  - the three Foundation 14 `blockMeshDict` files (`helmholtzResonance`, `rotatingCube`, `refineMesh/sector`);
  - Foundation 11 `refineMesh/refineFieldDirs/system/blockMeshDict`;
  - Foundation 11 `damBreak/system/fvSchemes`.
- [ ] **Every category A file loads with every entry.** The T-037 characterization tests marked `xfail(strict=True, reason="T-041: second entry on a line")` pass with their markers removed. Option (b)'s `FoamKitError` is no longer raised for these inputs.
- [ ] After the fix, every entry is present with the right value (`d.yc`, `d.zs` …). Written files re-read to the same entries, and write 1 == write 2.
- [ ] `x 1; y` (an incomplete trailing entry) raises `FoamKitError` naming the file and line.
- [ ] No golden file changes. Any golden that turns out to encode a dropped entry is listed and regenerated deliberately.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **`;` inside `#{ #}` code or strings must not split entries.** Reuse T-035's scanner, and test it.

## Ranking rationale
**Second, right after T-037, and ahead of T-040** (re-ranked 2026-10-27 after option (b)).
- **It makes stock tutorials load.** Category A tutorials (3 files per Foundation release, including stock `helmholtzResonance`) fail to load today. On main they failed with `IndexError` or "Parser made no progress"; since T-037 the error names the line and this ticket. (Corrected 2026-10-28: an earlier version said these loaded on main; a per-file check showed none did.)
- **Small and contained:** size S, a single code path, with the tests already written by the T-037 tester. It can land quickly behind PR #53.
- **Why T-040 stays close behind:** T-040 covers confirmed **hangs** on real Foundation 11 files (`rotorDisk`, `heatedDuct`), which are an untrusted-input DoS, and more files (category B). But those hangs **pre-date** T-037 and are not a new regression, and T-040 is size M. If the maintainer prefers DoS-first, swap them; the two tickets do not depend on each other.
