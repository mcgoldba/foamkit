# T-056: A `//` comment after an entry or directive (`x 1; // c`, `#include "f"; // c`) is kept on write

- **Issue:** [#75](https://github.com/mcgoldba/foamkit/issues/75)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M. If the design shows more than M, split: T-056a entries and the include family, T-056b block openers and closers (`{ // c`, `} // c`, `); // c`).
- **Depends on:** T-036 (#48). Its quote-aware `//` detection is needed so that a `//` inside a string is never taken as the start of a comment.
- **Related:** T-055 (#74, comment after a block keyword), T-057 (#76, comment after a list item), T-031 (#42, `/* */` comments), T-020 (#27, spacing of unedited entries), T-050 (#67, `fk format` must keep comments).
- **Found by:** the T-046 reviewer (PR #73, note 5: `#include "f"; // c` and `#include "f" // c` lose the comment). The planner's reproduction shows every entry kind loses a trailing `//` comment; T-037 recorded "A trailing `// c` is still dropped, as before" without a ticket. Pre-existing on main.

## Goal
A `//` comment at the end of a line that holds an entry, a directive or a block brace is written back on that line, so an unedited read → write keeps every line comment.

## Reproduction (planner, 2026-10-31, `t-052-entry-value-of-several-lists` at 0eb75b1 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
Each row loads with the right values and write 1 == write 2, but the comment is **silently dropped** on the first write:
| Input | Written |
|---|---|
| `x 1; // c`, `x 1;//c`, `x "a"; // c` (top level or in a sub-dict) | `x 1;`, `x "a";` |
| `#include "f"; // c`, `#include "f" // c`, `#include "f";// c` | `#include "f";` / `#include "f"` |
| `#includeEtc "x"; // c`, `#includeFunc streamlines; // c`, `#includeFunc streamlines // c`, `#includeFunc mag(U); // c` | the directive without the comment |
| `l (1 2); // c` | the list, no comment |
| `d { a 1; } // c`, `d` / `{` / `a 1;` / `} // end d` | the sub-dict, no comment |
| `d` / `{ // c` / `a 1;` / `}` | no comment |
| `x` / `(` / `1` / `); // c` | no comment |

Kept today (must not change): whole-line `// c` comments at top level, in sub-dicts and inside lists; `( // c` (kept, moved to its own line); `#remove a; // c` and other verbatim directives (T-016 keeps the whole line).

The value classes already carry a `_comment` field that the writer prints as ` //<text>` (`foamkit/types/__init__.py:218-219`, `:338-339`), but the parser never sets it: `_getLinesList` (`:4607`) cuts the line at `//` and throws the rest away.

## Real tutorial occurrences (planner, 2026-10-31, `git grep -l ';[[:space:]]*//'` over `system/` and `constant/`; ESI not checked: the scratchpad clones have no `tutorials/` checked out)
| | F11 | F12 | F13 | F14 |
|---|---|---|---|---|
| files with a `//` after a `;` | 77 | 73 | 83 | 85 |

F11 has 198 such lines, F14 226. The include family has 0 tutorial files with a trailing comment; it is in scope because the code path is shared.

## Scope
- `DictFileParser` in `foamkit/types/__init__.py`: when a line holding an entry, a directive of the include family or a `{`/`}`/`);` ends in a `//` comment outside quotes, keep its text (byte-for-byte after the `//`) and attach it to that entry, directive or block, using `_comment` where it exists.
- The writer puts it back on the same line. The spacing before `//` may follow today's writer style until T-020.
- Several entries on one line (T-041): the comment stays with the last entry on the line.

## Out of scope
- Comments after a block keyword (`d // c` then `{`): T-055
- Comments after a list item inside a multi-line list: T-057
- `/* */` comments: T-031. `//` inside strings: T-036
- Padding and layout: T-020

## Acceptance criteria
- [ ] **Failing tests first:** every row of the table, at top level and in a sub-dict (two levels deep for one row), plus one real Foundation fixture with trailing comments after `;` (pick a short one, byte-exact, with source and commit recorded).
- [ ] Each row: the written text has the comment text after `//` unchanged and on the same line as its entry; the re-read gives the same entries and comments; write 1 == write 2.
- [ ] The comment is not part of any value: `x 1; // c` loads `x` as `ofInt(1)`, `#include "f"; // c` has value `f`.
- [ ] Editing a value keeps its comment (`d.x = 2` writes `x 2; // c`); deleting the entry deletes the comment.
- [ ] The "Kept today" rows behave as before. No golden file changes unless a golden source has a trailing comment; review any such diff as "now equal to source".
- [ ] The JSON cache (`case.save` / load) keeps the comment, or the docs and a test say that a cache round trip drops it.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **`repr` and `==`:** setting `_comment` changes the repr of loaded values and may change equality between a loaded value and a constructed one (`ofInt(1)`). Decide whether `_comment` takes part in `==`, and test it; user code that compares loaded values to literals must not break.
- **A comment after an edited value:** keep it unless the user removes it. Document the rule.
- **Same parser paths as T-036, T-041 and T-052:** start after T-036 merges.

## Ranking rationale
Silent loss of user annotations in about 80 Foundation tutorial files per release, and in most hand-edited cases. No value changes meaning, so it ranks below the load and write bugs that change values; it follows T-036, whose quote-aware stripping it needs, and comes before T-031.
