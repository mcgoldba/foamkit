"""
T-059: a failed, missing or unrunnable `Allrun` raises `FoamKitError`.

Specification tests.  The stub scripts are POSIX shell scripts, so the tests
that run one are skipped on Windows; the missing-script test runs everywhere
and a Windows-only test covers a POSIX script that the platform cannot run.
Every failure mode is an `AssertionError`: a bare `OSError` or a silent return
from the code under test is converted by `_expect_error` / `_call`.
"""

import os
import shutil
import stat
import subprocess
import sys

import pytest

import foamkit.functions as fkf
import foamkit.types as fkt
from conftest import FIXTURES
from foamkit import FoamKitError

posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="stub Allrun is a POSIX shell script"
)


def _flat(text):
    """Remove all whitespace so that terminal line wrapping does not matter."""
    return "".join(text.split())


def _assert_names_case_and_script(msg, case):
    """`msg` names the case directory and the script (whitespace ignored)."""
    flat = _flat(msg)
    assert _flat(str(case)) in flat
    assert "Allrun" in flat


def _expect_error(fn):
    """Call `fn`; return the `FoamKitError`, or fail with an AssertionError."""
    try:
        fn()
    except FoamKitError as e:
        return e
    except (OSError, subprocess.SubprocessError) as e:
        raise AssertionError(f"bare {type(e).__name__} instead of FoamKitError: {e}")
    raise AssertionError("no FoamKitError raised")


def _call(fn):
    """Call `fn` and fail with an AssertionError on any error."""
    try:
        fn()
    except BaseException as e:  # FoamKitError is a SystemExit
        raise AssertionError(f"unexpected {type(e).__name__}: {e}")


def _write_script(path, body, executable=True):
    # - bytes, not write_text(newline=...): that argument needs Python 3.10, and the project
    # - supports 3.9; writing bytes also keeps the stub LF-only on every OS
    path.write_bytes(("#!/bin/sh\n" + body).encode("utf-8"))
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def spaced_case(tmp_path):
    """A pitzDaily copy whose path contains a space (no shell involved)."""
    path = tmp_path / "pitz daily"
    shutil.copytree(FIXTURES / "pitzDaily", path)
    return path


def _via_method(path):
    return lambda: fkt.CaseParser(path).initOFCase().allRun()


def _via_function(path):
    return lambda: fkf.allRun(path)


runners = pytest.mark.parametrize(
    "runner", [_via_method, _via_function], ids=["case.allRun", "fkf.allRun"]
)

NOISY = (
    "i=1; while [ $i -le 30 ]; do\n"
    '  echo "stdout line $(printf %02d $i)"\n'
    '  echo "stderr line $(printf %02d $i)" >&2\n'
    "  i=$((i+1))\n"
    "done\n"
    "exit 3\n"
)


@posix_only
@runners
def test_exit_0_returns_normally(spaced_case, runner):
    _write_script(spaced_case / "Allrun", "echo ok\nexit 0\n")
    _call(runner(spaced_case))


@posix_only
@runners
def test_exit_3_raises_foamkiterror_naming_case_script_and_code(spaced_case, runner):
    _write_script(spaced_case / "Allrun", NOISY)
    msg = _flat(str(_expect_error(runner(spaced_case))))
    _assert_names_case_and_script(msg, spaced_case)
    assert "3" in msg
    assert "stdoutline30" in msg
    assert "stderrline30" in msg


@posix_only
@runners
def test_message_has_only_the_last_20_lines_of_each_stream(spaced_case, runner):
    _write_script(spaced_case / "Allrun", NOISY)
    msg = _flat(str(_expect_error(runner(spaced_case))))
    for stream in ("stdout", "stderr"):
        assert f"{stream}line11" in msg
        assert f"{stream}line30" in msg
        assert f"{stream}line10" not in msg
        assert f"{stream}line01" not in msg


@posix_only
def test_failure_is_printed_to_the_user(spaced_case, capsys):
    _write_script(spaced_case / "Allrun", NOISY)
    err = _expect_error(_via_method(spaced_case))
    assert err.reported is True
    out = _flat(capsys.readouterr().out)
    assert "ERROR:" in out
    assert "Allrun" in out
    assert "stdoutline30" in out


@runners
def test_missing_script_raises_foamkiterror_naming_the_path(spaced_case, runner):
    assert not (spaced_case / "Allrun").exists()
    msg = _flat(str(_expect_error(runner(spaced_case))))
    _assert_names_case_and_script(msg, spaced_case)


@posix_only
@runners
def test_non_executable_script_raises_foamkiterror_naming_the_path(spaced_case, runner):
    _write_script(spaced_case / "Allrun", "exit 0\n", executable=False)
    msg = _flat(str(_expect_error(runner(spaced_case))))
    _assert_names_case_and_script(msg, spaced_case)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows cannot run POSIX scripts")
@runners
def test_posix_script_on_windows_raises_foamkiterror_not_winerror_193(
    spaced_case, runner
):
    _write_script(spaced_case / "Allrun", "exit 3\n", executable=False)
    msg = _flat(str(_expect_error(runner(spaced_case))))
    _assert_names_case_and_script(msg, spaced_case)


@posix_only
@runners
def test_script_runs_with_the_case_directory_as_working_directory(
    spaced_case, tmp_path, runner, chdir
):
    elsewhere = chdir(tmp_path)
    out = tmp_path / "cwd.txt"
    _write_script(spaced_case / "Allrun", f'pwd -P > "{out}"\n')
    _call(runner(spaced_case))
    assert out.is_file(), "stub did not run"
    assert os.path.samefile(out.read_text().strip(), spaced_case)
    assert not os.path.samefile(elsewhere, spaced_case)


def _make_study(tmp_path, chdir, stub_body=None):
    chdir(tmp_path)
    template = tmp_path / "study.template"
    shutil.copytree(FIXTURES / "pitzDaily", template)
    if stub_body is not None:
        _write_script(template / "Allrun", stub_body)
    return fkt.ofStudy(
        templatePath=template,
        parameterNames=["a"],
        samples=[[1.0], [2.0]],
        updateFunction=lambda case_, values: case_,
    )


@posix_only
def test_study_run_with_failing_sample_raises_naming_the_sample(tmp_path, chdir):
    log = tmp_path / "ran.log"
    study = _make_study(tmp_path, chdir, f'echo x >> "{log}"\nexit 3\n')
    msg = _flat(str(_expect_error(study.run)))
    assert "study.0" in msg
    assert "3" in msg
    assert log.read_text().count("x") == 1, "study went on to the next sample"


@posix_only
def test_study_run_with_passing_samples_runs_all(tmp_path, chdir):
    log = tmp_path / "ran.log"
    study = _make_study(tmp_path, chdir, f'echo x >> "{log}"\n')
    _call(study.run)
    assert log.read_text().count("x") == 2


# ---------------------------------------------------------------------------
# Platform-independent tests: `subprocess.run` is replaced by a fake.
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_run(monkeypatch, spaced_case):
    """Replace `subprocess.run`; return the list of recorded calls.

    Set `fake_run.raises` to an exception to raise from the fake.
    """

    class Fake(list):
        raises = None

    rec = Fake()

    def run(*args, **kwargs):
        rec.append((args, kwargs))
        if rec.raises is not None:
            raise rec.raises
        return subprocess.CompletedProcess(args[0], 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", run)
    return rec


def _lines(prefix, n):
    return "".join(f"{prefix} line {i:02d}\n" for i in range(1, n + 1)).encode()


def test_run_is_called_with_argv_list_cwd_and_no_shell(spaced_case, fake_run):
    _call(_via_method(spaced_case))
    ((args, kwargs),) = fake_run
    argv = args[0]
    assert isinstance(argv, list) and len(argv) == 1
    assert os.path.samefile(os.path.dirname(argv[0]), spaced_case)
    assert os.path.basename(argv[0]) == "Allrun"
    assert os.path.samefile(kwargs["cwd"], spaced_case)
    assert not kwargs.get("shell", False)
    assert kwargs["capture_output"] is True


def test_script_with_dot_slash_prefix_is_resolved_in_the_case(spaced_case, fake_run):
    _call(lambda: fkt.CaseParser(spaced_case).initOFCase().allRun(cmd="./Allrun"))
    argv = fake_run[0][0][0]
    assert os.path.normcase(os.path.realpath(argv[0])) == os.path.normcase(
        os.path.realpath(spaced_case / "Allrun")
    )


def test_called_process_error_message_and_reporting(spaced_case, fake_run, capsys):
    fake_run.raises = subprocess.CalledProcessError(
        3, ["Allrun"], output=_lines("stdout", 30), stderr=_lines("stderr", 30)
    )
    err = _expect_error(_via_method(spaced_case))
    assert err.reported is True
    msg = _flat(str(err))
    _assert_names_case_and_script(msg, spaced_case)
    assert "3" in msg
    for stream in ("stdout", "stderr"):
        assert f"{stream}line11" in msg and f"{stream}line30" in msg
        assert f"{stream}line10" not in msg
    out = _flat(capsys.readouterr().out)
    assert "ERROR:" in out and "stdoutline30" in out


def test_non_utf8_output_does_not_crash_message_building(spaced_case, fake_run):
    fake_run.raises = subprocess.CalledProcessError(
        1, ["Allrun"], output=b"bad \xff\xfe byte\n", stderr=b"\x80 oops\n"
    )
    msg = str(_expect_error(_via_method(spaced_case)))
    assert "byte" in msg and "oops" in msg


def test_output_none_is_handled(spaced_case, fake_run):
    fake_run.raises = subprocess.CalledProcessError(2, ["Allrun"])
    assert "2" in str(_expect_error(_via_method(spaced_case)))


@pytest.mark.parametrize(
    "exc",
    [FileNotFoundError(2, "nope"), PermissionError(13, "denied"), OSError(5, "io")],
    ids=["notfound", "permission", "oserror"],
)
def test_oserrors_raise_foamkiterror_naming_the_path(spaced_case, fake_run, exc):
    fake_run.raises = exc
    msg = _flat(str(_expect_error(_via_method(spaced_case))))
    _assert_names_case_and_script(msg, spaced_case)


def test_windows_193_says_posix_scripts_cannot_run(spaced_case, fake_run):
    exc = OSError(8, "not a valid Win32 application")
    exc.winerror = 193
    fake_run.raises = exc
    msg = str(_expect_error(_via_method(spaced_case)))
    assert _flat(str(spaced_case)) in _flat(msg)
    assert "POSIX" in msg and "Windows" in msg


def test_missing_case_directory_is_reported(fake_run, spaced_case):
    case = fkt.CaseParser(spaced_case).initOFCase()
    shutil.rmtree(spaced_case)
    fake_run.raises = FileNotFoundError(2, "nope")
    msg = str(_expect_error(case.allRun))
    assert "case directory" in msg and "does not exist" in msg


def test_function_and_study_use_the_same_path(tmp_path, chdir, spaced_case, fake_run):
    fake_run.raises = subprocess.CalledProcessError(3, ["Allrun"], output=b"x\n")
    assert "3" in str(_expect_error(_via_function(spaced_case)))
    fake_run.clear()

    study = _make_study(tmp_path, chdir)
    msg = str(_expect_error(study.run))
    assert "study.0" in msg and "3" in msg
    assert len(fake_run) == 1, "study went on to the next sample"
