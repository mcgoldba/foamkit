"""Several entries on one line (T-041).

T-037 made a second entry on the same line raise `FoamKitError` instead of silently
dropping it.  T-041 parses every entry on the line, in order, at top level and in
sub-dicts.  The tests marked `xfail(strict=True, reason="T-041: ...")` describe the
new behaviour; the implementer removes the markers.  T-040 owns the contents of a
one-line `{ ... }` block, T-027 value-position `#calc`, T-020 layout (entries may be
written on separate lines).

Real files (byte-exact copies in tests/releases/, which is outside the golden glob).
Each was checked by `git hash-object` against the blob in the shallow clone and by
`cmp` against the GitHub raw download (the clones check out CRLF; the raw bytes are LF):
- foundation-14.helmholtzResonance.blockMeshDict, OpenFOAM-14 at commit a4867fc:
  https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-14/a4867fc/tutorials/fluid/helmholtzResonance/system/blockMeshDict
  Lines 144 and 145 are
    x1  14; x2   6; x3  20; x4   6; x5   4; // X divisions
    yc   6; ys  12; zc $yc; zs $ys;         // Y and Z corner and side divisions
- foundation-14.rotatingCube.blockMeshDict, OpenFOAM-14 at a4867fc:
  https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-14/a4867fc/tutorials/incompressibleVoF/rotatingCube/system/blockMeshDict
  Lines 76-80 are `nIn   7; fIn  0.4;` ... `nFar 12; fFar 2.0;`.  The file also has
  value-position `#calc` (line 23, T-027), which stops a full load first.
- foundation-14.refineMeshSector.blockMeshDict, OpenFOAM-14 at a4867fc:
  https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-14/a4867fc/tutorials/mesh/refineMesh/sector/system/blockMeshDict
  Lines 32-38 are `Ax  0.438912;    Ay  0.000000;` ... `Gx  16.895909;   Gy  -6.998515;`.
- foundation-11.refineFieldDirs.blockMeshDict, OpenFOAM-11 at commit 9cbf94f:
  https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-11/9cbf94f/tutorials/mesh/refineMesh/refineFieldDirs/system/blockMeshDict
  Lines 34-40 are the same `Ax ... Gy` block.
- foundation-11.damBreak.fvSchemes, OpenFOAM-11 at 9cbf94f:
  https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-11/9cbf94f/tutorials/compressibleVoF/damBreak/system/fvSchemes
  Line 31 is `div(rhoPhi,U)   Gauss linearUpwind grad(U);Gauss upwind;`.  OpenFOAM reads
  the second part as the keyword `Gauss` with value `upwind`.
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
RELEASES = TESTS / "releases"
HELM = RELEASES / "foundation-14.helmholtzResonance.blockMeshDict"
CUBE = RELEASES / "foundation-14.rotatingCube.blockMeshDict"
SECTOR = RELEASES / "foundation-14.refineMeshSector.blockMeshDict"
FIELD_DIRS = RELEASES / "foundation-11.refineFieldDirs.blockMeshDict"
DAM_BREAK = RELEASES / "foundation-11.damBreak.fvSchemes"
HL = HEADER.count(NL)
XF_T027 = pytest.mark.xfail(strict=True, reason="T-027: value-position #calc")


def _load(path):
    return fkt.DictFileParser(path).readDictFile()


def _read_error(path):
    with pytest.raises(FoamKitError) as err:
        _load(path)
    return str(err.value)


def _line(msg, n):
    return re.search(rf"\bline {n}\b", msg, re.IGNORECASE)


def _write(tmp_path, text, name="entryLine"):
    path = tmp_path / name
    path.write_text(text)
    return path


def _keys(node):
    """Names of the entries of `node`, in order, without comments."""
    return [
        k
        for k, v in vars(node).items()
        if not k.startswith("_") and type(v).__name__ != "ofComment"
    ]


def _cycle(tmp_path, path):
    """Read `path`, write, re-read, write again: (first, second, text1, text2)."""
    first = _load(path)
    text1 = first.toString()
    out = tmp_path / "wa"
    out.write_text(text1)
    second = _load(out)
    return first, second, text1, second.toString()


def _snippet(tmp_path, path, first, last, name="snippet"):
    """A file made of the standard header and lines `first`..`last` (1-based) of `path`."""
    lines = path.read_text().split(NL)[first - 1 : last]
    return _write(tmp_path, HEADER + NL.join(lines) + NL, name)


def _check_values(node, wanted):
    for key, value in wanted.items():
        assert getattr(node, key).value == pytest.approx(value), key


# --- the helmholtzResonance file (category A) ----------------------------------------


def test_helmholtz_fixture_has_the_two_multi_entry_lines():
    lines = HELM.read_text().split(NL)
    assert lines[143].startswith("x1  14; x2   6; x3  20; x4   6; x5   4;")
    assert lines[144].startswith("yc   6; ys  12; zc $yc; zs $ys;")


HELM_VALUES = {"x1": 14, "x2": 6, "x3": 20, "x4": 6, "x5": 4, "yc": 6, "ys": 12}


def test_helmholtz_loads_with_every_variable_of_both_lines():
    d = _load(HELM)
    _check_values(d, HELM_VALUES)
    assert d.zc is not None
    assert d.zs is not None


def test_helmholtz_keeps_the_entries_of_a_line_in_order():
    keys = _keys(_load(HELM))
    wanted = ["x1", "x2", "x3", "x4", "x5", "yc", "ys", "zc", "zs"]
    assert [k for k in keys if k in wanted] == wanted


def test_helmholtz_every_variable_survives_a_write(tmp_path):
    d = _load(HELM)
    out = tmp_path / "wa"
    out.write_text(d.toString())
    again = _load(out)
    wanted = {"x1": 14, "x2": 6, "x3": 20, "x4": 6, "x5": 4, "yc": 6, "ys": 12, "o": 6}
    for obj in (d, again):
        assert {k: getattr(obj, k).value for k in wanted} == wanted
        assert getattr(obj, "zc") is not None
        assert getattr(obj, "zs") is not None


def test_helmholtz_second_write_equals_the_first(tmp_path):
    first, second, text1, text2 = _cycle(tmp_path, HELM)
    assert text1 == text2
    assert _keys(first) == _keys(second)


# - T-041's write behaviour is pinned on lines 144-146.
HELM_ORDER = ["x1", "x2", "x3", "x4", "x5", "yc", "ys", "zc", "zs", "o"]


def test_helmholtz_multi_entry_lines_survive_a_write_in_isolation(tmp_path):
    path = _snippet(tmp_path, HELM, 144, 146)
    first, second, text1, text2 = _cycle(tmp_path, path)
    for d in (first, second):
        _check_values(d, {**HELM_VALUES, "o": 6})
        assert d.zc is not None
        assert d.zs is not None
        assert _keys(d) == HELM_ORDER
    assert text1 == text2


# --- the other category A files --------------------------------------------------------
SECTOR_VALUES = {
    "Ax": 0.438912,
    "Ay": 0.0,
    "Bx": 18.288,
    "By": 0.0,
    "Cx": 0.310358,
    "Cy": -0.310358,
    "Dx": 12.931569,
    "Dy": -12.931569,
    "Hx": 0.405502,
    "Hy": -0.167964,
    "Gx": 16.895909,
    "Gy": -6.998515,
    "Z_DB_low": -0.88706,
    "Z_AC_low": -1.07,
    "Z_high": 4.39208,
}
SECTOR_ORDER = ["Ax", "Ay", "Bx", "By", "Cx", "Cy", "Dx", "Dy", "Hx", "Hy", "Gx", "Gy"]
CUBE_VALUES = {
    "nIn": 7,
    "fIn": 0.4,
    "nOut": 12,
    "fOut": 5.0,
    "nBed": 5,
    "fBed": 0.6,
    "nAtm": 7,
    "fAtm": 4.0,
    "nFar": 12,
    "fFar": 2.0,
}
CUBE_ORDER = list(CUBE_VALUES)

FULL_FILES = [
    pytest.param(SECTOR, SECTOR_VALUES, SECTOR_ORDER, id="sector-F14"),
    pytest.param(
        FIELD_DIRS,
        {**SECTOR_VALUES, "convertToMeters": 1},
        SECTOR_ORDER,
        id="fieldDirs-F11",
    ),
]


def test_fixtures_have_the_multi_entry_lines():
    assert CUBE.read_text().split(NL)[75].startswith("nIn   7; fIn  0.4;")
    assert SECTOR.read_text().split(NL)[31].startswith("Ax  0.438912;    Ay  0.0")
    assert FIELD_DIRS.read_text().split(NL)[33].startswith("Ax  0.438912;    Ay  0.0")
    assert "grad(U);Gauss upwind;" in DAM_BREAK.read_text().split(NL)[30]


@pytest.mark.parametrize("path, values, order", FULL_FILES)
def test_blockmeshdict_loads_with_every_entry(path, values, order):
    d = _load(path)
    _check_values(d, values)
    assert [k for k in _keys(d) if k in order] == order


@pytest.mark.parametrize("path, values, order", FULL_FILES)
def test_blockmeshdict_keeps_every_entry_after_a_write_and_re_read(
    tmp_path, path, values, order
):
    first, second, text1, text2 = _cycle(tmp_path, path)
    for d in (first, second):
        _check_values(d, values)
    assert _keys(first) == _keys(second)


@pytest.mark.parametrize("path, values, order", FULL_FILES)
def test_blockmeshdict_second_write_equals_the_first(tmp_path, path, values, order):
    first, second, text1, text2 = _cycle(tmp_path, path)
    assert text1 == text2


def test_rotating_cube_multi_entry_lines_load_in_isolation(tmp_path):
    d = _load(_snippet(tmp_path, CUBE, 76, 80))
    _check_values(d, CUBE_VALUES)
    assert _keys(d) == CUBE_ORDER


def test_rotating_cube_multi_entry_lines_survive_a_write_in_isolation(tmp_path):
    first, second, text1, text2 = _cycle(tmp_path, _snippet(tmp_path, CUBE, 76, 80))
    for d in (first, second):
        _check_values(d, CUBE_VALUES)
        assert _keys(d) == CUBE_ORDER
    assert text1 == text2


@XF_T027
def test_rotating_cube_loads_whole_with_its_multi_entry_lines():
    """Blocked by value-position `#calc` (T-027) first; T-041 alone does not unblock it."""
    d = _load(CUBE)
    _check_values(d, CUBE_VALUES)


# --- damBreak fvSchemes: `grad(U);Gauss upwind;` ---------------------------------------


def test_dambreak_fvschemes_keeps_both_entries_of_the_glued_line_in_order():
    div = _load(DAM_BREAK).divSchemes
    keys = _keys(div)
    assert "div_rhoPhi_U_" in keys
    assert "Gauss" in keys
    assert keys.index("Gauss") == keys.index("div_rhoPhi_U_") + 1
    assert div.div_rhoPhi_U_.value == "Gauss linearUpwind grad(U)"
    assert div.Gauss.value == "upwind"


def test_dambreak_fvschemes_write_keeps_both_entries(tmp_path):
    first, second, text1, text2 = _cycle(tmp_path, DAM_BREAK)
    assert re.search(r"div\(rhoPhi,U\)\s+Gauss linearUpwind grad\(U\);", text1)
    after = text1.split("grad(U);", 1)[1]
    assert re.search(r"(?<![\w(])Gauss\s+upwind;", after)
    for d in (first, second):
        assert d.divSchemes.Gauss.value == "upwind"
        assert d.divSchemes.div_rhoPhi_U_.value == "Gauss linearUpwind grad(U)"
    assert text1 == text2


def test_dambreak_fvschemes_other_entries_are_unaffected():
    div = _load(DAM_BREAK).divSchemes
    assert div.div_rhoPhi_K_.value == "Gauss upwind"
    assert div.div_phi_alpha_.value == "Gauss interfaceCompression vanLeer 1"


# --- reproduction table, top level and in a sub-dict ----------------------------------


def _where(line, nested):
    """The body with `line` at top level, or as the only line of a sub-dict `d`."""
    if nested:
        return "d" + NL + "{" + NL + "    " + line + NL + "}" + NL
    return line + NL


def _node(d, nested):
    return d.d if nested else d


NESTING = pytest.mark.parametrize("nested", [False, True], ids=["top", "subdict"])
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
def test_second_entry_on_a_line_is_loaded_with_its_value(
    tmp_path, body, prefix, body_line
):
    d = _load(_write(tmp_path, HEADER + body))
    node = d
    for name in prefix:
        node = getattr(node, name)
    assert node.x.value == 1
    assert node.y.value == 2


@pytest.mark.parametrize("body, prefix, body_line", SAME_LINE)
def test_second_entry_on_a_line_survives_write_and_second_write_is_equal(
    tmp_path, body, prefix, body_line
):
    first, second, text1, text2 = _cycle(tmp_path, _write(tmp_path, HEADER + body))
    for d in (first, second):
        node = d
        for name in prefix:
            node = getattr(node, name)
        assert (node.x.value, node.y.value) == (1, 2)
    assert text1 == text2


def test_three_entries_on_a_line_keep_their_order(tmp_path):
    d = _load(_write(tmp_path, HEADER + "x 1; y 2; z 3;" + NL))
    assert _keys(d) == ["x", "y", "z"]
    assert d.z.value == 3


@NESTING
def test_entry_then_sub_dict_on_one_line_keeps_the_sub_dict(tmp_path, nested):
    path = _write(tmp_path, HEADER + _where("a 1; sub { b 2; }", nested))
    node = _node(_load(path), nested)
    assert node.a.value == 1
    assert _keys(node) == ["a", "sub"]
    assert isinstance(node.sub, dict)


@NESTING
def test_entry_then_sub_dict_on_one_line_keeps_the_sub_dict_content(tmp_path, nested):
    """The content of a one-line `{ ... }` is kept (T-040)."""
    path = _write(tmp_path, HEADER + _where("a 1; sub { b 2; }", nested))
    assert _node(_load(path), nested).sub.b.value == 2


@NESTING
def test_entry_then_include_on_one_line_keeps_the_include_verbatim(tmp_path, nested):
    path = _write(tmp_path, HEADER + _where('a 1; #include "f"', nested))
    first, second, text1, text2 = _cycle(tmp_path, path)
    for d in (first, second):
        node = _node(d, nested)
        assert node.a.value == 1
        keys = _keys(node)
        assert keys[0] == "a"
        assert len(keys) == 2
        assert type(vars(node)[keys[1]]).__name__ == "ofInclude"
    assert re.search(r'^\s*#include\s+"f"\s*$', text1, re.MULTILINE)
    assert text1.index("a ") < text1.index("#include")
    assert text1 == text2


@NESTING
def test_entry_then_print_directive_on_one_line_keeps_it_verbatim(tmp_path, nested):
    path = _write(tmp_path, HEADER + _where('a 1; #print "hi"', nested))
    first, second, text1, text2 = _cycle(tmp_path, path)
    for d in (first, second):
        node = _node(d, nested)
        assert node.a.value == 1
        keys = _keys(node)
        assert len(keys) == 2
        assert type(vars(node)[keys[1]]).__name__ == "ofVerbatimDirective"
    assert re.search(r'^\s*#print\s+"hi"\s*$', text1, re.MULTILINE)
    assert text1 == text2


def test_entry_after_a_one_line_sub_dict_is_kept(tmp_path):
    """`d { a 1; } e 2;` loads with `e` (T-041) and the content of `d` (T-040)."""
    d = _load(_write(tmp_path, HEADER + "d { a 1; } e 2;" + NL))
    assert _keys(d) == ["d", "e"]
    assert d.e.value == 2


def test_entry_after_a_one_line_sub_dict_survives_a_write(tmp_path):
    path = _write(tmp_path, HEADER + "d { a 1; } e 2;" + NL)
    first, second, text1, text2 = _cycle(tmp_path, path)
    for d in (first, second):
        assert _keys(d) == ["d", "e"]
        assert d.e.value == 2
    assert text1 == text2


def test_entry_inside_a_one_line_sub_dict_is_kept(tmp_path):
    """`a` of `d { a 1; } e 2;` is kept (T-040)."""
    d = _load(_write(tmp_path, HEADER + "d { a 1; } e 2;" + NL))
    assert d.d.a.value == 1


# --- guards: must keep passing ------------------------------------------------------------


@NESTING
def test_incomplete_trailing_entry_raises_naming_file_and_line(tmp_path, nested):
    body = _where("x 1; y", nested)
    line = HL + (3 if nested else 1)
    msg = _read_error(_write(tmp_path, HEADER + body))
    assert "entryLine" in msg
    assert _line(msg, line), msg


def test_incomplete_trailing_entry_with_more_lines_after_it_raises(tmp_path):
    body = "a 1;" + NL + "x 1; y" + NL + "z 3;" + NL
    msg = _read_error(_write(tmp_path, HEADER + body))
    assert "entryLine" in msg
    assert _line(msg, HL + 2), msg


NOT_A_SPLIT = [
    # - T-037's `_queueTrailing` splits inside the string today (the error quotes 'b";'),
    # - so these fail until T-041 reuses T-035's scanner there.
    pytest.param('s "a; b";', ["s", "z"], id="string"),
    pytest.param('s "a; b"; // c', ["s", "z"], id="string-then-comment"),
    pytest.param("x 1; // y 2; w 3;", ["x", "z"], id="line-comment"),
    pytest.param("x 1; /* y 2; w 3; */", ["x", "z"], id="block-comment"),
    pytest.param("x ( 1 ); // y 2;", ["x", "z"], id="list-then-comment"),
]


@pytest.mark.parametrize("line, keys", NOT_A_SPLIT)
def test_semicolon_in_string_or_comment_does_not_start_an_entry(tmp_path, line, keys):
    d = _load(_write(tmp_path, HEADER + line + NL + "z 3;" + NL))
    assert _keys(d) == keys


def test_semicolon_in_a_string_keeps_the_string_intact(tmp_path):
    d = _load(_write(tmp_path, HEADER + 's "a; b";' + NL + "z 3;" + NL))
    assert d.s.value == '"a; b"'
    assert d.z.value == 3


CODE = (
    "    codeExecute"
    + NL
    + "    #{"
    + NL
    + "        foo(); bar();"
    + NL
    + "    #};"
    + NL
)
# - A top-level `codeExecute` block raises AttributeError ('ofCodeExecute' has no
# - '_name') independent of this ticket, so the code-block guards use a sub-dict.
CODE_BODY = "d" + NL + "{" + NL + "    a 1;" + NL + CODE + "    z 3;" + NL + "}" + NL


def test_semicolons_inside_a_code_block_do_not_split_entries(tmp_path):
    d = _load(_write(tmp_path, HEADER + CODE_BODY)).d
    assert [k for k in _keys(d) if not k.startswith("unnamed")] == ["a", "z"]
    assert d.a.value == 1
    assert d.z.value == 3


def test_semicolons_inside_a_code_block_are_written_back(tmp_path):
    first, second, text1, text2 = _cycle(tmp_path, _write(tmp_path, HEADER + CODE_BODY))
    assert "foo(); bar();" in text1
    assert second.d.z.value == 3
    assert text1 == text2


# --- malformed leftovers raise FoamKitError naming file and line (review round 1) -----------


@pytest.mark.parametrize(
    "line",
    ['x 1; "y"', "x 1; y", "x 1; y;", "a 1;; b 2;", "a 1; ; b 2;"],
    ids=[
        "quoted-word",
        "bare-word",
        "keyword-without-value",
        "empty-statement",
        "spaced-empty-statement",
    ],
)
@NESTING
def test_malformed_leftover_after_an_entry_raises_naming_file_and_line(
    tmp_path, line, nested
):
    msg = _read_error(_write(tmp_path, HEADER + _where(line, nested)))
    assert "entryLine" in msg
    assert _line(msg, HL + (3 if nested else 1)), msg


def test_a_doubled_semicolon_at_the_end_of_an_entry_still_loads(tmp_path):
    d = _load(_write(tmp_path, HEADER + "a 1;;" + NL + "b 2;" + NL))
    assert (d.a.value, d.b.value) == (1, 2)


@pytest.mark.parametrize(
    "line, keys, block, content",
    [
        ("a 1; sub { b 2; }", ["a", "sub"], "sub", {"b": 2}),
        ("d { a 1; } e 2;", ["d", "e"], "d", {"a": 1}),
        ("x 1; d { a 1; b 2; }", ["x", "d"], "d", {"a": 1, "b": 2}),
    ],
    ids=["entry-then-block", "block-then-entry", "entry-then-two-entry-block"],
)
@NESTING
def test_one_line_block_with_content_next_to_other_entries_loads_every_entry(
    tmp_path, line, keys, block, content, nested
):
    """Was an error until T-040 (the block's entries would have been dropped)."""
    d = _load(_write(tmp_path, HEADER + _where(line, nested)))
    node = _node(d, nested)
    assert _keys(node) == keys
    inner = vars(node)[block]
    assert {k: vars(inner)[k].value for k in _keys(inner)} == content


def test_empty_one_line_block_next_to_other_entries_loads(tmp_path):
    d = _load(_write(tmp_path, HEADER + "d { } e 2;" + NL))
    assert _keys(d) == ["d", "e"]
    assert d.e.value == 2


def test_one_line_block_alone_on_its_line_is_unchanged(tmp_path):
    """Loads with its entry (T-040; it was silently empty before)."""
    d = _load(_write(tmp_path, HEADER + "sub { b 2; }" + NL + "z 3;" + NL))
    assert d.sub.b.value == 2
    assert d.z.value == 3


def test_several_entries_inside_a_one_line_block_are_all_kept(tmp_path):
    d = _load(_write(tmp_path, HEADER + "d { a 1; b 2; }" + NL))
    assert _keys(d) == ["d"]
    assert (d.d.a.value, d.d.b.value) == (1, 2)


def test_text_inside_a_one_line_block_that_cannot_be_parsed_names_the_line(tmp_path):
    """`{ a 1; b }`: a lone word is an incomplete entry, never a silent drop."""
    msg = _read_error(_write(tmp_path, HEADER + "d { a 1; b }" + NL))
    assert "entryLine" in msg
    assert _line(msg, HL + 1), msg
    assert "incomplete entry ('b')" in msg


# --- verbatim directive bodies are not split ---------------------------------------------
CODE_STREAM = (
    "d"
    + NL
    + "{"
    + NL
    + "    a 1;"
    + NL
    + "    #codeStream"
    + NL
    + "    {"
    + NL
    + '        codeOptions "-I."; codeLibs "-lm";'
    + NL
    + "    };"
    + NL
    + "    z 3;"
    + NL
    + "}"
    + NL
)


def test_code_stream_body_with_several_entries_per_line_stays_verbatim(tmp_path):
    d = _load(_write(tmp_path, HEADER + CODE_STREAM))
    assert 'codeOptions "-I."; codeLibs "-lm";' in d.toString()
    assert (d.d.a.value, d.d.z.value) == (1, 3)


def test_multi_line_eval_body_with_a_semicolon_is_not_split(tmp_path):
    body = "a 1;" + NL + "b #eval" + NL + "{" + NL + "    $a * 2; c" + NL + "};" + NL
    d = _load(_write(tmp_path, HEADER + body + "z 3;" + NL))
    assert type(d.b).__name__ == "ofEval"
    assert "$a * 2; c" in d.b.value
    assert (d.a.value, d.z.value) == (1, 3)


def test_one_line_eval_body_with_a_semicolon_is_not_split(tmp_path):
    d = _load(_write(tmp_path, HEADER + "b #eval { $a * 2; c };" + NL + "z 3;" + NL))
    assert d.z.value == 3
    assert "b" in vars(d)


# --- the split is linear in the length of a line ----------------------------------------------


def test_one_line_with_many_entries_is_split_in_linear_time(tmp_path):
    import time

    def split(n):
        text = HEADER + " ".join(f"x{i} {i};" for i in range(n)) + NL
        parser = fkt.DictFileParser(_write(tmp_path, text, f"long{n}"))
        start = time.perf_counter()
        parser._splitEntries()
        return time.perf_counter() - start, parser

    small, _ = split(5000)
    big, parser = split(20000)
    assert len(parser.lines) == HL + 20000
    assert big < 5
    assert big < 12 * small + 0.5


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
    d = _load(path)
    assert d._foamFile is not None
