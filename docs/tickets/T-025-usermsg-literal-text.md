# T-025: `userMsg` prints messages literally and always raises `FoamKitError` at ERROR level

- **Issue:** [#35](https://github.com/mcgoldba/foamkit/issues/35)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Depends on:** T-017 (PR #34). Found in the T-017 review, which is posted on PR #34.

## Goal
Any message FoamKit shows the user is printed exactly as written, including text copied from case files such as `[velocity]`. `userMsg(..., "ERROR")` always raises `FoamKitError`, whatever the message contains.

## Bug (reproduced 2026-10-20 on the T-017 branch)
`userMsg` (`foamkit/__init__.py`, the `print(f'[{style}]{level}:[/{style}] {msg}')` line) passes `msg` to `rich.print` as **markup**:
- `userMsg("value [velocity] ok", "INFO")` prints `INFO: value  ok`. `[velocity]` is silently dropped, and the same happens at WARNING and ERROR.
- `userMsg("a [/] b", "ERROR")` raises **`rich.errors.MarkupError`** instead of `FoamKitError`. `except FoamKitError` and T-017's CLI handler miss it, and `fk` shows a traceback.
- Messages often contain untrusted case-file text, for example Foundation 14 `dimensions [velocity];` (T-013) and directive text (T-016's planned warnings). So a crafted or ordinary case file can turn an error message into a crash.

## Maintainer requirement (2026-10-20)
- At ERROR level, `userMsg` **always** raises `FoamKitError`, whatever the message text.
- The message is printed **literally** at every level.
- Fix direction: `rich.markup.escape(msg)` for every level (only the level label stays styled), or something equivalent.

## Scope
- `userMsg` in `foamkit/__init__.py`: escape the message, keep the styled level label, and keep the DEBUG-logger branch unchanged (it does not use markup).
- **Other rich output sites:** audited 2026-10-20.
  - `foamkit/__main__.py`:
    - `:83` (T-017 CLI handler) already uses `escape(e.msg)`;
    - `:38` prints the version banner (no case text);
    - `:41` prints a fixed `pf` deprecation string.
  - `foamkit/types/__init__.py:28-29` creates a `rich.console.Console()` that is not used for printing.
  - Every other `print(` in `foamkit/types` and `foamkit/functions` is Python's built-in `print` (no markup).

  The tester re-runs `grep -rn "from rich\|rich\." foamkit` and records any new site. Every site that interpolates non-constant text must escape it.
- Tests: extend `tests/test_config.py` / `tests/test_foamkit_error.py`, or add a new `tests/test_usermsg.py`.

## Out of scope
- Replacing rich, or changing message styles or colours
- Moving `userMsg` to the logging module

## Acceptance criteria
- [ ] **Failing tests first.** Parametrize over messages `value [velocity] bad`, `a [/] b`, `[bold]x`, `x [y` (unbalanced) and `x ]y` (unbalanced), and over levels `INFO`, `WARNING`, `ERROR`. Check:
  - captured stdout contains the message **literally**;
  - at `ERROR`, the call raises `FoamKitError` (and nothing else), and `err.value.msg` equals the original text;
  - at `INFO` and `WARNING`, nothing is raised.
- [ ] A plain message (`"boom"`) prints exactly as before, including the styled level label: an existing-output check (byte-for-byte stdout comparison with today's output for the no-markup case).
- [ ] CLI: `fk` with a failure whose message contains `[/]` exits 1 with one `ERROR:` line and no traceback. Use a subprocess test in `tests/test_cli.py`; the tester picks a path that reaches `userMsg` with case text, or monkeypatches one.
- [ ] Audited rich sites are listed in the PR, and each interpolating site escapes its text.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Intentional markup:** a caller who put markup in a message on purpose would now see the tags literally. A grep of `userMsg(` call sites shows no styled messages, but the tester confirms with `grep -rn 'userMsg(.*\['`.
- `escape` does not touch `\` sequences that are not markup. Check that Windows paths in messages (`C:\Users\...`) print unchanged.

## Ranking rationale
**First, ahead of T-016.**
- **It is tiny** and changes every message FoamKit prints.
- **It is a crash path** on untrusted input that T-017's handler cannot catch.
- **T-016 makes it worse:** T-016 adds a WARNING that quotes directive text from case files, so a `[...]` in a directive would be mangled, or raise `MarkupError` while the file loads. Fixing `userMsg` first means T-016 (and T-013's `[velocity]` messages) are safe from the start.
- **T-023 depends on it:** T-023 promises "one clean `ERROR:` line, no traceback" for every subcommand, which only holds once `userMsg` cannot raise `MarkupError`.

## Completion notes (implementer)
- `userMsg` (`foamkit/__init__.py`) now calls `rich.get_console().print(label + escape(msg), emoji=False, highlight=False)` instead of `rich.print(f'...{msg}')`. `from rich import print` is replaced by `import rich` and `from rich.markup import escape`; `print` was used nowhere else in that module. The label markup and styles are unchanged (WARNING's invalid `bold orange` still renders unstyled).
- `escape()` keeps `C:\dir\[velocity]` intact (tested). `emoji=False` makes `:warning:` print literally (no test; checked by hand: `x :warning: C:\dir\[velocity] 12 [/]` prints unchanged). `highlight=False` is needed by `test_only_the_label_is_styled_when_message_has_markup`: with rich's default highlighter, brackets and numbers in the message get coloured on a terminal. Visible change: on a colour terminal, numbers/paths in messages are no longer auto-coloured; plain no-colour output is byte-identical.
- `emoji` and `highlight` are Console.print arguments that `rich.print` does not expose, hence `rich.get_console().print`. The tests' `rich.get_console` monkeypatch still applies because it is looked up through the module.
- The DEBUG-logger branch and `FoamKitError(msg)` (original unescaped text, `reported = True`) are unchanged.
- Numbers: pytest 731 passed, 1 skipped, 7 xfailed on 3.12 and 3.9; ruff check 190 (baseline 190, no change); ruff format 55 files (baseline 55); mypy 127 (baseline 127). The ci.yml baselines are not lowered.

### Update after review (backslash fix)
- `rich.markup.escape()` appends a `\` when the text ends in an odd number of backslashes, so `userMsg('C:\dir\')` printed `C:\dir\`. `userMsg` now builds `Text.assemble((f'{level}:', style), ' ', msg)` and prints it with `rich.get_console().print(line, emoji=False, highlight=False)`. The message is never parsed as markup, so `escape` is no longer used and its import was removed (replaced by `from rich.text import Text`).
- WARNING's `"bold orange"` does not raise: `Text` render resolves span styles with `console.get_style(..., default=Style.null())`, so the unparseable name is ignored and WARNING stays unstyled (verified; pinned ANSI tests pass). INFO and ERROR label ANSI is byte-identical. `emoji=False` is kept (harmless, Text is not emoji-processed anyway).
- Numbers: pytest 749 passed, 1 skipped, 7 xfailed on 3.12 and 3.9; ruff check 190 (baseline 190); ruff format 55 files (max 55); mypy 127 (max 127). No baseline change.
