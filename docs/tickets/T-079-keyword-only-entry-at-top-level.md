# T-079: a keyword-only entry (`print;`, `box ;`) at the top level loads instead of crashing with a bare `AttributeError`

- **Issue:** [#106](https://github.com/mcgoldba/foamkit/issues/106)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (one top-level branch, matching the sub-dict handling that already works)
- **Related:** T-087 (#115; depends on this ticket: it writes `count;` for `.value = None`, which must load back at the top level), T-076 (#103; after `groups.clear()` the writer emitted `box ;`, which then failed on re-read; T-076 makes that write raise), T-020 (layout of unedited entries), T-041 (several entries per line).
- **Depends on:** none. Start after T-020 merges, because both change `foamkit/types/__init__.py`.
- **Maintainer decision to confirm at approval:** how the entry is represented. (A, recommended) The same as in a sub-dict today: an `ofWord` holding the keyword, stored under an `unnamed_<n>` key, written `keyword;`. No API change. (B) A named entry with an empty value (`d.print` exists). This changes the sub-dict representation too, so it needs a deprecation path for `unnamed_<n>` and is no longer S.

## Goal
A file whose top level holds a keyword with no value, such as Foundation 14's `print;` in `createZonesDict`, loads and is written back with the keyword, the same as such entries inside a sub-dict; anything still unsupported raises `FoamKitError` naming the file and line.

## OpenFOAM semantics
A keyword followed directly by `;` is a valid entry with an empty token stream. Real tutorials rely on it: `particleForces { sphereDrag; gravity; }` (`cloudProperties`), `liquid { H2O; }` (`physicalProperties`), `fluxRequired { pcorr ; p ; }` (ESI `fvSchemes`), and Foundation 14 `createZonesDict` `print;` at the top level and `fan;` in a sub-dict. (Not checked against an OpenFOAM build; the claim rests on these shipped tutorials.)

## Today (planner, reproduced on f8590d8, 2026-11-08)
| Input | Top level | In a sub-dict |
|---|---|---|
| `box ;`, `box;`, `x ;`, `x  ;`, `x; // c` | **bare `AttributeError: 'ofWord' object has no attribute '_name'`** (`readDictFile`, ~4905) | `unnamed_1` = `ofWord('x')`, written `x;`, write 1 == write 2 |
| `a 1;` / `x ;` / `b 2;`, `a 1;` / `x;` (at EOF), `print;` / `b 2;`, blank lines around | **bare `AttributeError`** | loads with `a`, `unnamed_1`, `b` in order; written back; write 1 == write 2 |
| `s { x; y; }` (multi-line) | loads (the entries are in a sub-dict) | loads |
| `box ( );`, `x "";` | `ofSplitList` `[]` / `ofStr '""'`, written back | same |

Real tutorials (`git grep` over `tutorials/`, `polyMesh` excluded; ESI v2606 read with `grep -r` on the extracted tree):

| Release | Files (lines) with a keyword-only entry | Of which at the top level |
|---|---|---|
| Foundation 11 | 52 (70) | 0 |
| Foundation 14 | 56 (80) | 2: `incompressibleVoF/trayedPipe/system/createZonesDict:115`, `multicomponentFluid/filter/system/createZonesDict:52` (`print;`) |
| ESI v2606 | 123 (222) | 0 (the only unindented hit is in an `Allrun` script) |

The nested ones load today. Stock `filter/system/createZonesDict` fails on this bug; `trayedPipe` fails first on `#codeDict` (T-028).

## Scope
- `foamkit/types/__init__.py`: the top-level read path (`readDictFile`, ~4905, and `_parseSingleLineEntry`, ~5172) handles a keyword-only entry the way the sub-dict path does (option A), or as chosen at approval.
- Tests: a new `tests/test_keyword_only_entry.py`, using a byte-exact copy of the Foundation 14 `filter/system/createZonesDict` in `tests/releases/` (source commit and blob in the docstring, as in `tests/test_bound_box.py`), if it loads once this is fixed; otherwise the inline rows only, with the next blocker named.

## Out of scope
- The layout of `x ;` and `pcorr           ;` (written `x;`, `pcorr;`): whitespace only, T-020.
- The write side of an `ofListGroups` with no groups (T-076).
- Named access to keyword-only entries (option B), unless chosen at approval.

## Acceptance criteria
- [ ] **Failing tests first**: every input row above, at top level and inside a sub-dict, alone, between entries and as the last entry in the file.
- [ ] Each top-level row loads with the same type and key scheme as the sub-dict row (option A), keeps the entry order, and is written with the keyword followed by `;`. Write 1 == write 2.
- [ ] The sub-dict rows keep their current behaviour (pinned).
- [ ] No input raises a bare exception. Any shape still refused raises `FoamKitError` naming the file and line.
- [ ] The Foundation 14 `filter` `createZonesDict` loads, or its test names the next blocker.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): load keyword-only entries at the top level (T-079)`.

## Risks
- **Behaviour change:** files that crashed now load. With option A, no existing loaded value changes.
- **Duplicates:** two top-level `print;` entries must give two entries (`unnamed_1`, `unnamed_2`), not one.
- **OpenFOAM versions:** none known; Foundation 11/14 and ESI v2606 all use keyword-only entries.
