"""A list reads back as exactly its items after every write/read cycle (T-037).

Specification tests for docs/tickets/T-037-one-line-list-empty-item.md (issue #49).

Bug: `_parseList` tests `line.endswith(');')` on a line that still has its trailing
newline, so the `;` is parsed as an extra empty `ofStr` item.  Two consequences, both
checked here:
- `x ( 1 );` read -> write -> read has the items `[1, '']`;
- the same happens on the FIRST read whenever the closing `);` is not on the key's
  line, i.e. for every multi-line list (`x\\n(\\n 1\\n 2\\n);` reads as `[1, 2, '']`)
  and for a one-line list with a trailing comment or without spaces (`x (1 2);`).
  The coordinator's brief called the multi-line form "working today"; it works only
  in the sense that the real items are right and one spurious empty item is added.

Only the parsed items are asserted (count and values), never the layout (T-020).

Expectations marked `xfail(strict=True, reason="T-037: ...")` fail today for exactly
that reason (the only wrong thing is the extra `''` item) and must pass after the fix.

Not covered, found while probing: `x(1);` (no space before the parenthesis) raises
`AttributeError: 'ofWord' object has no attribute '_name'` on read; unrelated to
T-037, so it is not tested here.  No sibling `endswith(')` on a raw line exists in
`_parseList`; the nearby checks (`lineList[0] == ');'`, `lineList[0].strip()[-1]`,
`lineList[1][-1]`) work on tokens, and no input was found that triggers them.
"""

import pytest

import foamkit.types as fkt
from conftest import TESTS
from test_directives import HEADER
from test_golden import DICT_FILES, _id

NL = "\n"
RELEASES = TESTS / "releases"
CYCLES = [0, 1, 2, 3]

# --- helpers ------------------------------------------------------------------


def _node(d, path):
    for name in path:
        d = getattr(d, name)
    return d


def _items(d, path):
    return [getattr(i, "value", i) for i in _node(d, path).value]


def _cycle(tmp_path, raw, n):
    """Parse `raw` (bytes); then write and re-read `n` times.  Return the last object."""
    src = tmp_path / "wa"
    src.write_bytes(raw)
    d = fkt.DictFileParser(src).readDictFile()
    for k in range(n):
        out = tmp_path / ("wb", "wc", "wd")[k]
        out.write_text(d.toString())
        d = fkt.DictFileParser(out).readDictFile()
    return d


def _raw(body, eol=NL):
    return (HEADER + body).replace(NL, eol).encode()


def _lists(obj, prefix=""):
    """`{path: [item values]}` of every list below `obj`."""
    out = {}
    for k, v in vars(obj).items():
        if k.startswith("_"):
            continue
        if "List" in type(v).__name__ and isinstance(v.value, list):
            out[prefix + k] = [getattr(i, "value", i) for i in v.value]
        elif isinstance(v, dict):
            out.update(_lists(v, f"{prefix}{k}/"))
    return out


# --- one-line forms -------------------------------------------------------------
# (id, source line, expected items, first read already wrong today)
ONE_LINE = [
    ("int", "x ( 1 );", [1], False),
    ("ints", "x ( 1 2 3 );", [1, 2, 3], False),
    ("strings", 'x ( "a" "b" );', ['"a"', '"b"'], False),
    ("paren-string", 'x ( ")" );', ['")"'], False),
    ("brace-string", 'x ( "}" );', ['"}"'], False),
    ("empty", "x ();", [], False),
    ("empty-with-space", "x ( );", [], False),
    ("libs", 'libs ( "libfoo.so" );', ['"libfoo.so"'], False),
    ("fields", "fields ( p U );", ["p", "U"], False),
    ("tight", "x (1 2);", [1, 2], False),
    ("trailing-comment", "x ( 1 ); // c", [1], True),
    ("trailing-block-comment", "x ( 1 ); /* c */", [1], True),
]


def _key(line):
    return line.split()[0]


def _param(form, cycles=CYCLES):
    """Parameters (form, n) with a strict xfail where the read is wrong today."""
    out = []
    for i, line, items, bad_first in form:
        for n in cycles:
            out.append(pytest.param(i, line, items, n, id=f"{i}-{n}", marks=[]))
    return out


@pytest.mark.parametrize("ident, line, items, n", _param(ONE_LINE))
def test_one_line_list_reads_back_with_exactly_its_items(
    tmp_path, ident, line, items, n
):
    raw = _raw(line + NL + NL + "y 2;" + NL)
    d = _cycle(tmp_path, raw, n)
    assert _items(d, (_key(line),)) == items
    assert d.y.value == 2


@pytest.mark.parametrize("ident, line, items, n", _param(ONE_LINE, [1, 3]))
def test_one_line_list_in_a_subdict_reads_back_with_exactly_its_items(
    tmp_path, ident, line, items, n
):
    raw = _raw("d" + NL + "{" + NL + "    " + line + NL + "    y 2;" + NL + "}" + NL)
    d = _cycle(tmp_path, raw, n)
    assert _items(d, ("d", _key(line))) == items
    assert d.d.y.value == 2


@pytest.mark.parametrize("ident, line, items, n", _param(ONE_LINE, [1, 3]))
def test_one_line_list_in_a_nested_subdict_reads_back_with_exactly_its_items(
    tmp_path, ident, line, items, n
):
    raw = _raw(
        "d"
        + NL
        + "{"
        + NL
        + "    e"
        + NL
        + "    {"
        + NL
        + "        "
        + line
        + NL
        + "    }"
        + NL
        + "}"
        + NL
    )
    d = _cycle(tmp_path, raw, n)
    assert _items(d, ("d", "e", _key(line))) == items


# --- other end-of-line situations -------------------------------------------------


@pytest.mark.parametrize("n", [pytest.param(0), pytest.param(1), pytest.param(3)])
def test_crlf_input_reads_back_with_exactly_its_items(tmp_path, n):
    raw = _raw("x ( 1 2 );" + NL + "y 2;" + NL, "\r\n")
    d = _cycle(tmp_path, raw, n)
    assert _items(d, ("x",)) == [1, 2]


@pytest.mark.parametrize("n", [pytest.param(0), pytest.param(1), pytest.param(3)])
def test_list_on_the_last_line_without_a_newline_reads_back_exactly(tmp_path, n):
    raw = (HEADER + "y 2;" + NL + "x ( 1 2 );").encode()
    d = _cycle(tmp_path, raw, n)
    assert _items(d, ("x",)) == [1, 2]


@pytest.mark.parametrize("n", [pytest.param(0), pytest.param(1), pytest.param(3)])
def test_list_on_the_last_line_with_crlf_and_no_newline(tmp_path, n):
    raw = (HEADER.replace(NL, "\r\n") + "y 2;\r\nx ( 1 2 );").encode()
    d = _cycle(tmp_path, raw, n)
    assert _items(d, ("x",)) == [1, 2]


def test_two_one_line_lists_after_two_cycles_keep_only_their_items(tmp_path):
    raw = _raw("a ( 1 );" + NL + "b ( 2 3 );" + NL + "c ();" + NL)
    d = _cycle(tmp_path, raw, 2)
    assert _lists(d) == {"a": [1], "b": [2, 3], "c": []}


# --- multi-line forms (items right today, plus the one spurious empty item) -----------
MULTI = [
    ("multi", "x" + NL + "(" + NL + "    1" + NL + "    2" + NL + ");", [1, 2]),
    (
        "multi-indented-close",
        "x" + NL + "(" + NL + "    1" + NL + "    2" + NL + "    );",
        [1, 2],
    ),
    (
        "multi-close-on-item-line",
        "x" + NL + "(" + NL + "    1" + NL + "    2 );",
        [1, 2],
    ),
    (
        "multi-strings",
        "x" + NL + "(" + NL + '    "a )"' + NL + '    "b"' + NL + ");",
        ['"a )"', '"b"'],
    ),
    ("multi-empty", "x" + NL + "(" + NL + ");", []),
]


@pytest.mark.parametrize("ident, text, items", MULTI, ids=[m[0] for m in MULTI])
def test_multi_line_list_keeps_its_real_items_in_order(tmp_path, ident, text, items):
    """Characterization (passes today): the real items are right, in order."""
    d = _cycle(tmp_path, _raw(text + NL + NL + "y 2;" + NL), 0)
    real = [v for v in _items(d, ("x",)) if v != ""]
    assert real == items
    assert d.y.value == 2


@pytest.mark.parametrize("ident, text, items", MULTI, ids=[m[0] for m in MULTI])
@pytest.mark.parametrize(
    "n",
    [pytest.param(0), pytest.param(1), pytest.param(3)],
)
def test_multi_line_list_reads_back_with_exactly_its_items(
    tmp_path, ident, text, items, n
):
    d = _cycle(tmp_path, _raw(text + NL + NL + "y 2;" + NL), n)
    assert _items(d, ("x",)) == items


@pytest.mark.parametrize("ident, text, items", MULTI, ids=[m[0] for m in MULTI])
@pytest.mark.parametrize("n", [pytest.param(0), pytest.param(2)])
def test_multi_line_list_in_a_subdict_reads_back_with_exactly_its_items(
    tmp_path, ident, text, items, n
):
    body = "d" + NL + "{" + NL + text + NL + "    y 2;" + NL + "}" + NL
    d = _cycle(tmp_path, _raw(body), n)
    assert _items(d, ("d", "x")) == items


@pytest.mark.parametrize("n", [pytest.param(0), pytest.param(2)])
def test_multi_line_list_with_crlf_reads_back_with_exactly_its_items(tmp_path, n):
    text = "x" + NL + "(" + NL + "    1" + NL + "    2" + NL + ");" + NL + "y 2;" + NL
    d = _cycle(tmp_path, _raw(text, "\r\n"), n)
    assert _items(d, ("x",)) == [1, 2]


# --- the spurious item is the only difference (and it does not grow) -----------------


def test_the_extra_item_does_not_grow_with_more_cycles(tmp_path):
    """Characterization (passes today): at most ONE empty item, however many cycles."""
    raw = _raw("x ( 1 2 );" + NL + "y 2;" + NL)
    counts = [_items(_cycle(tmp_path, raw, n), ("x",)).count("") for n in (1, 2, 3)]
    assert max(counts) <= 1


# --- real files ----------------------------------------------------------------------
# - Outcome pinned before T-037; files that fail to load are not part of this test.
REAL_LOADING = [
    "esi-v2606.bendJunction.blockMeshDict",
    "esi-v2606.externalCoupled",
    "foundation-11.controlDict",
    "foundation-14.cylinder.momentumTransport",
    "foundation-14.pitzDaily.momentumTransport",
    "foundation-14.roomHeating.fvModels",
]


def _reread(tmp_path, path):
    first = fkt.DictFileParser(path).readDictFile()
    out = tmp_path / "wb"
    out.write_text(first.toString())
    return first, fkt.DictFileParser(out).readDictFile()


@pytest.mark.parametrize("name", REAL_LOADING)
def test_release_file_lists_are_the_same_after_a_write_and_re_read(tmp_path, name):
    first, second = _reread(tmp_path, RELEASES / name)
    assert _lists(second) == _lists(first)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            n,
            marks=[],
        )
        for n in REAL_LOADING
    ],
)
def test_release_file_lists_have_no_empty_items(tmp_path, name):
    first, second = _reread(tmp_path, RELEASES / name)
    for d in (first, second):
        for path, items in _lists(d).items():
            assert "" not in items, path


# - Same properties on every fixture the golden tests use (pitzDaily case, headers,
# - templates).  Only the files that contain lists matter; the rest pass trivially.
FIXTURE_FILES = [p for p in DICT_FILES if p.is_file()]


# - Fixtures whose lists are wrong today (the files behind the T-037 golden changes).
FIXTURE_EMPTY_ITEMS = {
    "headers/foam-extend-4.1.controlDict",
    "headers/foam-extend-5.0.controlDict",
    "pitzDaily/system/blockMeshDict",
    "pitzDaily/system/controlDict",
    "pitzDaily/system/setFieldsDict",
}
FIXTURE_CHANGE_ON_WRITE = {"pitzDaily/system/controlDict"}


def _fixture_params(xfail_ids):
    return [pytest.param(p, id=_id(p), marks=[]) for p in FIXTURE_FILES]


@pytest.mark.parametrize("path", _fixture_params(FIXTURE_CHANGE_ON_WRITE))
def test_fixture_lists_are_the_same_after_a_write_and_re_read(tmp_path, path):
    first, second = _reread(tmp_path, path)
    assert _lists(second) == _lists(first)


@pytest.mark.parametrize("path", _fixture_params(FIXTURE_EMPTY_ITEMS))
def test_fixture_lists_have_no_empty_items(tmp_path, path):
    first, second = _reread(tmp_path, path)
    for d in (first, second):
        for key, items in _lists(d).items():
            assert "" not in items, key
