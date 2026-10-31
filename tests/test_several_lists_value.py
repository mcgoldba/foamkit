"""Entry values made of two or more lists (`transform (tensor) (vector);`) (T-052, issue #69).

Specification tests for docs/tickets/T-052-entry-value-of-several-lists.md.  A value of two
or more top-level `( ... )` groups is one entry holding all groups in order, written back
with the same tokens; a shape that is still unsupported raises `FoamKitError` naming the
file and line.  Never a different type (`ofNamedDimension` for a non-dimension), a new
`unnamed_<n>` entry, or a bare IndexError/ValueError/AttributeError/TypeError.

The tests do not pin a representation (nested lists, a new type, ...): they compare the
leaves of the loaded value in order and the tokens of the written text.

Outcome of the ticket's reproduction table on this branch (main 0eb75b1, after T-042,
T-046 and T-048), identical at top level and inside a sub-dict, alone or between entries:

    transform (1 0 0 0 1 0 0 0 1) (0.5 0.45 0.1);          silent corruption, as in the
    transform (1 2 3 4 5 6 7 8 9) (0.5 0.45 0.1);          table: ofNamedDimension, written
                                                           `transform   [0 0 0 1 0 0 0];`
    transform (...) (2.929541 0 0.2);                      FoamKitError "A list closes in
    c (1 2) (3 4);  c (1 2)(3 4);  c (a b) (c d);          the middle of a line (line N
    c (1 2 3) (4 5 6) (7 8 9);                             ...); this list shape is not
    c (1 2) (3 4) / `;` on the next line                   supported yet" (the table says
                                                           bare IndexError/AttributeError:
                                                           T-048 changed that)
    c 2(1 2) 2(3 4);                                       bare ValueError (unchanged)
    c / ( / 1 2 / ) / ( / 3 4 / );                         silent: `c` gets (1 2), a new
                                                           entry `unnamed_1` gets (3 4)
    t ( / 1 2 / ) / (3 4);                                 silent: `(3 4);` is written as
                                                           an orphan statement (also
                                                           `c (1 2)` / `(3 4);`)
    box (0 0 -1) (0.1461 0.292 1);  c ((1 2) (3 4));       OK, round trip (guards)

Found while writing these tests (same dimension-set detection, in the ticket's scope
"must not match a parenthesised value"): a single nine-number list such as
`t (1 2 3 4 5 6 7 8 9);` also becomes `ofNamedDimension` and is written `t   [2 3 4 5 6 7 8];`.
`x (1);` raises a bare TypeError (T-045, not asserted here).

How OpenFOAM reads these (a token stream; the code that looks the keyword up decides the
type): OpenFOAM-14 rigidBodyModel.C does `bodyDict.lookup("transform")` into a
`spatialTransform`, whose `operator>>` is `is >> X.E() >> X.r()` (a tensor of 9 numbers, then
a vector of 3).  `box` is a `boundBox` (two vectors).  `c (1 2) (3 4)` has no fixed type: the
consumer reads as many tokens as it needs.

Real files (byte-exact copies in tests/releases/, outside the golden glob; no file contains
a CR; `git hash-object` of each copy equals the blob in the upstream tree and `cmp` shows no
difference to the raw file):

esi-v2606.floatingObject.dynamicMeshDict    (`transform (1 0 0 0 1 0 0 0 1) (0.5 0.45 0.1);`, line 59)
  ESI OpenFOAM-v2606 (tag OpenFOAM-v2606, commit 481094fdf34f11ed6d0d603ee59a858a0124236d,
  https://gitlab.com/openfoam/core/openfoam):
  tutorials/multiphase/interFoam/RAS/floatingObject/constant/dynamicMeshDict
  blob 1be5c4defad8a5fa0537adc15cd670bb265b4072
foundation-14.DTCHullMoving.dynamicMeshDict (`transform (...) (2.929541 0 0.2);`, line 42)
  Shallow clone of https://github.com/OpenFOAM/OpenFOAM-14 (tag 20261008, commit
  a4867fc914c10ee10c2f6f83c294c3d3160dd573), extracted with `git show HEAD:<path>`:
  tutorials/incompressibleVoF/DTCHullMoving/constant/dynamicMeshDict
  blob 17f6e4ec6de0e23ed8f2d94a26c8286f7d960960
foundation-14.planingHullW3.dynamicMeshDict (tensor over four lines, `)` and the vector `(0.586 0 0.156)` on the last)
  OpenFOAM-14 as above:
  tutorials/incompressibleVoF/planingHullW3/constant/dynamicMeshDict
  blob 10a1bf71bf78dcfecaad25d626b10232ddbb50fd
"""

import re

import pytest

import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import TESTS
from test_directives import HEADER

NL = "\n"
RELEASES = TESTS / "releases"
ESI = RELEASES / "esi-v2606.floatingObject.dynamicMeshDict"
DTC = RELEASES / "foundation-14.DTCHullMoving.dynamicMeshDict"
PLANING = RELEASES / "foundation-14.planingHullW3.dynamicMeshDict"
HL = HEADER.count(NL)
KEY = "c"


def _load(path):
    return fkt.DictFileParser(path).readDictFile()


# --- helpers: representation-independent views of a loaded value -------------------------
def _num(tok):
    try:
        return float(tok)
    except (TypeError, ValueError):
        return tok


def _leaves(obj):
    """The words and numbers of a loaded value, in order, whatever the container type."""
    if isinstance(obj, (list, tuple)):
        return [leaf for item in obj for leaf in _leaves(item)]
    if isinstance(obj, fkt.ofStr):
        return [obj.value]
    value = getattr(obj, "value", None)
    if isinstance(value, (list, tuple)):
        return _leaves(value)
    if value is not None:
        return [_num(value)]
    return [str(obj)]


def _leaf_tokens(entry):
    """`_leaves` with any word that holds raw text (`w (1 2)`) split into its tokens."""
    out = []
    for leaf in _leaves(entry):
        out += (
            [_num(t) for t in re.findall(r"[^\s()]+", leaf)]
            if isinstance(leaf, str)
            else [leaf]
        )
    return out


def _is_list(obj):
    return isinstance(obj, (list, tuple)) or isinstance(
        getattr(obj, "value", None), (list, tuple)
    )


def _groups(obj):
    """Number of list-like nodes below `obj` that hold no list-like node themselves; a
    value that is a single flat list counts as one group."""
    if not _is_list(obj):
        return 0
    items = obj if isinstance(obj, (list, tuple)) else obj.value
    inner = [i for i in items if _is_list(i)]
    return sum(_groups(i) for i in inner) if inner else 1


def _expected_groups(text, key=KEY):
    """Number of top-level `( ... )` groups in the value of `key` in `text`."""
    toks = _tokens(text)
    depth = n = 0
    for t in toks[toks.index(key) + 1 :]:
        n += t == "(" and depth == 0
        depth += (t == "(") - (t == ")")
    return n


def _tokens(text):
    """Tokens of `text`: parentheses, braces, words and numbers (numbers normalised)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return [_num(t) for t in re.findall(r"[(){}]|[^\s(){};]+", text)]


def _body(text):
    """`text` after the banner line that ends the file header."""
    return re.split(
        r"^// \* \* \*[^\n]*\n",
        text,
        maxsplit=1,
        flags=re.MULTILINE,
    )[-1]


def _wrap(text, container):
    if container == "top":
        return text
    return "sub\n{\n" + "".join("    " + ln + NL for ln in text.splitlines()) + "}\n"


def _scope(d, container):
    return d if container == "top" else d.sub


def _names(d, container):
    scope = _scope(d, container)
    # - (entries of an ofDict are attributes: iterating the dict itself yields nothing)
    names = [k for k in vars(scope) if not k.startswith("_")]
    return [n for n in names if type(getattr(scope, n)).__name__ != "ofComment"]


def _expected_leaves(text, key=KEY):
    """Leaves of the value of `key` in `text`: all tokens after the key, no ( ) or ;."""
    toks = [t for t in _tokens(text) if t not in ("(", ")")]
    return toks[toks.index(key) + 1 :]


def _span(text):
    """Regex of the line numbers (1-based file lines) the text occupies."""
    return "|".join(str(HL + 1 + i) for i in range(text.count(NL)))


def _cycle(tmp_path, text):
    """Write, read, write, re-read, write.  Returns (first, second, text1, text2), or None
    when the read raised FoamKitError (after checking that it names the file and a line
    of `text`).  Any other exception is a failure of the test."""
    path = tmp_path / "several"
    path.write_text(HEADER + text)
    try:
        first = _load(path)
    except FoamKitError as err:
        assert "several" in str(err), err
        assert re.search(
            rf"\bline ({_span(text)})\b",
            str(err),
            re.IGNORECASE,
        ), err
        return None
    text1 = first.toString()
    out = tmp_path / "wa"
    out.write_text(text1)
    second = _load(out)
    return first, second, text1, second.toString()


# --- the table -------------------------------------------------------------------------------
# - (id, text of the entry `c`/`transform`/`t`, must load).  `must` rows have to load,
# - round-trip and keep every value (acceptance criteria); the others either do so or raise
# - FoamKitError naming file and line.
ROWS = [
    (
        "transform-identity",
        "transform (1 0 0 0 1 0 0 0 1) (0.5 0.45 0.1);\n",
        "transform",
        True,
    ),
    (
        "transform-1-to-9",
        "transform (1 2 3 4 5 6 7 8 9) (0.5 0.45 0.1);\n",
        "transform",
        True,
    ),
    (
        "transform-dtc",
        "transform (1 0 0 0 1 0 0 0 1) (2.929541 0 0.2);\n",
        "transform",
        True,
    ),
    ("two-numbers", "c (1 2) (3 4);\n", "c", True),
    ("two-words", "c (a b) (c d);\n", "c", True),
    (
        "three-groups",
        "c (1 2 3) (4 5 6) (7 8 9);\n",
        "c",
        True,
    ),
    ("glued-groups", "c (1 2)(3 4);\n", "c", False),
    (
        "counted-groups",
        "c 2(1 2) 2(3 4);\n",
        "c",
        False,
    ),
    (
        "semicolon-on-next-line",
        "c (1 2) (3 4)\n;\n",
        "c",
        False,
    ),
    (
        "multi-line-groups",
        "c\n(\n    1 2\n)\n(\n    3 4\n);\n",
        "c",
        False,
    ),
    (
        "multi-line-groups-compact",
        "c\n(\n1\n2\n)\n(\n3\n4\n);\n",
        "c",
        False,
    ),
    (
        "first-multi-line-second-on-closing",
        "t (\n    1 2\n)\n(3 4);\n",
        "t",
        False,
    ),
    (
        "first-one-line-second-on-next-line",
        "c (1 2)\n(3 4);\n",
        "c",
        False,
    ),
    (
        "planing-tensor-over-four-lines",
        "transform (\n    0.99 0 0.06\n    0 1 0\n    -0.06 0 0.99\n)\n(0.586 0 0.156);\n",
        "transform",
        False,
    ),
    (
        "words-then-groups",
        "c w (1 2) (3 4);\n",
        "c",
        False,
    ),
    (
        "groups-then-word",
        "c (1 2) (3 4) w;\n",
        "c",
        False,
    ),
    (
        "group-word-group",
        "c (1 2) w (3 4);\n",
        "c",
        False,
    ),
    (
        "group-number-group",
        "c (1 2) 5 (3 4);\n",
        "c",
        False,
    ),
    (
        "six-groups",
        "c (1 2) (3 4) (5 6) (7 8) (9 10) (11 12);\n",
        "c",
        False,
    ),
    (
        "quoted-groups",
        'c ("a b") ("c");\n',
        "c",
        False,
    ),
    (
        "hex-like-value",
        "h hex (0 1 2 3 4 5 6 7) (10 10 1) simpleGrading (1 1 1);\n",
        "h",
        False,
    ),
    # - a lone 9-number list is not a dimension set either (same detection)
    (
        "one-list-of-nine-numbers",
        "t (1 2 3 4 5 6 7 8 9);\n",
        "t",
        True,
    ),
    (
        "one-list-of-identity-tensor",
        "t (1 0 0 0 1 0 0 0 1);\n",
        "t",
        True,
    ),
]
CONTAINERS = ["top", "sub"]
# - "alone": the entry is the last one in the file/dictionary; "between": entries around it.
POSITIONS = {
    "alone": ("", ""),
    "between": ("before 1;\n", "after 2;\n"),
}


def _params(must_only=None):
    out = []
    for rid, text, key, must in ROWS:
        if must_only is not None and must is not must_only:
            continue
        for cont in CONTAINERS:
            for pos in POSITIONS:
                out.append(
                    pytest.param(
                        rid,
                        text,
                        key,
                        cont,
                        pos,
                        id=f"{rid}-{cont}-{pos}",
                    )
                )
    return out


def _full(text, cont, pos):
    pre, post = POSITIONS[pos]
    return _wrap(pre + text + post, cont)


def _marked(name, must_only):
    """Parameters for test `name` (`must_only`: only the rows that must load, or not)."""
    return _params(must_only)


ARGS = "rid, text, key, cont, pos"


def _run(tmp_path, text, cont, pos):
    return _cycle(tmp_path, _full(text, cont, pos))


# --- rows that must load, round-trip and keep every value ---------------------------------------
@pytest.mark.parametrize(ARGS, _marked("loads", True))
def test_entry_loads_with_every_group_and_value(tmp_path, rid, text, key, cont, pos):
    result = _run(tmp_path, text, cont, pos)
    assert result is not None, "FoamKitError for a shape the ticket requires to load"
    first = result[0]
    scope = _scope(first, cont)
    entry = getattr(scope, key)
    assert not isinstance(entry, fkt.ofNamedDimension)
    assert _leaf_tokens(entry) == _expected_leaves(text, key)
    expected_names = ["before", key, "after"] if pos == "between" else [key]
    assert _names(first, cont) == expected_names
    assert not any(n.startswith("unnamed") for n in _names(first, cont))


@pytest.mark.parametrize(ARGS, _marked("groups", True))
def test_every_group_is_kept_as_its_own_list(tmp_path, rid, text, key, cont, pos):
    result = _run(tmp_path, text, cont, pos)
    assert result is not None
    for d in result[:2]:
        assert _groups(getattr(_scope(d, cont), key)) == _expected_groups(text, key)


@pytest.mark.parametrize(ARGS, _marked("tokens", True))
def test_written_text_has_the_same_tokens(tmp_path, rid, text, key, cont, pos):
    result = _run(tmp_path, text, cont, pos)
    assert result is not None
    assert _tokens(_body(result[2])) == _tokens(_full(text, cont, pos))


@pytest.mark.parametrize(ARGS, _marked("reread", True))
def test_written_text_reads_back_to_the_same_value(tmp_path, rid, text, key, cont, pos):
    result = _run(tmp_path, text, cont, pos)
    assert result is not None
    second = result[1]
    entry = getattr(_scope(second, cont), key)
    assert not isinstance(entry, fkt.ofNamedDimension)
    assert _leaf_tokens(entry) == _expected_leaves(text, key)


@pytest.mark.parametrize(ARGS, _marked("stable", True))
def test_second_write_equals_the_first(tmp_path, rid, text, key, cont, pos):
    result = _run(tmp_path, text, cont, pos)
    assert result is not None
    assert result[2] == result[3]


@pytest.mark.parametrize(
    ARGS,
    [p for p in _marked("neighbours", True) if p.values[4] == "between"],
)
def test_neighbouring_entries_keep_their_values(tmp_path, rid, text, key, cont, pos):
    result = _run(tmp_path, text, cont, pos)
    assert result is not None
    scope = _scope(result[0], cont)
    assert scope.before.value == 1
    assert scope.after.value == 2


# --- rows that round-trip or raise FoamKitError with file and line --------------------------------
@pytest.mark.parametrize(ARGS, _marked("either", False))
def test_shape_round_trips_or_raises_foamkiterror_with_file_and_line(
    tmp_path, rid, text, key, cont, pos
):
    result = _run(tmp_path, text, cont, pos)
    if result is None:
        return
    first, second, text1, text2 = result
    scope = _scope(first, cont)
    entry = getattr(scope, key)
    assert not isinstance(entry, fkt.ofNamedDimension)
    assert not any(n.startswith("unnamed") for n in _names(first, cont))
    assert _leaf_tokens(entry) == _expected_leaves(text, key)
    assert _tokens(_body(text1)) == _tokens(_full(text, cont, pos))
    assert _leaf_tokens(getattr(_scope(second, cont), key)) == _expected_leaves(
        text, key
    )
    assert text1 == text2


# - Truly broken input: always FoamKitError naming the file and a line.
BROKEN = [
    ("unclosed-second-group", "c (1 2) (3 4;\n"),
    ("extra-closing-paren", "c (1 2)) (3 4);\n"),
    ("missing-semicolon-at-end", "c (1 2) (3 4)\n"),
    (
        "missing-semicolon-before-next-entry",
        "c (1 2) (3 4)\nd 1;\n",
    ),
]


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize(
    ("text",),
    [pytest.param(t, id=i) for i, t in BROKEN],
)
def test_broken_several_lists_raise_foamkiterror_naming_file_and_line(
    tmp_path, text, cont
):
    full = _wrap(text, cont)
    path = tmp_path / "broken"
    path.write_text(HEADER + full)
    with pytest.raises(FoamKitError) as err:
        _load(path)
    assert "broken" in str(err.value)
    assert re.search(
        rf"\bline ({_span(full)})\b",
        str(err.value),
        re.IGNORECASE,
    ), err.value


# --- guards: behave as today ---------------------------------------------------------------------
@pytest.mark.parametrize("cont", CONTAINERS)
def test_box_of_two_vectors_stays_a_bound_box(tmp_path, cont):
    text = "box (0 0 -1) (0.1461 0.292 1);\n"
    first, second, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    for d in (first, second):
        box = _scope(d, cont).box
        assert isinstance(box, fkt.ofBoundBox)
        assert box.value == [
            [0.0, 0.0, -1.0],
            [0.1461, 0.292, 1.0],
        ]
    assert _tokens(_body(text1)) == _tokens(_wrap(text, cont))
    assert text1 == text2


@pytest.mark.parametrize("cont", CONTAINERS)
def test_list_of_two_lists_keeps_its_two_inner_lists(tmp_path, cont):
    first, second, text1, text2 = _cycle(tmp_path, _wrap("c ((1 2) (3 4));\n", cont))
    for d in (first, second):
        items = _scope(d, cont).c.value
        assert [[leaf for leaf in _leaves(i)] for i in items] == [
            [1.0, 2.0],
            [3.0, 4.0],
        ]
        assert all(isinstance(i, fkt.ofList) for i in items)
    assert text1 == text2


HEX = "(0 1 2 3 4 5 6 7) (10 10 1) simpleGrading (1 1 1)"
BLOCKS = [
    ("one-line", f"blocks ( hex {HEX} );\n"),
    ("multi-line", f"blocks\n(\n    hex {HEX}\n);\n"),
    (
        "two-blocks",
        f"blocks\n(\n    hex {HEX}\n    hex {HEX}\n);\n",
    ),
]


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize(
    ("text",),
    [pytest.param(t, id=i) for i, t in BLOCKS],
)
def test_hex_blocks_stay_list_items_and_round_trip(tmp_path, text, cont):
    first, second, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    expected = _expected_leaves(text, "blocks")
    for d in (first, second):
        assert _leaves(_scope(d, cont).blocks) == expected
    assert _tokens(_body(text1)) == _tokens(_wrap(text, cont))
    assert text1 == text2


POSITIONS_TEXT = {
    "vectors": "(\n(0 0 0)\n(1 1 1)\n)\n",
    "one-vector": "(\n(0.05 0.05 0.005)\n)\n",
}


@pytest.mark.parametrize(
    ("text",),
    [pytest.param(t, id=i) for i, t in POSITIONS_TEXT.items()],
)
def test_top_level_positions_list_is_one_unnamed_entry(tmp_path, text):
    first, second, text1, text2 = _cycle(tmp_path, text)
    for d in (first, second):
        assert _names(d, "top") == ["unnamed_1"]
        assert _leaves(d.unnamed_1) == [t for t in _tokens(text) if t not in ("(", ")")]
    assert text1 == text2


def test_top_level_positions_list_after_the_real_cloud_positions_header():
    d = _load(RELEASES / "foundation-13.parcelInBox.cloudPositions")
    assert _leaves(d.unnamed_1) == [0.05, 0.05, 0.005]


DIMENSIONS = [
    (
        "set-alone",
        "d [0 2 -1 0 0 0 0];\n",
        fkt.ofNamedDimension,
        [0, 2, -1, 0, 0, 0, 0],
    ),
    (
        "set-with-name",
        "dimensions [0 2 -1 0 0 0 0];\n",
        fkt.ofNamedDimension,
        [0, 2, -1, 0, 0, 0, 0],
    ),
    (
        "dimensioned-scalar",
        "nu [0 2 -1 0 0 0 0] 1e-5;\n",
        fkt.ofDimensionedScalar,
        None,
    ),
]


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize(
    ("text", "type_", "dims"),
    [p[1:] for p in DIMENSIONS],
    ids=[p[0] for p in DIMENSIONS],
)
def test_a_real_dimension_set_is_still_a_dimension(tmp_path, text, type_, dims, cont):
    first, second, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    name = text.split()[0]
    for d in (first, second):
        entry = getattr(_scope(d, cont), name)
        assert isinstance(entry, type_)
        if dims is not None:
            assert list(entry.dimensions) == dims
    assert "[0 2 -1 0 0 0 0]" in text1
    assert text1 == text2
    if type_ is fkt.ofDimensionedScalar:
        assert getattr(_scope(first, cont), name).value == pytest.approx(1e-5)


ONE_ELEMENT = [
    ("one-number", "x ( 1 );\n", [1.0]),
    (
        "inner-one-element",
        "x ( a (b) );\n",
        ["a", "b"],
    ),
    (
        "number-then-one-element",
        "x ( 1(5) );\n",
        [1.0, 5.0],
    ),
]


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize(
    ("text", "leaves"),
    [p[1:] for p in ONE_ELEMENT],
    ids=[p[0] for p in ONE_ELEMENT],
)
def test_one_element_lists_behave_as_before(tmp_path, text, leaves, cont):
    first, second, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    for d in (first, second):
        assert _leaves(_scope(d, cont).x) == leaves
    assert text1 == text2


GLUED = [
    (
        "glued-word",
        "x ( p mag(U) );\n",
        ["p", "mag(U)"],
    ),
    (
        "counted-list",
        "x ( 4(0 1 2 3) 4(4 5 6 7) );\n",
        None,
    ),
    (
        "div-word",
        "x ( div((I*interpolate(phi))) );\n",
        ["div((I*interpolate(phi)))"],
    ),
]


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize(
    ("text", "leaves"),
    [p[1:] for p in GLUED],
    ids=[p[0] for p in GLUED],
)
def test_t048_glued_items_stay_as_they_are(tmp_path, text, leaves, cont):
    first, _, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    if leaves is not None:
        assert _leaves(_scope(first, cont).x) == leaves
    assert _tokens(_body(text1)) == _tokens(_wrap(text, cont))
    assert text1 == text2


# --- the real files --------------------------------------------------------------------------------
def _transform_groups(text):
    """The two groups of every `transform (...) (...);` statement in `text`, as floats."""
    pattern = r"transform\s*\(([^()]*)\)\s*\(([^()]*)\)\s*;"
    return [
        (
            [float(t) for t in a.split()],
            [float(t) for t in b.split()],
        )
        for a, b in re.findall(pattern, text)
    ]


REAL = {
    "esi": (
        ESI,
        (
            [1, 0, 0, 0, 1, 0, 0, 0, 1],
            [0.5, 0.45, 0.1],
        ),
    ),
    "dtc": (
        DTC,
        (
            [1, 0, 0, 0, 1, 0, 0, 0, 1],
            [2.929541, 0, 0.2],
        ),
    ),
    "planing": (
        PLANING,
        (
            [
                0.9981507467,
                0,
                0.06078722637,
                0,
                1,
                0,
                -0.06078722637,
                0,
                0.9981507467,
            ],
            [0.586, 0, 0.156],
        ),
    ),
}
REAL_PARAMS = [pytest.param(*v, id=k) for k, v in REAL.items()]


def _real_params(test):
    return [pytest.param(*v, id=k) for k, v in REAL.items()]


@pytest.mark.parametrize(("path", "groups"), _real_params("loads"))
def test_real_file_loads(path, groups):
    assert _load(path) is not None


@pytest.mark.parametrize(
    ("path", "groups"),
    _real_params("written-transform"),
)
def test_real_file_written_transform_has_the_tensor_and_the_vector(path, groups):
    written = _load(path).toString()
    assert _transform_groups(written) == [groups]
    assert _transform_groups(path.read_text()) == [groups]


@pytest.mark.parametrize(("path", "groups"), _real_params("no-orphan"))
def test_real_file_written_has_no_orphan_statement_or_dimension(path, groups):
    written = _load(path).toString()
    assert "[0 0 0 1 0 0 0]" not in written
    # - (one line: `^\s*` would also match a split list `L` / `(` / ... / `);`, which is fine)
    assert not re.search(r"^[ \t]*\([^()\r\n]*\)[ \t]*;", written, re.MULTILINE)


@pytest.mark.parametrize(("path", "groups"), _real_params("stable"))
def test_real_file_second_write_has_the_same_tokens_as_the_first(
    tmp_path, path, groups
):
    """Token stream, not text: the files hold one-element lists (`patches (hull);`), written
    on one line the first time and on three lines the second time (T-045, not T-052)."""
    text1 = _load(path).toString()
    out = tmp_path / path.name
    out.write_text(text1)
    assert _tokens(_body(_load(out).toString())) == _tokens(_body(text1))


@pytest.mark.parametrize("name", ["esi", "dtc", "planing"])
@pytest.mark.xfail(
    strict=True,
    reason="T-045: `patches (hull);` is a one-element list, written on one line, then on three",
)
def test_real_file_second_write_equals_the_first_text(tmp_path, name):
    path = REAL[name][0]
    text1 = _load(path).toString()
    out = tmp_path / path.name
    out.write_text(text1)
    assert _load(out).toString() == text1


@pytest.mark.parametrize(("path", "groups"), _real_params("tokens"))
def test_real_file_written_keeps_the_numbers_of_the_source(path, groups):
    src = [t for t in _tokens(_body(path.read_text())) if isinstance(t, float)]
    out = [t for t in _tokens(_body(_load(path).toString())) if isinstance(t, float)]
    assert out == src


def test_real_files_pinned_in_brace_scan():
    """The three files are in REAL_OUTCOMES (tests/test_brace_scan.py); T-052 updates it."""
    text = (TESTS / "test_brace_scan.py").read_text()
    for path, _ in REAL.values():
        assert f'"{path.name}"' in text
