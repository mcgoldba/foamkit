# T-090: a one-line bare list between entries (`a 1;` / `( x y )` / `b 2;`) no longer hides the next entry

- **Issue:** [#124](https://github.com/mcgoldba/foamkit/issues/124)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (the statement scanner ends a one-line bare list at its closing `)`, as it already does for the multi-line form; the multi-line path from T-084 stores and writes it)
- **Related:** T-084 (#112; bare lists keep no keyword, multi-line form; this is the one-line form it leaves out), T-048 (#64; glued parentheses in list items), T-052 (#69; entry values of several lists), T-035 (#47; the end-of-statement scan), T-020a (#27; unedited entries are written from source).
- **Depends on:** **T-084** (#112), in progress: same bare-list key and writer; this ticket reuses them. Found by the T-084 tester.

## Goal
A file with a one-line bare list between entries loads every entry (`d.b` is `2`, the list is its own `unnamed_<n>` entry, as the multi-line form already is), and any form FoamKit still cannot read raises `FoamKitError` naming the file and line instead of hiding entries.

## Today (planner, reproduced on 401bb6c = `origin/main`, 2026-11-10)
`DictFileParser(p).readDictFile()`; the multi-line form is correct and is the reference.

| Input (after the header) | Loads as | Silent? |
|---|---|---|
| `a 1;` / `(` / `x y` / `)` / `b 2;` (multi-line, reference) | `a`, `unnamed_1 = [x, y]`, `b` | correct |
| `a 1;` / `( x y )` / `b 2;` | `a`, **`_ = ['x y )', 'b 2']`**; **no `b`** | **yes**: `d.b` reads `None`; `d.b = 5` writes a second `b 5;` |
| same with `( 1 2 3 )` | `_ = ['1 2 3 )', 'b 2']`, no `b` | **yes** |
| `( x y )` / `a 1;` / `b 2;` (list first) | `_ = ['x y )', 'a 1']`, `b`; **no `a`** | **yes** |
| `a 1;` / `( x y )` / `b 2;` / `c 3;` | `a`, `_` (holds `b`), `c` | **yes**: only the next entry is lost |
| `a 1;` / `( x y ) // c` / `b 2;` | `a`, `_` (holds `b`) | **yes** |
| `a 1; ( x y ) b 2;` (one line) | `a`, `_ = 'x y ) b 2'` | **yes** |
| `s { a 1; ( x y ) b 2; }` (sub-dict, multi-line) | `s.a`, `s._` (holds `b`); `s.b` missing | **yes** |
| `a 1;` / `((1 2) (3 4))` / `b 2;` (nested, one line) | `a` only; **list and `b` both missing** from the model | **yes** |
| `a 1;` / `( x y );` / `b 2;` (with `;`) | `a`, **`_ = 'x y )'`** (a string, `(` lost), `b` | wrong key and type, `b` kept |
| `a 1;` / `b 2;` / `( x y )` (list last) | `FoamKitError` "Could not find end of statement", line 11 | loud |
| `( x y )` alone | `FoamKitError`, line 9 | loud |

An unedited write keeps the file text (T-020a), but the model is wrong: the hidden entry cannot be read or edited, assigning it adds a duplicate, and regenerating the `_` entry (an edit, or `toString(_preserve=False)`) writes `(                       x y )` / `            b 2;` as one garbled value. Two one-line lists in a file both map to the key `_`, and the second replaces the first: `a 1;` / `( x y );` / `( p q );` / `b 2;` loads `_ = 'p q )'`, so `( x y )` is gone from the model, and without `;` (`( x y )` / `b 2;` / `( p q )` / `c 3;`) `b` and `c` are hidden too.

Cause (for the implementer to confirm): the scanner does not treat `(` at the start of a statement as a complete bare list when it closes on the same line, so it reads on to the next `;`; the `(` keyword is then sanitised to `_` by `SPECIAL_CHARS`.

Real tutorials: **0 files**. Foundation 11 (9cbf94f) and 14 (3155431), `git grep` for a one-line `( … )` line, at any indent, whose previous line ends with `;` or `}`, excluding data files (`polyMesh`, `*Positions`, `*.eMesh`, field files in `0/`, `*.orig`, `boundaryData`, `reactions*`, scripts): no hits. The column-0 `();` lines found (`boundary` / `();` in `hotRoomComfort`, `sweep` and `nanoNozzle` `blockMeshDict`s, `writeFlags` / `();` in `mixerVessel` `snappyHexMeshDict`) have their keyword on the line above and are not bare. ESI v2606 not checked (no clone available). Users hit it by hand-written or generated files.

## OpenFOAM semantics
In a `dictionary` file OpenFOAM expects a keyword before each entry; a bare list is the whole content of non-dictionary files such as `cloudPositions` (T-084). Whether OpenFOAM accepts a bare list *between* dictionary entries was not checked against an OpenFOAM build. FoamKit already loads the multi-line form there as `unnamed_<n>` and writes it back as read (T-084), so the one-line form should match it.

## Design (planner, 2026-11-10)
- **Option A (recommended):** a statement that starts with `(` and whose brackets balance on that line (using the T-035 quote- and comment-aware scan) ends at its closing `)`, plus an optional `;`. It is stored like the multi-line form (`unnamed_<n>`, T-084's key and writer), and the next entry loads as its own entry. Same at the top level and in sub-dicts; `;` or no `;` is kept as read. This also replaces the `_` key of the `( x y );` row.
- **Required fallback (errors never pass silently):** any bare one-line form the scanner still cannot end (for example a nested `((1 2) (3 4))` if the T-084 list reader does not take it, or a list last in the file without `;`) raises `FoamKitError` naming the file and the list's line. No form may hide an entry.
- **Option B (if A turns out larger than S):** every one-line bare list raises `FoamKitError` with file and line. Loud, but it stops files that load today (`( x y );` between entries) from loading; the planner recommends A.

## Scope
- `foamkit/types/__init__.py`: the statement scanner in `DictFileParser` (top level and sub-dicts) and the bare-list path T-084 adds.
- Tests: extend T-084's `tests/test_bare_top_level_list.py` or add `tests/test_one_line_bare_list.py` with every row of the table, top level and sub-dict.

## Out of scope
- Multi-line bare lists and the `unnamed_1` keyword on write (T-084).
- Counted bare lists (`2(a b)`, T-080) and `N{…}` items (T-049).
- Glued keywords (`x(1);`, T-039).

## Acceptance criteria
- [ ] **Failing tests first:** every **yes** row of the table, at the top level and in a sub-dict.
- [ ] `a 1;` / `( x y )` / `b 2;` loads `a == 1`, `unnamed_1 == ['x', 'y']`, `b == 2`; the same for `( 1 2 3 )`, the list first, a trailing `// c` comment (kept on write), two entries after it, and all three on one line.
- [ ] `( x y );` between entries loads as `unnamed_1` (not `_`), with `;` kept on write.
- [ ] Two one-line bare lists load as `unnamed_1` and `unnamed_2`; neither is lost.
- [ ] The nested one-line `((1 2) (3 4))` between entries loads as one `unnamed_<n>` list of two lists with `b` kept, or raises `FoamKitError` naming the file and line; never a missing entry.
- [ ] An unedited write reproduces each input byte for byte; after `d.b.value = 5` the file has one `b 5;` and the list as read; write 1 == write 2.
- [ ] The multi-line rows of T-084 and every file in `tests/releases/` and `tests/fixtures/pitzDaily` write the same text as before.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): a one-line bare list no longer hides the next entry (T-090)`.

## Risks
- **Behaviour change:** files that loaded with a `_` entry now load with `unnamed_<n>` and the hidden entry; code reading `d._` breaks (that key was never meaningful).
- **Scanner change near T-035/T-041:** one-line `{ … }` blocks and second entries on a line use the same scan; their tests must stay green.
- **OpenFOAM:** the semantics of a bare list inside a dictionary are unverified (see above); FoamKit keeps it as read either way.
