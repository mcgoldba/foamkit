# T-053: A `;` inside a quoted list item (`x ( "a;b" 1 );`, `#include "a;b"`) no longer adds an empty item or writes an unreadable file

- **Issue:** [#70](https://github.com/mcgoldba/foamkit/issues/70)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-036 (#48, `//` inside a quoted string; same missing quote-awareness in the line parser), T-037 (#53, the empty-item bug this re-creates), T-042 (#57, `#include` inside a list), T-046 (#62, a `;` **after** an include, a different bug in `ofInclude`).
- **Found by:** the T-042 reviewer (PR #66): `#include "a;b"` inside a list writes a file FoamKit cannot read back. The planner's reproduction shows the cause is any quoted list item containing `;`, not the include. Pre-existing on main.

## Goal
A list item whose quoted string contains `;` loads as one item, with no extra item, and is written back so it reads again. Anything still unsupported raises `FoamKitError` naming file and line.

## Reproduction (planner, 2026-10-30, `t-048-glued-parentheses-in-list-items` at 693d945 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| `x ( "a;b" 1 );` | **silent change:** loads as 3 items, `"a;b"`, `1` and an empty `ofStr('')`; written multi-line with a blank item line; **re-read fails** with `FoamKitError: Unhandled pattern found!` (no file or line) |
| `x ( #include "a;b" 1 );`, `x ( #include "a;b" );` | same: an extra empty item, and the written file fails to re-read with `Unhandled pattern found!` |
| `x` / `(` / `    "a;b"` / `    1` / `);` (multi-line), and the same with `#include "a;b"` | fails on load: `FoamKitError: Unhandled pattern found!` with no file or line |
| `note "a;b";`, `#include "a;b"` (dict level) | OK, round-trip (must not change) |

Not related to T-046: there the `;` follows the directive (`#include "f";`) and the bug is in `ofInclude`; here the `;` is inside the quotes and the list parser splits on it.

## Real tutorial occurrences (planner, 2026-10-30)
0 in Foundation 11 and 14 and ESI v2606 tutorials (`git grep` for a quoted string containing `;`; the only dictionary hit, ESI `arch "LSB;label=32;scalar=64"`, is a `FoamFile` header entry at dict level). Likely sources are user-written strings: file names, `#message` text, shell snippets.

## Scope
- The list parser in `foamkit/types/__init__.py` (`_parseList` / `_parseListValues` and the line splitting that feeds them): a `;` inside a quoted string, honouring `\"` escapes, does not end an item or a list. Reuse the quote-aware scanner from T-035 / T-036 where possible.
- The `Unhandled pattern found!` message on this path names file and line.

## Out of scope
- `//` inside strings (T-036); `;` after a directive (T-046)
- Layout of the written list (T-020)

## Acceptance criteria
- [ ] **Failing tests first:** every bug row of the table, one-line and multi-line, at top level and inside a sub-dict; plain strings and `#include "a;b"`.
- [ ] `x ( "a;b" 1 );` loads as exactly 2 items; the written file re-reads to the same items; write 1 == write 2. Same for the include and multi-line forms.
- [ ] No list in the table ever gains an empty item (errors never pass silently): it round-trips, or raises `FoamKitError` naming file and line.
- [ ] No `Unhandled pattern found!` without file and line on any row.
- [ ] The dict-level rows behave as today. No golden file changes. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Unterminated quote:** follow T-035's rule (`FoamKitError` with file and line).
- Same list code as T-048 (in progress) and the same quote-aware stripping as T-036. Start after T-048 merges; if T-036 is in flight, land after it and reuse its scanner.

## Ranking rationale
Right after T-036. It silently adds an item and writes an unreadable file, but no tutorial has the form; it shares T-036's fix (quote-aware line parsing).
