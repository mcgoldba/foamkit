# T-055: A `//` comment after a sub-dict or list keyword is not part of the key (`mixture // air …`)

- **Issue:** [#74](https://github.com/mcgoldba/foamkit/issues/74)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Related:** T-056 (#75, trailing `//` comments lost on write; same family, separate code path), T-036 (#48, `//` inside quoted strings), T-039 (#52, keyword glued to its bracket).
- **Found by:** the planner while reproducing the T-046 review notes (PR #73, note 5: comments after an include are lost). Pre-existing on main.

## Goal
A keyword line with a `//` comment, followed by `{` or `(` on the next line, loads under the plain keyword (`mixture`), and the comment is written back on the keyword line.

## Reproduction (planner, 2026-10-31, `t-052-entry-value-of-several-lists` at 0eb75b1 with no `foamkit/` changes; `foamkit` conda env, Python 3.12)
| Input | Today |
|---|---|
| `d // c` / `{` / `a 1;` / `}` (top level) | **silent key change:** loads under the key `d_//_c`, so `case…d` does not exist. The written text is unchanged (`d // c`) |
| `d //c`, `d<TAB>// c` | same: keys `d_//c` and `d\t//_c` (a tab inside the key) |
| `p { d // c` / `{ … } }` (in a sub-dict) | same, one level down |
| `x // c` / `(` / `1` / `);` | bare `ValueError: Name must be a single word.` (no file or line) |
| `d /* c */` / `{ … }` | `FoamKitError` "Unexpected '}'" (block comments: added to T-031) |

## Real tutorial occurrences (planner, 2026-10-31, `git grep` in the Foundation clones; ESI not checked: the scratchpad clones have no `tutorials/` checked out)
| | F11 | F12 | F13 | F14 |
|---|---|---|---|---|
| `{` after a commented keyword (wrong key) | 2 files | 2 | 6 | 6 |
| `(` after a commented keyword (`ValueError`) | 3 files (6 lines) | 3 | 3 | 3 |

- Wrong key, F14: `fluid/aerofoilNACA0012{,Steady}/constant/physicalProperties:28` (`mixture // air at room temperature (293 K)` loads as `mixture_//_air_at_room_temperature__293_K_`) and `incompressibleFluid/simpleRushton{MRF,NCC}/system/createBafflesDict.{baffles,stirrer}:21` (`bafflesGroup // group name`).
- `ValueError`, F11-F14: `multicomponentFluid/{SandiaD_LTS,smallPoolFire2D,smallPoolFire3D}/constant/radiationProperties` (`loTcoeffs // coefss for T < Tcommon` then `(`).

## Scope
- The keyword-line handling for entries whose `{` or `(` is on the next line, in `foamkit/types/__init__.py` (`DictFileParser`): drop the `//` comment from the keyword before the key is built, and keep the comment text so the writer puts it back on the keyword line.
- The `ValueError` path for the list form raises `FoamKitError` with file and line if any shape is still unsupported.

## Out of scope
- `//` after `;`-terminated entries and directives (T-056); `//` after list items (T-057)
- `/* */` after the keyword (T-031); `//` inside a quoted keyword (T-036)
- Spacing before `//` (T-020)

## Acceptance criteria
- [ ] **Failing tests first:** every row of the table except the `/* */` one, at top level and in a sub-dict; the three real files above as byte-exact fixtures in `tests/releases/` (F14 `aerofoilNACA0012/constant/physicalProperties`, `simpleRushtonMRF/system/createBafflesDict.baffles`, F11 or F14 `SandiaD_LTS/constant/radiationProperties`), with source and commit recorded as for earlier fixtures.
- [ ] `d // c` + `{ a 1; }` loads as key `d` with entry `a`; the written text has `// c` on the `d` line; the re-read gives the same keys; write 1 == write 2. Same for `//c`, the tab form and the list form (`x` is a list of one item).
- [ ] No loaded key contains `//`, for any input (errors never pass silently: it loads correctly or raises `FoamKitError` with file and line).
- [ ] The real fixtures load with `mixture`, `bafflesGroup` and `loTcoeffs`/`hiTcoeffs` as keys and round-trip with every comment kept.
- [ ] No golden file changes. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change (keys that used to contain the comment now load under the plain keyword).

## Risks
- **Behaviour change:** code that looked up the corrupted key (`mixture_//_air…`) stops finding it. That key was never valid, so this is a bug fix; say so in the commit body.
- **JSON cache:** a cache written before the fix holds the wrong key. Re-running `fk init` refreshes it; mention this in the commit body.
- Keep the comment's text byte-for-byte; only the spacing before `//` may follow today's writer style until T-020.

## Ranking rationale
Silent key change in stock Foundation 11-14 tutorials (2-6 files per release) and a bare `ValueError` in 3 more. It goes first in the backlog, right after the ranked seven: a wrong key changes what the user edits, which outranks the loud load failures of T-045 onwards.
