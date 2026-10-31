"""List items with parentheses glued on (`mag(U)`, `4(0 1 2 3)`) (T-048, issue #64).

Specification tests for docs/tickets/T-048-glued-parentheses-in-list-items.md.  A word
with balanced parentheses attached is ONE list item (`mag(U)`, `div(phi,U)`,
`div((I*interpolate(phi)))`, `columnAverage:columnAverage(UMean)`); a number directly
followed by `(` is the number and then a list (`4(0 1 2 3)`).  The parentheses are never
dropped on write; what cannot be kept raises `FoamKitError` with file and line.

Outcome of the ticket's reproduction table on this branch (693d945):

    fields ( p mag(U) );, multi-line mag(U)/div(phi,U),    items split at every paren,
    div((I*interpolate(phi))), columnAverage:...(UMean),   parens lost on write (silent);
    x ( 4(0 1 2 3) 4(4 5 6 7) );, x ( a(0 1) );            write 1 == write 2 is stable
    fields (mag(U));       differs from the table: it loads as `fields ( mag(U);` (the
                           write is unreadable), but the re-read raises FoamKitError
                           ("Could not locate the end of 'fields'"), not IndexError
    x ( mag(U );  (and the multi-line form)                FoamKitError with file and line
                           already (guard)
    x ( mag(U)) );         loads and silently drops both parentheses
    x ( mag(U))\n p );     FoamKitError "Invalid syntax on line N" already (guard)

The tests that failed on 693d945 passed their strict xfails on the T-048 change.

Real files (byte-exact copies in tests/releases/, outside the golden glob).  Shallow
clones of https://github.com/OpenFOAM/OpenFOAM-13 (tag 20260624, commit
18870c24d21c6b982e2cdec27b2f59738cca5f90) and https://github.com/OpenFOAM/OpenFOAM-14
(tag 20261008, commit a4867fc914c10ee10c2f6f83c294c3d3160dd573), extracted with
`git show HEAD:<path>`; `git hash-object` of each copy equals the hash of the file on
GitHub raw at that commit and `cmp` shows no difference.  No file contains a CR.

foundation-13.shockTube.sample                          (`fields (T mag(U) p);`, line 36)
  OpenFOAM-13: tutorials/shockFluid/shockTube/system/sample
  blob 65f93846d73f812c28e17da553eacd8e0b7636d1
foundation-14.hotWire.controlDict                       (`div((I*interpolate(phi)))`, line 55)
  OpenFOAM-14: tutorials/multiRegion/CHT/hotWire/system/controlDict
  blob f20102eb1c48bf251e1dd45087efdaedd96cbe72
foundation-14.concentricCylinders.blockMeshDict.orig    (`arc 10 11(0.07071067811 ...)`, line 56)
  OpenFOAM-14: tutorials/fluid/concentricCylinders/system/blockMeshDict.orig
  blob 65ef05ababa030cbef29553b936dc8bff6b3ea23
"""

import re

import pytest

import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import TESTS
from test_directives import HEADER

NL = "\n"
RELEASES = TESTS / "releases"
SAMPLE = RELEASES / "foundation-13.shockTube.sample"
HOTWIRE = RELEASES / "foundation-14.hotWire.controlDict"
CONCENTRIC = RELEASES / "foundation-14.concentricCylinders.blockMeshDict.orig"
HL = HEADER.count(NL)


def _load(path):
    return fkt.DictFileParser(path).readDictFile()


def _text(item):
    """Text of one list item: the word for a string, `str()` for numbers and lists."""
    if isinstance(item, fkt.ofStr):
        return item.value
    return str(item).strip()


def _sub(body):
    return "sub\n{\n" + "".join("    " + ln + NL for ln in body.splitlines()) + "}\n"


def _wrap(text, container):
    return text if container == "top" else _sub(text)


def _entry(d, container, key="x"):
    return getattr(d if container == "top" else d.sub, key)


def _items(d, container, key="x"):
    return [_text(i) for i in _entry(d, container, key).value]


def _cycle(tmp_path, text):
    """Write `text`, read, write, re-read, write: (first, second, text1, text2)."""
    path = tmp_path / "glued"
    path.write_text(HEADER + text)
    first = _load(path)
    text1 = first.toString()
    out = tmp_path / "wa"
    out.write_text(text1)
    second = _load(out)
    return first, second, text1, second.toString()


def _parens(text):
    """Count of `(` and `)` outside comments."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text.count("("), text.count(")")


CONTAINERS = ["top", "sub"]


def _xfail(reason):
    return pytest.mark.xfail(strict=True, reason=reason)


# --- word items with parentheses attached ------------------------------------------------
# - (id, text, expected items); every one of them is silent corruption today.
WORDS = [
    ("one-line-mag", "x ( p mag(U) );\n", ["p", "mag(U)"]),
    ("one-line-fields-sample", "x ( T mag(U) p );\n", ["T", "mag(U)", "p"]),
    (
        "multi-line-mag-div",
        "x\n(\n    mag(U)\n    div(phi,U)\n    p\n);\n",
        ["mag(U)", "div(phi,U)", "p"],
    ),
    ("one-line-div-phi-U", "x ( div(phi,U) );\n", ["div(phi,U)"]),
    (
        "one-line-div-double",
        "x ( div((I*interpolate(phi))) );\n",
        ["div((I*interpolate(phi)))"],
    ),
    (
        "multi-line-div-double",
        "x\n(\n    div((I*interpolate(phi)))\n);\n",
        ["div((I*interpolate(phi)))"],
    ),
    (
        "one-line-column-average",
        "x ( columnAverage:columnAverage(UMean) );\n",
        ["columnAverage:columnAverage(UMean)"],
    ),
    (
        "multi-line-column-average",
        "x\n(\n    columnAverage:columnAverage(UMean)\n    p\n);\n",
        ["columnAverage:columnAverage(UMean)", "p"],
    ),
    (
        "one-line-htc-model",
        "x ( reactingEulerHtcModel(T.liquid) );\n",
        ["reactingEulerHtcModel(T.liquid)"],
    ),
]
WORD_PARAMS = [
    pytest.param(text, expected, cont, id=f"{name}-{cont}")
    for name, text, expected in WORDS
    for cont in CONTAINERS
]


@pytest.mark.parametrize(("text", "expected", "cont"), WORD_PARAMS)
def test_a_word_with_glued_parentheses_loads_as_one_item(
    tmp_path, text, expected, cont
):
    path = tmp_path / "glued"
    path.write_text(HEADER + _wrap(text, cont))
    assert _items(_load(path), cont, text.split()[0]) == expected


@pytest.mark.parametrize(("text", "expected", "cont"), WORD_PARAMS)
def test_written_text_keeps_every_parenthesis(tmp_path, text, expected, cont):
    text1 = _cycle(tmp_path, _wrap(text, cont))[2]
    assert _parens(text1) == _parens(text)
    for item in expected:
        assert item in text1


@pytest.mark.parametrize(("text", "expected", "cont"), WORD_PARAMS)
def test_written_text_reads_back_to_the_same_items(tmp_path, text, expected, cont):
    _, second, _, _ = _cycle(tmp_path, _wrap(text, cont))
    assert _items(second, cont, text.split()[0]) == expected


@pytest.mark.parametrize(("text", "expected", "cont"), WORD_PARAMS)
def test_second_write_equals_the_first_for_glued_words(tmp_path, text, expected, cont):
    """Stable today (the loss happens on the first read); must stay stable."""
    _, _, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    assert text1 == text2


# --- number glued to a list: `4(0 1 2 3)` ------------------------------------------------
COUNTED = [
    ("one-line", "x ( 4(0 1 2 3) 4(4 5 6 7) );\n"),
    ("multi-line", "x\n(\n    4(0 1 2 3)\n    4(4 5 6 7)\n);\n"),
    ("single", "x ( 4(0 1 2 3) );\n"),
]
COUNTED_PARAMS = [
    pytest.param(text, cont, id=f"{name}-{cont}")
    for name, text in COUNTED
    for cont in CONTAINERS
]


@pytest.mark.parametrize(("text", "cont"), COUNTED_PARAMS)
def test_a_counted_list_never_becomes_flat_integers(tmp_path, text, cont):
    path = tmp_path / "glued"
    path.write_text(HEADER + _wrap(text, cont))
    items = _entry(_load(path), cont).value
    assert any(isinstance(i, fkt.ofList) for i in items), [_text(i) for i in items]
    assert len(items) < 5 * text.count("(")


@pytest.mark.parametrize(("text", "cont"), COUNTED_PARAMS)
def test_counted_list_written_text_keeps_every_inner_list(tmp_path, text, cont):
    text1 = _cycle(tmp_path, _wrap(text, cont))[2]
    assert _parens(text1) == _parens(text)
    assert "(0 1 2 3)" in text1


@pytest.mark.parametrize(("text", "cont"), COUNTED_PARAMS)
def test_counted_list_reads_back_with_its_inner_list(tmp_path, text, cont):
    _, second, _, _ = _cycle(tmp_path, _wrap(text, cont))
    items = _entry(second, cont).value
    assert any(isinstance(i, fkt.ofList) for i in items)


@pytest.mark.parametrize(("text", "cont"), COUNTED_PARAMS)
def test_second_write_equals_the_first_for_counted_lists(tmp_path, text, cont):
    _, _, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    assert text1 == text2


# --- `x ( a(0 1) );`: a word followed directly by a bracket ------------------------------
A_ROWS = [("one-line", "x ( a(0 1) );\n"), ("multi-line", "x\n(\n    a(0 1)\n);\n")]
A_PARAMS = [
    pytest.param(text, cont, id=f"{name}-{cont}")
    for name, text in A_ROWS
    for cont in CONTAINERS
]


def _written_or_none(tmp_path, text, cont):
    """The written text, or None when a FoamKitError named the file and a line."""
    full = _wrap(text, cont)
    path = tmp_path / "glued"
    path.write_text(HEADER + full)
    span = "|".join(str(HL + 1 + i) for i in range(full.count(NL)))
    try:
        return _load(path).toString()
    except FoamKitError as err:
        msg = str(err)
        assert "glued" in msg
        assert re.search(rf"\bline ({span})\b", msg, re.IGNORECASE), msg
        return None


@pytest.mark.parametrize(("text", "cont"), A_PARAMS)
def test_word_then_bracket_keeps_its_parentheses_or_raises_with_file_and_line(
    tmp_path, text, cont
):
    text1 = _written_or_none(tmp_path, text, cont)
    if text1 is not None:
        assert _parens(text1) == _parens(text)


@pytest.mark.parametrize(("text", "cont"), A_PARAMS)
def test_second_write_equals_the_first_for_word_then_bracket(tmp_path, text, cont):
    _, _, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    assert text1 == text2


# --- `fields (mag(U));`: the glued item right against the list brackets ------------------
TIGHT = [
    ("one-line", "x (mag(U));\n"),
    ("with-neighbours", "x (T mag(U) p);\n"),
    ("multi-line", "x\n(mag(U)\n);\n"),
]
TIGHT_PARAMS = [
    pytest.param(text, cont, id=f"{name}-{cont}")
    for name, text in TIGHT
    for cont in CONTAINERS
]


@pytest.mark.parametrize(("text", "cont"), TIGHT_PARAMS)
def test_item_against_the_brackets_round_trips_or_raises_with_file_and_line(
    tmp_path, text, cont
):
    text1 = _written_or_none(tmp_path, text, cont)
    if text1 is None:
        return
    out = tmp_path / "wa"
    out.write_text(text1)
    try:
        second = _load(out)
    except FoamKitError as err:
        pytest.fail(f"the written text cannot be read back: {err}")
    assert _parens(text1) == _parens(text)
    assert second.toString() == text1


@pytest.mark.parametrize("cont", CONTAINERS)
def test_item_against_the_brackets_never_raises_indexerror(tmp_path, cont):
    path = tmp_path / "glued"
    path.write_text(HEADER + _wrap("x (mag(U));\n", cont))
    try:
        text1 = _load(path).toString()
        out = tmp_path / "wa"
        out.write_text(text1)
        _load(out)
    except FoamKitError:
        pass


# --- unbalanced glued items: refuse, naming file and line ---------------------------------
UNBALANCED = [
    ("open-one-line", "x ( mag(U );\n", None),
    ("open-multi-line", "x\n(\n    mag(U\n    p\n);\n", None),
    ("close-multi-line", "x\n(\n    mag(U))\n    p\n);\n", None),
    ("close-one-line", "x ( mag(U)) );\n", None),
]
UNBAL_PARAMS = [
    pytest.param(
        text,
        cont,
        id=f"{name}-{cont}",
        marks=[_xfail(reason)] if reason else [],
    )
    for name, text, reason in UNBALANCED
    for cont in CONTAINERS
]


@pytest.mark.parametrize(("text", "cont"), UNBAL_PARAMS)
def test_an_unbalanced_glued_item_raises_foamkiterror_naming_file_and_line(
    tmp_path, text, cont
):
    full = _wrap(text, cont)
    path = tmp_path / "unbal"
    path.write_text(HEADER + full)
    span = "|".join(str(HL + 1 + i) for i in range(full.count(NL)))
    with pytest.raises(FoamKitError) as err:
        _load(path)
    assert "unbal" in str(err.value)
    assert re.search(rf"\bline ({span})\b", str(err.value), re.IGNORECASE), err.value


# --- guards: spaced forms read as before ---------------------------------------------------
SPACED = [
    ("number-then-list", "x ( 4 (0 1 2 3) );\n", ["4", "(0 1 2 3)"]),
    ("arc", "edges ( arc 0 1 (0 0 0) );\n", ["arc", "0", "1", "(0 0 0)"]),
    (
        "hex",
        "blocks ( hex (0 1 2 3 4 5 6 7) (10 10 1) simpleGrading (1 1 1) );\n",
        ["hex", "(0 1 2 3 4 5 6 7)", "(10 10 1)", "simpleGrading", "(1 1 1)"],
    ),
    (
        "hex-multi-line",
        "blocks\n(\n    hex (0 1 2 3 4 5 6 7) (10 10 1) simpleGrading (1 1 1)\n);\n",
        ["hex", "(0 1 2 3 4 5 6 7)", "(10 10 1)", "simpleGrading", "(1 1 1)"],
    ),
]
SPACED_PARAMS = [
    pytest.param(text, expected, cont, id=f"{name}-{cont}")
    for name, text, expected in SPACED
    for cont in CONTAINERS
]


@pytest.mark.parametrize(("text", "expected", "cont"), SPACED_PARAMS)
def test_spaced_forms_load_as_before(tmp_path, text, expected, cont):
    path = tmp_path / "glued"
    path.write_text(HEADER + _wrap(text, cont))
    assert _items(_load(path), cont, text.split()[0]) == expected


@pytest.mark.parametrize(("text", "expected", "cont"), SPACED_PARAMS)
def test_spaced_forms_round_trip_and_keep_their_parentheses(
    tmp_path, text, expected, cont
):
    _, second, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    assert text1 == text2
    assert _parens(text1) == _parens(text)
    assert _items(second, cont, text.split()[0]) == expected


# --- guards: T-042 include-in-list behaviour -----------------------------------------------
INCLUDES = [
    ('x ( #include "f" 1 2 );\n', '#include "f"'),
    (
        "x ( #includeFunc patchAverage(name=inlet, p) );\n",
        "#includeFunc patchAverage(name=inlet, p)",
    ),
    ("x\n(\n    #includeFunc mag(U)\n    1\n);\n", "#includeFunc mag(U)"),
]


@pytest.mark.parametrize(("text", "directive"), INCLUDES)
@pytest.mark.parametrize("cont", CONTAINERS)
def test_include_items_in_a_list_stay_one_item_on_one_line(
    tmp_path, text, directive, cont
):
    first, _, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    items = _entry(first, cont).value
    assert sum(isinstance(i, fkt.ofInclude) for i in items) == 1
    assert directive in [" ".join(ln.split()) for ln in text1.splitlines()]
    assert text1 == text2


# --- the real files --------------------------------------------------------------------------
REAL = [
    pytest.param(SAMPLE, id="shockTube-sample"),
    pytest.param(HOTWIRE, id="hotWire-controlDict"),
    pytest.param(CONCENTRIC, id="concentricCylinders-blockMeshDict.orig"),
]


@pytest.mark.parametrize("path", REAL)
def test_real_file_loads(path):
    assert _load(path) is not None


@pytest.mark.parametrize("path", REAL)
def test_real_file_written_text_keeps_every_parenthesis(path):
    assert _parens(_load(path).toString()) == _parens(path.read_text())


# - The shockTube sample also holds `libs ("libsampling.so");`, a one-line list of one quoted
# - item that is written on one line the first time and on three the second time.  That is
# - not a glued parenthesis but the T-045 one-element-list bug, so the sample's own stability
# - test is a separate strict xfail and the fields entry is checked on its own below.
STABLE = [p for p in REAL if p.values[0] is not SAMPLE]


@pytest.mark.parametrize("path", STABLE)
def test_real_file_second_write_equals_the_first(tmp_path, path):
    text1 = _load(path).toString()
    out = tmp_path / path.name
    out.write_text(text1)
    assert _load(out).toString() == text1


@_xfail(
    'T-045: not a glued paren: `libs ("libsampling.so");` is written on one line, then on'
    " three (a one-element one-line list)"
)
def test_sample_second_write_equals_the_first(tmp_path):
    text1 = _load(SAMPLE).toString()
    out = tmp_path / "sample"
    out.write_text(text1)
    assert _load(out).toString() == text1


def _without_libs(text):
    return re.sub(r"libs\s*\([^;]*;", "", text)


def test_sample_write_1_equals_write_2_once_libs_is_set_aside(tmp_path):
    text1 = _load(SAMPLE).toString()
    out = tmp_path / "sample"
    out.write_text(text1)
    text2 = _load(out).toString()
    assert "mag(U)" in text2
    assert _without_libs(text1) == _without_libs(text2)


def test_sample_fields_is_three_items():
    assert [_text(i) for i in _load(SAMPLE).fields.value] == ["T", "mag(U)", "p"]


def test_sample_written_file_keeps_mag_U():
    assert "mag(U)" in _load(SAMPLE).toString()


def test_sample_written_fields_read_back_as_three_items(tmp_path):
    out = tmp_path / "sample"
    out.write_text(_load(SAMPLE).toString())
    assert [_text(i) for i in _load(out).fields.value] == ["T", "mag(U)", "p"]


def test_hotwire_cache_temporary_objects_is_one_item():
    d = _load(HOTWIRE)
    assert [_text(i) for i in d.cacheTemporaryObjects.value] == [
        "div((I*interpolate(phi)))"
    ]


def test_hotwire_written_file_keeps_the_div_word():
    assert "div((I*interpolate(phi)))" in _load(HOTWIRE).toString()


def _point_after_arc_10_11(items):
    for n in range(len(items) - 3):
        if (
            _text(items[n]) == "arc"
            and _text(items[n + 1]) == "10"
            and _text(items[n + 2]) == "11"
        ):
            return items[n + 3]
    return None


POINT = [0.07071067811, -0.07071067811, 1]


def test_concentric_cylinders_item_after_arc_10_11_is_the_point_list():
    point = _point_after_arc_10_11(_load(CONCENTRIC).edges.value)
    assert isinstance(point, fkt.ofList)
    assert [v.value for v in point.value] == POINT


def test_concentric_cylinders_written_arc_10_11_keeps_its_point(tmp_path):
    out = tmp_path / "blockMeshDict.orig"
    out.write_text(_load(CONCENTRIC).toString())
    point = _point_after_arc_10_11(_load(out).edges.value)
    assert isinstance(point, fkt.ofList)
    assert [v.value for v in point.value] == POINT
