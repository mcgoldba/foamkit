# T-084: a file holding a bare list (`cloudPositions`, `*.eMesh`) is written back without an invented `unnamed_1` keyword

- **Issue:** [#112](https://github.com/mcgoldba/foamkit/issues/112)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (one writer rule, plus keeping the source's `;` or no `;`)
- **Related:** T-020 (#27, T-020a, gap kind **U** and design note 3), T-048 (#64; pinned that these files load and write 1 == write 2, with the keyword), T-079 (#106; keyword-only entries use the same `unnamed_<n>` keys, written by value, unaffected), T-080 (#107, counted lists).
- **Depends on:** T-020 (#27). Both change `ofDictFile.toString`, and the regenerate path this ticket fixes is the one T-020a keeps.

## Goal
A file whose content is one or more bare lists, such as `constant/cloudPositions`, `parcelInjectionProperties` or a `featureEdgeMesh` `*.eMesh`, is written back with its lists as read, with no `unnamed_1` keyword added, so OpenFOAM can still read it after a FoamKit write; anything still not handled raises `FoamKitError` naming the file and line.

## OpenFOAM semantics
These files are not dictionaries: after the `FoamFile` header the reader expects the list itself (`vectorField`, `scalarListList`, `featureEdgeMesh` points then edges). The added word `unnamed_1` before `(` is therefore not what the reader expects. (Not checked against an OpenFOAM build; the claim rests on the file classes and the shipped tutorials, which never put a keyword there.)

## Today (planner, reproduced on 839663c = `origin/main`, 2026-11-08)
`DictFileParser(...).readDictFile()` → `toString()` → write → re-read → `toString()`:

| Input (after the header) | Loads as | Write 1 | Write 1 == write 2 |
|---|---|---|---|
| Real `foundation-13.parcelInBox.cloudPositions`: `(` / `(0.05 0.05 0.005)` / `)` | `unnamed_1` | **`unnamed_1` / `(` … `);`**: keyword and `;` added | yes (added once, then stable) |
| Real Foundation 11 `filter/constant/parcelInjectionProperties` (`(` … `);`) | `unnamed_1` | **`unnamed_1` added**; `;` kept | yes |
| Real Foundation 11 `iglooWithFridges/constant/geometry/fridgeA.eMesh` (two bare lists ending in `)`, with `// Points`, `// Edges`) | `unnamed_1`, `unnamed_2` | **both keywords and both `;` added** | yes |
| `a 1;` / `( x y )` multi-line / `b 2;` | `a`, `unnamed_1`, `b` | **`unnamed_1` added** | yes |
| Bare list inside a sub-dict | `s.unnamed_1` | **`unnamed_1` added** (plus two extra blank lines) | yes |
| Bare `{ a 1; }` at the top level | `unnamed_1` (dict) | **`unnamed_1` added** | yes |
| `2` / `(` … `)` (counted bare list) | key `t_2` (the count read as a keyword) | `2` / `(` … `);` (`;` added) | yes |
| `((1 2 3) (4 5 6))` one line | `FoamKitError` "Could not find end of statement", line 8 | - | - |

- **Cache:** an `fk init`-style `init` → `save` → `load` keeps `unnamed_1` and writes the same text; `case.write()` puts `unnamed_1` on disk.
- **Likely cause (for the implementer to confirm):** `ofDict.toString` blanks unnamed keys with `re.match(UNNAMED_TAG+'_[0-9]+$', k)`, i.e. `unnamed__1` with two underscores, which never matches; and the list and dict writers print their own `_name`. Scalars go through `printNameStr`, which does match `unnamed_<n>`.

Real tutorials (bare list right after the header; comments ignored; `polyMesh` excluded; Foundation via `git ls-files`/`git grep` on the clones, ESI v2606 with `grep -r` on the extracted tree):

| Release | Files | Kinds |
|---|---|---|
| Foundation 11 | 13 | 8 cloud positions (`cloudPositions`, `coalCloudPositions`, `limestoneCloudPositions`), 4 `parcelInjectionProperties`, 1 `fridgeA.eMesh` |
| Foundation 14 | 13 | the same 13 files |
| ESI v2606 | 20 | 13 cloud positions (`kinematicCloudPositions`, `reactingCloud1Positions`, …), 6 `parcelInjectionProperties`, 1 `resources/geometry/fridgeA.eMesh` |

Counted bare lists (`N` / `(`, the form OpenFOAM itself writes for run output): 0 Foundation files, 1 ESI file (`multiphase/compressibleInterDyMFoam/laminar/sphereDrop/include/meshModifiers`).

## Scope
- `foamkit/types/__init__.py`: the writers (`ofDict.toString`, `ofDictFile.toString`, and the list/dict `toString` called for an entry) never print an `unnamed_<n>` key as a keyword. A bare list keeps whether its source ended in `)` or `);`. This holds on the regenerate path that T-020a keeps (an edited entry, `toString(_preserve=False)`, later T-050's `format_on_write`).
- Read side unchanged: the entries stay reachable as `d.unnamed_1`, `d.unnamed_2` (no API change).
- Tests: a new `tests/test_bare_list_files.py`, reusing `tests/releases/foundation-13.parcelInBox.cloudPositions` and adding byte-exact copies of the Foundation 11 (or 14) `fridgeA.eMesh` and `filter/constant/parcelInjectionProperties`, with source commit and blob in the docstring as in `tests/test_glued_parens_in_list.py`.

## Out of scope
- Counted bare lists (`2` / `(` … `)`, key `t_2`, `;` added): 1 ESI tutorial file; counted lists belong to T-080. Pin today's output in a test with a comment naming T-080.
- One-line bare lists (`((1 2 3) (4 5 6))`): already a loud `FoamKitError`.
- Layout of unedited entries (T-020a) and the extra blank lines in the sub-dict row (layout, T-083).

## Acceptance criteria
- [ ] **Failing tests first:** every loading row of the table, unedited and after an edit to the list (append an item; `toString(_preserve=False)` once T-020a has landed), at the top level, between entries, inside a sub-dict, and two bare lists in one file.
- [ ] No written text contains `unnamed_` for any of these rows; the bare lists are written in their source order and position, with `;` exactly when the source had one. Write 1 == write 2.
- [ ] The three real fixtures write back with only the lists' own layout changing on the regenerate path, and byte-identical when unedited (T-020a).
- [ ] An edited item is written (`d.unnamed_1` append shows up on disk through `case.write()`), and `init` → `save` → `load` → `case.write()` writes no keyword.
- [ ] T-079's keyword-only entries (`print;` under `unnamed_<n>`) keep being written `print;` (pinned).
- [ ] No input raises a bare exception; any bare shape still refused raises `FoamKitError` naming the file and line.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): write bare lists without an unnamed_1 keyword (T-084)`.

## Risks
- **Behaviour change:** files written by FoamKit since the keyword appeared already contain `unnamed_1 (…);`. Re-reading such a file loads a list *named* `unnamed_1`, which this ticket would then write bare: it repairs those files. Say so in the commit body.
- **Interaction with T-020a:** T-020a writes an unedited bare list from its source text, so the keyword disappears for unedited writes there (its corpus test needs `cloudPositions` at 0 changed lines). Edited and regenerated entries go through the writer this ticket fixes.
- **Duplicates:** `unnamed_<n>` numbering must stay as today so `d.unnamed_2` still names the second list.
- **OpenFOAM versions:** none known; Foundation 11/14 and ESI share these file kinds.
