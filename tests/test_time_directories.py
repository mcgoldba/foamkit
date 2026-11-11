"""
T-063: latest time and time-directory listing handle non-integer times.

OpenFOAM writes time directories such as `0.5` and `1e-05`.  Names that are
not times (`constant`, `nan`, `inf`, `1_0`, hidden entries, `postProcessing`)
are ignored, and times are ordered by numeric value.
"""

import shutil
import sys

import pytest

import foamkit.functions as fkf
from foamkit import FoamKitError
from foamkit.functions._paths import _isTime, latestTimeName
from conftest import FIXTURES

timeDirs = fkf.timeDirs

# - The directories of the ticket's reconstructed set.
TICKET_NAMES = ["0", "0.5", "1e-05", "100", "constant", "nan", "1_0"]


def mkdirs(base, *names):
    for name in names:
        (base / name).mkdir(parents=True, exist_ok=True)


def expectFoamKitError(func, *args, **kwargs):
    """Return the FoamKitError raised by the call; no error is an AssertionError."""
    try:
        func(*args, **kwargs)
    except FoamKitError as err:
        return err
    raise AssertionError("no FoamKitError was raised")


@pytest.fixture
def ticketCase(case):
    """pitzDaily with the ticket's reconstructed directories."""
    mkdirs(case, *TICKET_NAMES)
    return case


# ---------------------------------------------------------------- getLatestTime


def test_latest_time_of_ticket_set_is_100_reconstructed(ticketCase):
    assert fkf.getLatestTime(ticketCase) == ("100", "reconstructed")
    assert fkf.isDecomposed(ticketCase) is False


@pytest.mark.parametrize(
    "processorTimes, latest, caseType",
    [
        (["0"], "100", "reconstructed"),
        (["0", "50"], "100", "reconstructed"),  # earlier
        (["0", "0.25"], "100", "reconstructed"),  # earlier, non-integer
        (["0", "200"], "200", "decomposed"),  # later
        (["0", "100.5"], "100.5", "decomposed"),  # later, non-integer
        (["0", "1e+03"], "1e+03", "decomposed"),  # later, exponent
    ],
)
def test_latest_time_with_processor0(ticketCase, processorTimes, latest, caseType):
    mkdirs(ticketCase / "processor0", *processorTimes)
    assert fkf.getLatestTime(ticketCase) == (latest, caseType)
    assert fkf.isDecomposed(ticketCase) is (caseType == "decomposed")
    assert fkf.isReconstructed(ticketCase) is (caseType == "reconstructed")


@pytest.mark.parametrize(
    "processorTimes, latest, caseType",
    [
        (["0", "0.25"], "0.5", "reconstructed"),  # the ticket's contradiction
        (["0", "1e-06"], "0.5", "reconstructed"),
        (["0", "1e-01"], "0.5", "reconstructed"),
    ],
)
def test_latest_time_non_integer_reconstructed_vs_processor0(
    case, processorTimes, latest, caseType
):
    mkdirs(case, "0.5", "1e-05")
    mkdirs(case / "processor0", *processorTimes)
    assert fkf.getLatestTime(case) == (latest, caseType)
    assert fkf.isDecomposed(case) is (caseType == "decomposed")


def test_latest_time_non_integer_processor0_later_than_reconstructed(case):
    """A later non-integer `processor0` time makes the case decomposed."""
    mkdirs(case, "0.5", "1e-05")
    mkdirs(case / "processor0", "0", "0.75")
    assert fkf.getLatestTime(case) == ("0.75", "decomposed")
    assert fkf.isDecomposed(case) is True


@pytest.mark.parametrize("name", ["nan", "-inf"])
def test_processor0_nan_and_negative_inf_are_ignored(ticketCase, name):
    """`nan` and `-inf` are not times, so they never make a case decomposed."""
    mkdirs(ticketCase / "processor0", "0", name)
    assert fkf.getLatestTime(ticketCase) == ("100", "reconstructed")
    assert fkf.isDecomposed(ticketCase) is False


@pytest.mark.parametrize("name", ["inf", "1_000"])
def test_processor0_non_time_names_are_not_times(ticketCase, name):
    """`inf` and `1_000` are not times in `processor0` either."""
    mkdirs(ticketCase / "processor0", "0", name)
    assert fkf.getLatestTime(ticketCase) == ("100", "reconstructed")
    assert fkf.isDecomposed(ticketCase) is False


def test_isDecomposed_agrees_with_getLatestTime_on_equal_times(ticketCase):
    """
    Equal latest times: the two functions agree, and the case counts as
    reconstructed (`isDecomposed` needs a strictly later `processor0` time).
    """
    mkdirs(ticketCase / "processor0", "0", "100")
    _, caseType = fkf.getLatestTime(ticketCase)
    assert fkf.isDecomposed(ticketCase) is (caseType == "decomposed")
    assert fkf.isReconstructed(ticketCase) is (caseType == "reconstructed")


@pytest.mark.parametrize(
    "names, latest",
    [
        (["0.5", "1e-05"], "0.5"),
        (["1e-05"], "1e-05"),
        (["0.5", "1e-05", "0.25"], "0.5"),
        (["1e-05", "1e-04"], "1e-04"),
    ],
)
def test_case_with_only_non_integer_times_returns_real_latest(case, names, latest):
    """The real latest time is returned, not '0' (names are not integer-only)."""
    mkdirs(case, *names)
    assert fkf.getLatestTime(case) == (latest, "reconstructed")


def test_plain_directory_with_only_non_integer_times(tmp_path):
    """Not a case (no system/controlDict): caseType stays None."""
    mkdirs(tmp_path, "0.5", "1e-05")
    assert fkf.getLatestTime(tmp_path) == ("0.5", None)


@pytest.mark.parametrize("withEmptyProcessor0", [False, True])
def test_negative_only_times_are_reconstructed_without_processor0_times(
    case, withEmptyProcessor0
):
    """No placeholder '0' for a missing `processor0` may beat a negative time."""
    # - `0.orig` keeps it a case (isCase) without a time named `0`
    (case / "0").rename(case / "0.orig")
    mkdirs(case, "-1")
    if withEmptyProcessor0:
        mkdirs(case / "processor0")
    assert fkf.getLatestTime(case) == ("-1", "reconstructed")
    assert fkf.isDecomposed(case) is False
    assert fkf.isReconstructed(case) is True


def test_case_without_extra_times_returns_0(case):
    assert fkf.getLatestTime(case) == ("0", "reconstructed")


def test_latest_time_ignores_non_time_names(case):
    mkdirs(case, "nan", "1_0", "inf", "latestTimeLater")
    assert fkf.getLatestTime(case) == ("0", "reconstructed")


# -------------------------------------------------------------------- timeDirs


def test_timeDirs_ticket_set_in_numeric_order(ticketCase):
    assert timeDirs(ticketCase) == ["0", "1e-05", "0.5", "100"]


def test_timeDirs_default_path_is_current_directory(ticketCase, chdir):
    chdir(ticketCase)
    assert timeDirs() == ["0", "1e-05", "0.5", "100"]
    assert timeDirs(path=None, processor=False) == ["0", "1e-05", "0.5", "100"]


def test_timeDirs_processor_lists_processor0_times(ticketCase):
    mkdirs(ticketCase / "processor0", "0", "0.25", "7", "1e-03", "constant", "nan")
    assert timeDirs(ticketCase, processor=True) == ["0", "1e-03", "0.25", "7"]
    # - the reconstructed listing is unchanged
    assert timeDirs(ticketCase) == ["0", "1e-05", "0.5", "100"]


def test_timeDirs_processor_without_processor0_is_empty(case):
    """No `processor0` means no decomposed times (an empty list, not an error)."""
    assert timeDirs(case, processor=True) == []


def test_timeDirs_ignores_files_hidden_and_postProcessing(case):
    mkdirs(case, "0.5", ".hidden", ".git", "postProcessing")
    (case / "7").write_text("a file, not a directory")
    (case / "8.5").write_text("a file, not a directory")
    assert timeDirs(case) == ["0", "0.5"]


def test_timeDirs_orders_numerically_not_lexically(case):
    mkdirs(case, "10", "9", "1e-05", "2", "0.10", "0.9")
    assert timeDirs(case) == ["0", "1e-05", "0.10", "0.9", "2", "9", "10"]


# - What the ticket's rule ("decimal or exponent number, optionally signed;
#  not nan/inf/underscores") implies for each name.
VALID_NAMES = ["-1", "-0.5", "+1", "1E5", "1e+05", "1e-05", "5.", ".5", "0.0"]
INVALID_NAMES = [
    "nan",
    "NaN",
    "inf",
    "Infinity",
    "-inf",
    "1_0",
    "1_000.5",
    "0x10",
    "1e",
    "e5",
    "-",
    "+",
    ".",
    "1.2.3",
    "1 0",
    "1,5",
    "1e999",
    "-1e999",
]


@pytest.mark.parametrize("name", VALID_NAMES)
def test_time_name_rule_accepts_signed_decimal_and_exponent_names(name):
    assert _isTime(name)


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_time_name_rule_rejects_names_that_are_not_times(name):
    assert not _isTime(name)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            n,
            marks=pytest.mark.skipif(
                n == "5." and sys.platform == "win32",
                reason="Windows drops the trailing dot of a directory name",
            ),
        )
        for n in VALID_NAMES
    ],
)
def test_timeDirs_accepts_signed_decimal_and_exponent_names(case, name):
    mkdirs(case, name)
    assert name in timeDirs(case)


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_timeDirs_rejects_names_that_are_not_times(case, name):
    mkdirs(case, name)
    assert timeDirs(case) == ["0"]


def test_timeDirs_negative_and_signed_times_in_numeric_order(case):
    mkdirs(case, "-1", "+2", "-0.5", "1")
    assert timeDirs(case) == ["-1", "-0.5", "0", "1", "+2"]


@pytest.mark.parametrize("pair", [("1", "1.0"), ("10", "1e1")])
def test_timeDirs_keeps_same_value_names_in_a_deterministic_order(tmp_path, pair):
    results = []
    for i, order in enumerate([pair, pair[::-1]]):
        path = tmp_path / f"c{i}"
        shutil.copytree(FIXTURES / "pitzDaily", path)
        mkdirs(path, *order)
        results.append(timeDirs(path))
    assert sorted(results[0]) == sorted(["0", *pair])
    assert results[0] == results[1]
    assert results[0][0] == "0"


def test_timeDirs_is_public_on_foamkit_functions():
    """`foamkit.functions` has no `__all__`; its public names are its imports."""
    import foamkit.functions

    assert hasattr(foamkit.functions, "timeDirs"), "timeDirs is not exposed"
    assert callable(foamkit.functions.timeDirs)


# -------------------------------------------------- same-value time directories


@pytest.mark.parametrize("pair", [("1", "1.0"), ("10", "1e1")])
def test_same_value_times_raise_FoamKitError_naming_both(case, capsys, pair):
    mkdirs(case, *pair)
    err = expectFoamKitError(fkf.getLatestTime, case)
    for name in pair:
        assert name in err.msg
    assert case.name in err.msg
    # - shown to the user, not a silent exit
    assert err.reported is True
    assert "ERROR:" in capsys.readouterr().out


def test_same_value_times_below_the_latest_are_not_a_problem(case):
    """A duplicate older than the latest time is not a problem."""
    mkdirs(case, "1", "1.0", "100")
    assert fkf.getLatestTime(case) == ("100", "reconstructed")


# -------------------------------------------------------------- latestTimeName


@pytest.mark.parametrize(
    "names, expected",
    [
        (["0", "0.5", "1e-05", "100"], "100"),
        (["0.5", "1e-05"], "0.5"),
        (["1e-05", "1e-04"], "1e-04"),
        ([], "0"),
        (["nan"], "0"),
        (["-inf", "0.5"], "0.5"),
    ],
)
def test_latestTimeName_accepts_valid_times(tmp_path, names, expected):
    mkdirs(tmp_path, *names)
    assert latestTimeName(tmp_path) == expected


@pytest.mark.parametrize("bad", ["inf", "Infinity", "1_0", "1_000"])
def test_latestTimeName_rejects_non_time_names(tmp_path, bad):
    mkdirs(tmp_path, "0.5", "5", bad)
    assert latestTimeName(tmp_path) == "5"


# ------------------------------------------------------------- listing failures


def test_unreadable_directory_raises_FoamKitError_naming_it(case, monkeypatch, capsys):
    """A permission error is hard to create on Windows, so mock the scan."""

    def denied(path):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr("foamkit.functions._paths.os.scandir", denied)
    err = expectFoamKitError(timeDirs, case)
    assert case.name in err.msg
    assert err.reported is True
    assert "ERROR:" in capsys.readouterr().out
