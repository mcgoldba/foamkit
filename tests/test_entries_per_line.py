"""Several entries on one line raise FoamKitError until T-041 parses them (T-037 review).

Maintainer decision (option b): a second entry on the same line after ANY entry, not
just a list, raises `FoamKitError` naming the file and the line, instead of silently
losing the entry.  T-041 will parse such lines; the strict xfails here flip then.

Real file (byte-exact copy, verified with `cmp`):
- foundation-14.helmholtzResonance.blockMeshDict, OpenFOAM-14 at commit a4867fc:
  https://github.com/OpenFOAM/OpenFOAM-14/blob/a4867fc/tutorials/fluid/helmholtzResonance/system/blockMeshDict
  Lines 144 and 145 are
    x1  14; x2   6; x3  20; x4   6; x5   4; // X divisions
    yc   6; ys  12; zc $yc; zs $ys;         // Y and Z corner and side divisions
"""

import re

import pytest

import foamkit.functions as pf
import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import TESTS
from test_banner_variants import BODY, ONE_LINE_BLOCK
from test_directives import HEADER

NL = "\n"
HELM = TESTS / "releases" / "foundation-14.helmholtzResonance.blockMeshDict"
HL = HEADER.count(NL)
XF_T041 = pytest.mark.xfail(strict=True, reason="T-041: second entry on a line")


def _read_error(path):
    with pytest.raises(FoamKitError) as err:
        fkt.DictFileParser(path).readDictFile()
    return str(err.value)


def _line(msg, n):
    return re.search(rf"\bline {n}\b", msg, re.IGNORECASE)


def _write(tmp_path, text, name="entryLine"):
    path = tmp_path / name
    path.write_text(text)
    return path


# --- the real file -----------------------------------------------------------------


def test_helmholtz_fixture_has_the_two_multi_entry_lines():
    lines = HELM.read_text().split(NL)
    assert lines[143].startswith("x1  14; x2   6; x3  20; x4   6; x5   4;")
    assert lines[144].startswith("yc   6; ys  12; zc $yc; zs $ys;")


def test_helmholtz_raises_naming_the_file_and_the_first_multi_entry_line():
    msg = _read_error(HELM)
    assert HELM.name in msg
    assert _line(msg, 144), msg


def test_helmholtz_message_does_not_blame_a_list():
    assert "after a list" not in _read_error(HELM)


@XF_T041
def test_helmholtz_every_variable_survives_a_write(tmp_path):
    d = fkt.DictFileParser(HELM).readDictFile()
    out = tmp_path / "wa"
    out.write_text(d.toString())
    again = fkt.DictFileParser(out).readDictFile()
    wanted = {"x1": 14, "x2": 6, "x3": 20, "x4": 6, "x5": 4, "yc": 6, "ys": 12, "o": 6}
    for obj in (d, again):
        assert {k: getattr(obj, k).value for k in wanted} == wanted
        assert getattr(obj, "zc") is not None
        assert getattr(obj, "zs") is not None


# --- ordinary entries ------------------------------------------------------------------
SAME_LINE = [
    pytest.param("x 1; y 2;" + NL, (), 1, id="top-level"),
    pytest.param(
        "d" + NL + "{" + NL + "    x 1; y 2;" + NL + "}" + NL,
        ("d",),
        3,
        id="in-subdict",
    ),
    pytest.param("x 1; y 2; z 3;" + NL, (), 1, id="three-entries"),
    pytest.param("x 1; y 2; // c" + NL, (), 1, id="then-a-comment"),
]


@pytest.mark.parametrize("body, prefix, body_line", SAME_LINE)
def test_second_entry_on_a_line_raises_naming_file_and_line(
    tmp_path, body, prefix, body_line
):
    path = _write(tmp_path, HEADER + body)
    msg = _read_error(path)
    assert "entryLine" in msg
    assert _line(msg, HL + body_line), msg
    assert "after a list" not in msg


@pytest.mark.parametrize("body, prefix, body_line", SAME_LINE)
@XF_T041
def test_second_entry_on_a_line_is_loaded_with_its_value(
    tmp_path, body, prefix, body_line
):
    d = fkt.DictFileParser(_write(tmp_path, HEADER + body)).readDictFile()
    node = d
    for name in prefix:
        node = getattr(node, name)
    assert node.x.value == 1
    assert node.y.value == 2


@pytest.mark.parametrize(
    "body",
    [
        "x 1;" + NL + "y 2;" + NL,
        "x 1; // y 2;" + NL + "z 3;" + NL,
        "x 1; /* y 2; */" + NL + "z 3;" + NL,
        "x ( 1 ); // c" + NL + "z 3;" + NL,
    ],
    ids=["two-lines", "line-comment", "block-comment", "list-comment"],
)
def test_one_entry_per_line_with_a_trailing_comment_still_loads(tmp_path, body):
    """Only a real second entry raises; a comment after the `;` is not one."""
    fkt.DictFileParser(_write(tmp_path, HEADER + body)).readDictFile()


# --- one-line FoamFile ----------------------------------------------------------------------
BANNER = HEADER.split("FoamFile")[0]


def test_banner_file_with_a_one_line_foamfile_raises_naming_the_file(tmp_path):
    path = _write(tmp_path, BANNER + ONE_LINE_BLOCK + BODY, "fvSchemes")
    msg = _read_error(path)
    assert "fvSchemes" in msg
    assert _line(msg, BANNER.count(NL) + 1), msg


def test_banner_file_with_a_one_line_foamfile_is_still_a_dict_file(tmp_path):
    path = _write(tmp_path, BANNER + ONE_LINE_BLOCK + BODY, "fvSchemes")
    assert pf.isDictFile(path) is True


def test_headerless_one_line_foamfile_is_still_skipped_by_isDictFile(tmp_path):
    """T-005 rule, unchanged: without a banner, a one-line block is not recognised."""
    path = _write(tmp_path, ONE_LINE_BLOCK + BODY, "fvSchemes")
    assert pf.isDictFile(path) is False


@pytest.mark.xfail(strict=True, reason="T-021: one-line FoamFile block")
def test_one_line_foamfile_block_loads(tmp_path):
    """T-021 parses a one-line FoamFile block; until then it raises (T-037)."""
    path = _write(tmp_path, BANNER + ONE_LINE_BLOCK + BODY, "fvSchemes")
    d = fkt.DictFileParser(path).readDictFile()
    assert d._foamFile is not None
