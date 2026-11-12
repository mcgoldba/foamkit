# T-095: a `//` comment after a scalar entry (`k 4; // note`) is kept when the entry is edited or regenerated

- **Issue:** [#136](https://github.com/mcgoldba/foamkit/issues/136)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (store the comment in three constructors and one parser path, print it in two writers, update two pinned golden files). If the `==` decision below makes existing tests fail beyond the rows listed here, split it: T-095a storing and writing, T-095b equality.
- **Depends on:** **T-087** (#115) merged: its 18 strict xfails (`COMMENT_NOT_STORED` in `tests/test_value_none.py`) are removed by this ticket, and both change the same `.value` and writer paths.
- **Related:** T-056 (#75; trailing `//` comments, which this ticket takes the scalar rows from), T-083 (#111; edits inside a sub-dict regenerate the whole dict today), T-020 (#27; T-020a writes unedited entries from source, `_preserve=False` and the pinned regenerated style), T-057 (#76; comments after list items), T-031 (#42; `/* */` comments), T-071 (#101; `ofBoundBox` already keeps its comment).
- **Found by:** the T-087 work (PR #135, maintainer request for a separate ticket, 2026-11-12).

## Goal
Editing a scalar entry that has a trailing `//` comment, or editing anything that makes FoamKit regenerate it, writes the comment back on the entry's line instead of silently dropping it.

## Today (planner, reproduced on ddcc8da = `origin/main`, 2026-11-12, in a detached worktree)
Each input loads with the right value, and an **unedited** write keeps the comment (T-020a writes the line from source). The comment is lost as soon as the entry is regenerated: its own value is edited, a sibling in the same sub-dict is edited (the whole sub-dict is regenerated until T-083), or the file is written with `toString(_preserve=False)`. Nothing is printed.

| Input (top level and in a sub-dict) | Loaded as | `_comment` stored | Regenerated |
|---|---|---|---|
| `k 4; // note`, `k 0.5; // note` | `ofInt`, `ofFloat` | `None` | **`k 4;`** |
| `k abc; // note`, `k "abc"; // note`, `k on; // note` | `ofStr`, `ofBool` | `None` | **no comment** |
| `k $a; // note` | `ofVar` | `None` (stored on a shared line, but not written, see below) | **no comment** |
| `k (1 2) (3 4); // note` | `ofListGroups` | `None` | **no comment** |
| `k [0 2 -1 0 0 0 0] 1e-05; // note`, `k k [0 2 -1 0 0 0 0] 1e-05; // note` | `ofDimensionedScalar` | `None` | **no comment** |
| `k uniform 1; // note` | `ofUniformField` | `None` | **no comment** |
| `box (0 0 0) (1 2 3); // note` | `ofBoundBox` | `' note'` | kept (must not change) |
| `k (1 2); // note`, `k (1 2 3); // note` | `ofSplitList` | `' note\n'` | **no comment** (stored but not written; stays with T-056, see Out of scope) |

Causes:
- `_ofNamedTypeBase.__init__` takes `_comment` and ignores it (the line that stored it is commented out), so `ofInt`, `ofFloat`, `ofStr`, `ofBool`, `ofVar` and the other subclasses never keep the comment the parser passes (`type_(key, value_, _comment=self._getComment())`).
- `ofDimensionedScalar.__init__` calls `ofFloat.__init__(..., _comment=None)`.
- The uniform-field parser never captures the comment; `ofListGroups` does not store it.
- `ofVar.toString` does not print `_comment`.
- `_getComment()` returns the text with its trailing newline (`' X divisions\n'`), so storing it as is adds a blank line after the entry (seen in a runtime prototype).

Real files: 73-85 Foundation 11-14 tutorial files per release have a `//` after a `;` (T-056 count, 2026-10-31); most are scalar entries. Stock pitzDaily `system/fvSolution` has `U 0.9; // 0.9 is more stable but 0.95 more convergent` in `relaxationFactors.equations`: editing `U`, or `p`'s relaxation in the same block, drops it.

## Design
- Store the comment text after `//` byte-for-byte, without the line ending, on every type in the table: `_ofNamedTypeBase.__init__` keeps `_comment`; `ofDimensionedScalar` passes it on; the uniform-field and list-group parsers capture it the way `ofBoundBox` does.
- Every scalar writer prints it as today's `_comment` writers do: ` //<text>` after the `;`, on the same line (one space before `//`; the source spacing is not kept for regenerated entries, as for every other padding).
- Several entries on one line (T-041): the comment stays with the last entry on the line, as the parser already assigns it (`x5` in `x1 14; … x5 4; // X divisions`).
- **`==`:** today `ofInt` equality is the dataclass one, which compares `_comment` but not the name (`ofInt('k', 4) == ofInt('j', 4)` is `True`). Storing the comment would make a loaded `k 4; // note` unequal to `ofInt('k', 4)`. Recommended: `_comment` does not take part in `==` for the types this ticket touches, like the name; `ofBoundBox` keeps its own `__eq__` (T-071). The tester pins the choice.
- Editing the value keeps the comment; deleting the entry deletes it; `.value = None` (T-087) writes `count; // note`.

## Expected golden diffs (deliberate; review each as "now equal to the source")
`tests/golden/regenerated/` pins the `toString(_preserve=False)` style. Storing the comment changes exactly these lines (prototype, runtime patch of the constructor only, on ddcc8da):
- `pitzDaily.system.fvSolution.txt` line 59: `        U           0.9;` → `        U           0.9; // 0.9 is more stable but 0.95 more convergent`
- `foundation-14.helmholtzResonance.blockMeshDict.txt` line 143: `x5          4;` → `x5          4; // X divisions`
- same file, line 151: `zs          $ys;` → `zs          $ys; // Y and Z corner and side divisions` (needs the `ofVar` writer change; the prototype stored but did not print it)
- same file, line 153: `o           6;` → `o           6; // O-grid divisions`
- no added blank lines; `pitzDaily.system.controlDict.txt` and `foundation-11.damBreak.fvSchemes.txt` unchanged.

So `tests/test_preserve_layout.py::test_preserve_false_gives_the_regenerated_style[system.fvSolution]` and `[releases.foundation-14.helmholtzResonance.blockMeshDict]` fail until the goldens are regenerated in this ticket's PR. Any other golden diff must be a comment restored on its source line, listed in the PR body; anything else is a regression.

## Scope
- `foamkit/types/__init__.py`: `_ofNamedTypeBase.__init__`, `ofDimensionedScalar.__init__`, `ofVar.toString`, `ofListGroups` (store and write), the uniform-field parse path in `DictFileParser`, and the comment text handed to constructors (no trailing newline).
- Tests: a new `tests/test_scalar_comments.py`; remove `COMMENT_NOT_STORED` and its xfail branch from `tests/test_value_none.py`; regenerate the two goldens above.

## Out of scope
- Lists (`ofSplitList`, `k (1 2); // c`), the include family, `{ // c`, `} // c`, `); // c` and entries after a multi-line list: T-056. Comments after list items: T-057. `/* */` comments (`x 1; /* c */`): T-031. `//` inside strings: T-036.
- Keeping the source spacing before `//` in a regenerated entry (T-050's style).
- Keeping siblings of an edited sub-dict entry from source: T-083. After T-083 a sibling edit no longer regenerates the entry, but `_preserve=False`, `fk format` and a direct edit still do, so this ticket is needed either way.

## Overlap
- **T-056:** its rows `x 1; // c`, `x 1;//c`, `x "a"; // c` and `c (1 2) (3 4); // c` (top level and sub-dict), and its "editing a value keeps its comment" criterion for scalars, move here. T-056 keeps the rest; it is not blocked by this ticket.
- **T-083:** both fix the sub-dict sibling-edit row; whichever lands second keeps the other's test green.
- **T-087:** removes the 18 strict xfails (9 rows x top/sub) it added for this gap.

## Acceptance criteria
- [ ] **Failing tests first:** every bold row of the table, at the top level and in a sub-dict, for each trigger: an edit of the entry's value, an edit of a sibling in the same sub-dict, and `toString(_preserve=False)`.
- [ ] Each row: the written line is the regenerated entry followed by ` //` and the comment text byte-for-byte, on the same line, with no added blank line; re-reading gives the same value and comment; write 1 == write 2.
- [ ] The comment is never part of a value: `k 4; // note` loads `ofInt` with value 4; `k abc; // note` has value `abc`.
- [ ] The `ofBoundBox` row and every unedited write in `tests/releases/` and `tests/fixtures/pitzDaily` are unchanged.
- [ ] The `==` choice is pinned by a test (recommended: a loaded `k 4; // note` equals `ofInt('k', 4)`).
- [ ] `case.save()` → load keeps the comment of an edited entry (pitzDaily `fvSolution` `U 0.9`), or a test and the docstring say the cache drops it.
- [ ] `COMMENT_NOT_STORED` is gone from `tests/test_value_none.py` and its 18 tests pass.
- [ ] The goldens change only as listed under "Expected golden diffs".
- [ ] `pytest -q` passes; ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): keep a // comment after a scalar entry when it is edited (T-095)`; the commit body names the entry kinds.

## Risks
- **Equality and repr:** loaded values gain `_comment` in their repr, and, unless excluded, in `==`; user code comparing loaded values to constructed ones could change result.
- **T-020a fingerprints:** `_comment` is already a fingerprint attribute; storing it changes the fingerprint of commented entries. Unedited writes must stay byte-identical, and a `.params` cache saved before this change must still load and write unchanged (test one).
- **Shared lines:** a comment after a line group belongs to its last entry; deleting that entry deletes the comment, which a user might expect to stay with the line.
- **OpenFOAM versions:** none; `//` comments are read the same by every release.

## Ranking rationale
A silent loss of user annotations on the usual edit of stock files (about 80 Foundation files per release, stock pitzDaily `fvSolution`). It ranks with the silent fixes on stock files, after T-083 and above T-092 (silent, 0 tutorial files) and the loud T-093 regression; it is smaller than T-056 and clears T-087's xfails.
