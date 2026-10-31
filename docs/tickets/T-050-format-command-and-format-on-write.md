# T-050: `fk format` reformats whole dictionary files in one style; opt-in `format_on_write`

- **Issue:** [#67](https://github.com/mcgoldba/foamkit/issues/67)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M. If the design step shows more than M, split off the `format_on_write` option (Scope 4) as its own S ticket. That part only reuses the formatter.
- **Depends on:** T-020 (#27, preserve the layout of unedited entries), T-019 (#26, no trailing space after `;`, no extra blank line after the `FoamFile` block). Lands **after T-020** (see Sequencing).
- **Related:** T-023 (#32, `fk` user errors print one `ERROR:` line and exit 1), T-006 (headers verbatim), T-031/T-032/T-033 (writer paths that still change text), T-045 (one-element lists change type on write), T-051 (#68, docs page).

## Maintainer decision (2026-10-30, verbatim)
"lets keep the original layout as default, and have a format command the reformats the whole file. Lets also add a user specifiable option to reformat files on write by default."

Background: the coordinator advised against merging tabs and spaces, because tab width varies, and offered two policies. Policy (a) keeps the layout of unedited entries and writes only edited or new entries in the standard style (T-020). Policy (b) reformats the whole file into one consistent style. The maintainer chose (a) as the default, (b) as an explicit command, and an option that makes (b) the default on write.

## Goal
A user can run `fk format <path>` (or `fkf.formatDictFile` / `fkf.formatCase`) to rewrite a dictionary file or a whole case in one consistent style. Only whitespace changes, never content. A user who wants this on every write can turn on the `format_on_write` config option.

## Canonical style (planner proposal, accepted by the maintainer on 2026-10-30: "Lets use the column-16 style.")
- **Spaces only.** No tab is ever written. Indentation is 4 spaces per level (today's `TAB_STR`). Tab width varies by editor, so mixing tabs and spaces is the inconsistency this command exists to remove.
- **Keyword column 16:** the keyword is padded with spaces so the value starts at column 16 (`application     foamRun;`). A keyword of 15 or more characters is followed by exactly one space. This is OpenFOAM's own output (`Ostream::writeKeyword`, 4-space indent, `entryIndentation_` 16), and the real fixtures in `tests/releases/` use it (for example `foundation-11.controlDict`). Formatting a stock tutorial therefore changes as few lines as possible.
  - **Change from today's writer:** `printNameStr` pads to 12 and puts a **tab** after names of 12 or more characters. The canonical style replaces both. One style function is used both by the formatter and for edited and new entries, so edited entries also move to column 16 with no tab. The rejected alternative was keeping column 12: it matches today's goldens, but no OpenFOAM release writes it, so formatting would move every line of every stock file.
- **Blocks and lists:** written in today's writer layout. Sub-dictionaries are always multi-line, and one-line `{ … }` blocks are expanded as the writer does since T-040. Redesigning list layout is out of scope.
- **Blank lines:** blank lines between entries stay where the source has them, and a run of blank lines becomes one. There are no blank lines right after `{` or `(` or right before `}` or `)`.
- **Line ends:** no trailing whitespace. The file ends with exactly one `\n`. Line endings are `\n`, the same as the writer writes today.
- **Not touched:** the banner and the `FoamFile` header are written exactly as T-006 writes them. The text inside comments, quoted strings and `#{ … #}` code blocks stays byte-identical.

## Safety rules ("Errors never pass silently")
Formatting may only change whitespace between tokens. For every file, the formatter checks all of the following **before writing anything**:
1. **Same tokens:** the input and output, tokenized with whitespace dropped, give equal token sequences. Strings, `//` and `/* */` comments and `#{ … #}` blocks each count as one token compared byte for byte. Values, directives, comments and their order are therefore unchanged.
2. **Line-ending directives:** directives that end at the end of their line (`#include "f"` with no `;`, `#remove x`, `#if`/`#else`/`#endif`, and so on) still end their line.
3. **Same entries on re-read:** the output re-reads to entries equal to those of the input.
4. **Idempotent:** formatting the output again gives the same bytes.

If any check fails, or the file does not load, `FoamKitError` is raised. It names the file and the first line that differs or fails, and **no file is written**. For a case directory, every file is formatted and checked in memory first, and nothing is written unless all of them pass. Known lossy writer paths (T-031 block comments, T-032 number text, T-033 `#codeStream`, T-045 one-element lists) are therefore refused loudly instead of being changed silently.

## Scope
1. **Style:** one function in `foamkit/types/__init__.py` defines the canonical style (it replaces the column-12 and tab rule in `printNameStr`). Edited and new entries use it on every write. Regenerate the goldens and review the diff: it should contain only the keyword column and the tab.
2. **Python API**, in `foamkit/functions/` and exported from `foamkit.functions`, with type hints and docstrings:
   - `formatDictFile(path) -> bool` formats one dictionary file in place and returns whether it changed.
   - `formatCase(path) -> list[Path]` formats every dictionary file that `fk init` would read: the same `_isDictFile` and `dict_filesize_limit` rules, and files `init` skips are left alone. It returns the changed files.
   - Both raise `FoamKitError` on a path that does not exist, a directory that is not a case, or a file that is not a dictionary, naming the path.
3. **CLI:** `fk format <path>`. Add `format` to `COMMANDS` in `foamkit/__main__.py` and add `CommandLine.format` in `foamkit/commandline/__init__.py` with an argparse parser, following the other commands. `<path>` is a required positional (as in `cloneCase src`), because this command rewrites files and should not default to the current directory. It accepts a file or a case directory. It prints one line per reformatted file and a summary such as "3 files reformatted, 12 unchanged", and exits 0. Any user error prints one `ERROR:` line and exits 1, with no traceback (T-023 rule). It does not read or write the `.params` cache.
4. **`format_on_write` option** (default **off**). It is a key in the config FoamKit already has. Add `'format_on_write': False` to `CONFIG_DEFAULTS` and `format_on_write = False` under `[default]` in `foamkit/config.ini`, so it is coerced to `bool` like `debug`. Users set it with `fk setConfig format_on_write True` (per user, `~/.foamkit/config.ini`) or in `.params/config.ini` (per project).
   - `ofCase.write()` gains an optional `format: Optional[bool] = None` argument, where `None` means "use the config". When the option is on, each file is written as usual and then passed through the formatter, with all safety rules applied (rule 1 compares against the normal write output). This **bypasses T-020's layout preservation**: unedited entries are reformatted too. All files are formatted and checked before the first one is written.
   - Adding an optional argument with a default does not change existing calls, so no deprecation path is needed.

## Why this option design
- FoamKit already has a layered `config.ini` lookup (`.params/config.ini`, then `~/.foamkit/config.ini`, then the legacy `~/.pyfoamd`, then the package default), typed defaults in `CONFIG_DEFAULTS`, and a `fk setConfig` command. One new key gives the "user-specifiable default" with no new mechanism.
- An environment variable, a `pyproject.toml` section or `~/.config/foamkit` would each add a second settings system.
- The `write(format=...)` argument is the smallest per-call override. It lets scripts and tests choose without touching the user's config.

## Sequencing: after T-020
- Until T-020 lands, every write already rewrites the whole file in the writer's style. `format_on_write` would then do almost nothing, and `fk format` would differ from a plain write only in the column-16 style.
- T-020 adds the "modified" flag and the preserve-or-regenerate split. This ticket plugs into that split (`format_on_write` means "regenerate everything") instead of T-020 having to retrofit a bypass.
- The safety checks raise on files whose write path is still lossy. Landing after the writer fixes ranked ahead of T-020 (T-019, T-031, T-032, T-033, T-045) means more real files format cleanly instead of raising.

## Out of scope
- `--check` and `--diff` modes (report without writing, for CI). These can follow as a separate ticket if the maintainer wants them.
- Formatting files that FoamKit cannot load yet. They raise `FoamKitError` with the load error's file and line.
- Header and banner layout (T-006, T-019, T-021), list layout redesign, and number formatting (T-032).
- A `-format` flag on `fk write`. The config key covers it.
- The docs page (T-051, #68).
- The empty `cleanDictFile` stub in `foamkit/functions/` is not reused or changed.

## Acceptance criteria
- [ ] Failing tests are written first (tester), with no OpenFOAM install needed.
- [ ] **Golden tests** under `tests/golden/` pin the canonical style: column 16, a 15+ character keyword followed by one space, 4-space nesting, no tabs, blank-line collapsing, no trailing whitespace and a single final newline. There is also one golden for a file mixing tabs and spaces.
- [ ] **Idempotence:** `format(format(x)) == format(x)` for every golden input and every fixture that formats.
- [ ] **Real fixtures:** for every file in `tests/releases/`, `formatDictFile` either (a) succeeds, gives the same token sequence as the source, re-reads to the same entries and is idempotent, or (b) raises `FoamKitError` naming the file and a line. In case (b), the source file is unchanged on disk. The tester records which fixtures raise today, with the ticket that will fix each one. No other exception type is allowed.
- [ ] **Safety tests:** a writer change that alters a token (simulated, for example a number written differently) makes `formatDictFile` raise `FoamKitError` with file and line and leaves the file unchanged. In a case directory with one such file, no file is written.
- [ ] **`format_on_write`:** off by default. With the option off, `case.write()` output equals T-020's preserved layout. With it on, through config or `write(format=True)`, output equals `formatDictFile` applied to that output. `write(format=False)` overrides a config set to `True`. The option is read through `getFoamKitConfig` and coerced to `bool`.
- [ ] **CLI tests** (`tests/test_cli.py`): `fk format <file>` and `fk format <case>` exit 0 and report counts. A missing path, a non-case directory, a non-dictionary file and an unformattable file each exit 1 with one `ERROR:` line naming the path and no traceback. Running `fk format` with no path exits non-zero with argparse usage.
- [ ] The goldens are regenerated for the column-16, no-tab style, and the diff is reviewed as style-only.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the T-002 baseline (`ci.yml`). The commit is `feat(cli): …`, and its body describes the new command, the option, and the column-12-to-16 and tab-to-space change for written entries.

## Risks
- **Output change for edited entries:** the keyword column moves from 12 to 16, and the tab after long keywords becomes a space. Users who diff FoamKit output against earlier FoamKit output will see this once. Say so in the commit body. The maintainer chose column 16 at approval (2026-10-30).
- **Per-project config is relative to the working directory:** `.params/config.ini` is looked up from the current directory, not from the case path. Document this (T-051). Moving the lookup to the case directory is out of scope.
- **OpenFOAM versions:** whitespace between tokens is not significant to OpenFOAM's parser in any tested release, except where a directive ends at the end of its line. Rule 2 guards that. `#{ … #}` code is C++ and is kept verbatim.
- **No backup:** `fk format` rewrites files in place without a `.params` backup. It only changes whitespace and refuses anything else, so version control is the expected undo. State this in the help text.
- **Performance:** each file is parsed twice (format and re-read check). This is fine at `dict_filesize_limit` sizes.
