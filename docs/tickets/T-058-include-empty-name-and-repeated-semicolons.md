# T-058: Include directives with no file name raise `FoamKitError`; `#includeFunc x;;` is handled like `#include "f";;`

- **Issue:** [#77](https://github.com/mcgoldba/foamkit/issues/77)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-046 (#62, `;` after include directives; this ticket finishes its edge cases), T-029 (#40, `#includeModel`/`#includeConstraint`).
- **Found by:** the T-046 reviewer (PR #73, notes 2 and 3). Pre-existing on main; not regressions.

## Goal
An include directive with no file name fails to load with `FoamKitError` naming file and line, and every include directive treats a repeated `;` the same way.

## Reproduction (planner, 2026-10-31, `t-052-entry-value-of-several-lists` at 0eb75b1 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
**No file name:**
| Input | Today |
|---|---|
| `#include ;`, `#sinclude ;`, `#includeIfPresent ;`, `#includeEtc ;`, `#includeFunc ;`, `#includeModel ;`, `#includeConstraint ;` (top level or in a sub-dict) | **loads silently** with value `""`; written `#include "";` (and so on) |
| `#include "";`, `#include ""`, `#includeFunc ""` | same: value `""`, written back as is |
| `#include`, `#includeFunc` (nothing after the keyword) | bare `IndexError: list index out of range`, no file or line |

OpenFOAM reads a file name (a string token) after the keyword, so `#include ;` is a read error there. FoamKit should not load a file OpenFOAM rejects as if it were fine (errors never pass silently).

**Repeated `;`:**
| Input | Today |
|---|---|
| `#includeFunc x;;`, `#includeFunc x(a);;` | loads with value `x;` / `x(a);` (the `;` inside the value), written `x;;` |
| `#includeFunc x;;;` | value `x;;` |
| `#include "f";;`, `#include f;;`, `#includeEtc "x";;`, `#includeModel f;;`, `#includeConstraint f;;`, `#includeFunc "x";;`, `#includeFunc x; ;` | `FoamKitError` "More than one ';' after '#…' on line N of file …" |
| `x 1;;` (ordinary entry) | loads `x` = 1, written `x 1;` |

OpenFOAM accepts any number of `;` here (`entry::getKeyword` skips `END_STATEMENT` tokens: Foundation 11 `entryIO.C:50`, ESI `entryIO.C:54`).

## Decision (maintainer, 2026-10-31: option A)
- **Option A (default, recommended per CLAUDE.md):** `#includeFunc x;;` (and `x(a);;`, `x;;;`) raises the same "More than one ';'" `FoamKitError` with file and line as the rest of the family. This is the smaller change, and nothing is silently changed.
- **Option B (OpenFOAM-faithful):** the whole family accepts any run of `;`. The value never contains `;`, and the written text keeps the number of `;` the source had (writing one `;` would silently change the text, which T-020 is meant to stop). This needs the count stored in place of today's `_semicolon` flag and changes its tests; about the same size, but it touches the T-046 tests and the `ofInclude` fields.

The acceptance below is for option A; if the maintainer picks B, replace the "More than one ';'" rows with "loads, value without `;`, written with the same number of `;`".

## Scope
- `_parseIncludeFunc` (`foamkit/types/__init__.py:5705`) and `_parseIncludes` (`:5769`): an empty name after stripping quotes and `;` raises `FoamKitError` with file and line; nothing after the keyword raises the same error instead of `IndexError`; a `;` left at the end of an unquoted `#includeFunc` name after the first one is stripped raises "More than one ';'".

## Out of scope
- `//` inside the name (T-036); comments after the directive (T-056)
- Includes inside lists (T-042) and value-position includes (T-046)
- Repeated `;` after ordinary entries (`x 1;;`, unchanged)

## Acceptance criteria
- [ ] **Failing tests first:** every row of both tables, at top level and in a sub-dict.
- [ ] Each "no file name" row raises `FoamKitError` naming the file and the directive's line, with no traceback through `fk`; none loads with value `""`.
- [ ] `#includeFunc x;;`, `x(a);;` and `x;;;` raise "More than one ';'" with file and line (option A). The rows that raise today keep their message.
- [ ] `#includeFunc x;`, `#includeFunc f(a;b);` and `#includeFunc f(name="a;b");` load as today (a `;` inside parentheses or quotes is part of the arguments).
- [ ] No golden file changes. All `tests/releases/` files behave as before; the full T-046 test file stays green.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Files that loaded now fail:** a file with `#include "";` or `#includeFunc x;;` loaded before and raises after. `#include "";` names no file. `#includeFunc x;;` is valid OpenFOAM, so option A rejects a file OpenFOAM reads, as `#include "f";;` already does since T-046; that is the trade-off option B removes. 0 Foundation 11-14 tutorial files use either form (ESI not checked); say so in the commit body.
- `#sinclude ""` / `#includeIfPresent ""` may be skipped by OpenFOAM instead of failing; raising is still the explicit choice. If the maintainer prefers loading them, they must at least warn once with file and line.

## Ranking rationale
Small and close to the T-046 code, but no Foundation 11-14 tutorial file has these shapes and the input is already invalid, so it ranks with the other low-frequency edge cases after T-054.
