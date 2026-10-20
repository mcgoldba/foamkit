"""
The `fk` command line interface and `FoamKitError` (T-017).

The CLI is run in a subprocess (no `shell=True`) from an empty directory so no
`.params/config.ini` is picked up.  The `test_cli_error_*` tests pin today's
output and must keep passing unchanged after `FoamKitError` stops being a
plain `SystemExit`.
"""

import os
import subprocess
import sys

# - `fk monitor res -yrange 1` fails through `userMsg(..., "ERROR")` in
#  `CommandLine.monitor` before anything is read from disk.
FAILING_ARGS = ["monitor", "res", "-yrange", "1"]
FAILING_MSG = "ERROR: `yrange` argument must be length two."

# - Raise a FoamKitError straight from a command, without `userMsg`.
DIRECT_RAISE = """
import sys
sys.argv = ['fk', 'monitor', 'res']
from foamkit import FoamKitError
from foamkit.commandline import CommandLine

def boom(self):
    raise FoamKitError('direct failure')

CommandLine.monitor = boom
from foamkit.__main__ import main
main()
"""

# - Same, but the command reports through `userMsg` first.
USERMSG_RAISE = DIRECT_RAISE.replace(
    "raise FoamKitError('direct failure')",
    "from foamkit import userMsg\n    userMsg('via userMsg', 'ERROR')",
)


def _run(args, cwd, code=None):
    cmd = [sys.executable] + (["-c", code] if code else ["-m", "foamkit"] + args)
    env = dict(os.environ, NO_COLOR="1", PYTHONIOENCODING="utf-8")
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(cwd), env=env, timeout=120
    )


def test_cli_error_exits_with_status_1(tmp_path):
    assert _run(FAILING_ARGS, tmp_path).returncode == 1


def test_cli_error_message_is_printed_once_on_stdout(tmp_path):
    out = _run(FAILING_ARGS, tmp_path)
    assert out.stdout.count(FAILING_MSG) == 1
    assert FAILING_MSG not in out.stderr


def test_cli_error_prints_nothing_on_stderr(tmp_path):
    """No traceback: the error is reported through the message only."""
    assert _run(FAILING_ARGS, tmp_path).stderr.strip() == ""


def test_cli_error_message_follows_the_banner_and_ends_the_output(tmp_path):
    lines = [
        ln for ln in _run(FAILING_ARGS, tmp_path).stdout.splitlines() if ln.strip()
    ]
    assert lines[0] == "FoamKit:  A Pythonic interface to OpenFOAM."
    assert lines[-1] == FAILING_MSG


def test_cli_prints_error_once_for_foamkit_error_raised_without_userMsg(tmp_path):
    """The CLI's handler prints `ERROR: <msg>` itself when `userMsg` did not."""
    out = _run([], tmp_path, code=DIRECT_RAISE)
    assert out.returncode == 1
    assert out.stdout.count("ERROR: direct failure") == 1


def test_cli_does_not_print_userMsg_error_a_second_time(tmp_path):
    out = _run([], tmp_path, code=USERMSG_RAISE)
    assert out.returncode == 1
    assert out.stdout.count("ERROR: via userMsg") == 1


def test_uncaught_foamkit_error_in_a_script_exits_non_zero(tmp_path):
    out = _run([], tmp_path, code="from foamkit import userMsg; userMsg('x', 'ERROR')")
    assert out.returncode == 1
    assert out.stdout.count("ERROR: x") == 1
