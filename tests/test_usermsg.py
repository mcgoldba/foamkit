"""
`userMsg` prints its message literally at every level and, at ERROR level,
always raises `FoamKitError` (T-025).

Output capture: rich writes to `sys.stdout`, which `capsys` replaces
with a non-terminal stream.  rich then emits no ANSI codes, applies no
highlighting and wraps at 80 columns, so the messages below are kept short and
the expected stdout is exactly `"<LEVEL>: <msg>\n"`.  The styled label is
checked separately by redirecting rich's global console to a colour-forcing
console that writes to a `StringIO` (`_colourConsole`); only the output stream
is replaced; `userMsg` and rich's own printing run unchanged, however
`userMsg` reaches the console.
"""

import io
import logging

import pytest
import rich
from rich.console import Console

from foamkit import FoamKitError, userMsg

LEVELS = ["INFO", "WARNING", "ERROR"]

MESSAGES = [
    "value [velocity] bad",
    "a [/] b",
    "[bold]x",
    "x [y",
    "x ]y",
    "[/bold] closing",
    "[red]a[/red] [",
    r"C:\Users\ivgol\case [velocity]",
]
MESSAGE_IDS = [
    "unknown_tag",
    "bare_closing_tag",
    "known_style",
    "unbalanced_open",
    "unbalanced_close",
    "unmatched_closing_style",
    "valid_markup_then_open",
    "windows_path_with_tag",
]


def _call(msg, level):
    """Call `userMsg`; return the `FoamKitError` it raised, or `None`."""
    try:
        userMsg(msg, level)
    except FoamKitError as err:
        return err
    return None


@pytest.fixture
def _colourConsole(monkeypatch):
    """Route rich's global console to a colour-forcing `StringIO` console."""
    buf = io.StringIO()
    console = Console(
        file=buf,
        force_terminal=True,
        color_system="standard",
        width=80,
        legacy_windows=False,
    )
    monkeypatch.setattr(rich, "get_console", lambda: console)
    return buf


# --- literal text ---------------------------------------------------------


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("msg", MESSAGES, ids=MESSAGE_IDS)
def test_message_is_printed_literally(capsys, msg, level):
    _call(msg, level)
    assert capsys.readouterr().out == f"{level}: {msg}\n"


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("msg", MESSAGES, ids=MESSAGE_IDS)
def test_message_is_printed_once(capsys, msg, level):
    _call(msg, level)
    assert capsys.readouterr().out.count(msg) == 1


@pytest.mark.parametrize("msg", MESSAGES, ids=MESSAGE_IDS)
def test_error_level_raises_only_foamkit_error_with_original_msg(capsys, msg):
    with pytest.raises(BaseException) as err:
        userMsg(msg, "ERROR")
    assert type(err.value) is FoamKitError
    assert err.value.msg == msg
    assert str(err.value) == msg


@pytest.mark.parametrize("level", ["INFO", "WARNING"])
@pytest.mark.parametrize("msg", MESSAGES, ids=MESSAGE_IDS)
def test_info_and_warning_do_not_raise(capsys, msg, level):
    assert userMsg(msg, level) is None


def test_default_level_is_info(capsys):
    userMsg("value [velocity] bad")
    assert capsys.readouterr().out == "INFO: value [velocity] bad\n"


@pytest.mark.parametrize("level", LEVELS)
def test_windows_path_backslashes_print_unchanged(capsys, level):
    msg = r"Could not read C:\Users\ivgol\case\0\U"
    _call(msg, level)
    assert capsys.readouterr().out == f"{level}: {msg}\n"


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize(
    "msg",
    ["C:\\dir\\", "\\", "ends with two \\\\", "a \\ b"],
    ids=["path_trailing_backslash", "lone_backslash", "two_backslashes", "inner"],
)
def test_backslashes_at_end_of_message_print_unchanged(capsys, msg, level):
    _call(msg, level)
    assert capsys.readouterr().out == f"{level}: {msg}\n"


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("msg", [":warning: x", "a :smile: b :thumbs_up:"])
def test_emoji_codes_print_literally(capsys, msg, level):
    _call(msg, level)
    assert capsys.readouterr().out == f"{level}: {msg}\n"


@pytest.mark.parametrize("level", LEVELS)
def test_backslash_before_bracket_prints_unchanged(capsys, level):
    msg = r"see C:\dir\[velocity]"
    _call(msg, level)
    assert capsys.readouterr().out == f"{level}: {msg}\n"


# --- plain messages: existing output, byte for byte ------------------------


@pytest.mark.parametrize("level", LEVELS)
def test_plain_message_plain_output_is_unchanged(capsys, level):
    _call("boom", level)
    assert capsys.readouterr().out == f"{level}: boom\n"


# - Today's styled output.  INFO is blue and ERROR is bold red.  WARNING is
#  unstyled: "bold orange" is not a rich colour, so rich ignores the style.
#  Changing the WARNING colour is out of scope for T-025.
@pytest.mark.parametrize(
    "level, expected",
    [
        ("INFO", "\x1b[34mINFO:\x1b[0m boom\n"),
        ("WARNING", "WARNING: boom\n"),
        ("ERROR", "\x1b[1;31mERROR:\x1b[0m boom\n"),
    ],
)
def test_plain_message_styled_label_is_unchanged(_colourConsole, level, expected):
    _call("boom", level)
    assert _colourConsole.getvalue() == expected


@pytest.mark.parametrize(
    "level, label",
    [
        ("INFO", "\x1b[34mINFO:\x1b[0m"),
        ("WARNING", "WARNING:"),
        ("ERROR", "\x1b[1;31mERROR:\x1b[0m"),
    ],
)
def test_only_the_label_is_styled_when_message_has_markup(_colourConsole, level, label):
    _call("value [velocity] [bold]x[/bold]", level)
    assert _colourConsole.getvalue() == f"{label} value [velocity] [bold]x[/bold]\n"


# --- DEBUG logger branch: unchanged -----------------------------------------


@pytest.mark.parametrize("level", LEVELS)
def test_debug_logging_branch_logs_message_without_printing(capsys, caplog, level):
    caplog.set_level(logging.DEBUG, logger="foamkit")
    _call("value [velocity] bad", level)
    assert capsys.readouterr().out == ""
    assert f"User Msg:{level}: value [velocity] bad" in caplog.text


def test_debug_logging_branch_still_raises_foamkit_error_at_error(caplog):
    caplog.set_level(logging.DEBUG, logger="foamkit")
    err = _call("a [/] b", "ERROR")
    assert err is not None and err.msg == "a [/] b"
