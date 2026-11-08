"""Tokens with `_` (`1_0`) are words, written back as read (T-075, issue #102).

Specification tests for docs/tickets/T-075-underscore-tokens-are-words.md.  `1_0` is not an
OpenFOAM number, so any token containing `_` loads as a word wherever it appears and an
unedited write gives back the source text.  Python's `int()`/`float()` accept `_` between
digits, which is how they were silently read as numbers and written without the `_`.

Two kinds of row:

- STRICT rows (scalars, list items, list-group items, `box`): the `_` token loads as `ofStr`
  (items of a list or group are `ofStr`, the other items keep their number type), the written
  tokens equal the source tokens, write 1 == write 2, and a `box` with a `_` token is a plain
  `ofListGroups`, not an `ofBoundBox`.
- FLEX rows (`uniform`, dimensioned values, dimension sets, a counted-list length): either the
  whole entry loads as an `ofStr` written as read, or the load raises `FoamKitError` naming the
  file and a line of the entry.  Never a bare exception, never a dropped or changed token.

Controls (pass today, must keep passing): `1e5`/`1E5`, `nan`/`inf`/`-Infinity`, plain numbers,
a normal box, and the tokens that are already words.

Call sites of `int(`/`float(` in foamkit/types/__init__.py on f8590d8
(grep -nE '\\b(int|float)\\(' foamkit/types/__init__.py); R = reads a file token, -- = not:

    485            float(itemName.rstrip('.orig'))          --  (time directory name)
    1335, 1364     ofInt/ofFloat(value=...) constructors    --  (Python input, out of scope)
    1888, 1935     list helper conversions                  --  (already-parsed numbers)
    3558, 3617-3618, 3766/3772, 3875, 3898   monitor/log file readers   --  (not entries)
    5243, 5245     counted-list length `int(lineList[0])`   R
    6113-6121      _parseValue: int/float/isclose           R
    6146, 6151     _parseValue (str branch): int, float     R
    6169           _parseValue `( ... )` tensor branch      R
    6228, 6232     _parseValue: float then int              R
    6937, 6945     dimension set `int(d)`                   R
    6966           dimensioned value `float(v)`             R
    7152           `int(value.strip('[];'))`                R (check in _parseDimensionedType)
    (list items, list groups and `uniform` go through _parseValue.)
"""

import pytest

import foamkit.types as fkt
from test_several_lists_value import (
    CONTAINERS,
    _body,
    _cycle,
    _wrap,
)
from test_bound_box import _entry, _raw

NUMBERS = (fkt.ofInt, fkt.ofFloat)


def _leaves(obj):
    """Leaf objects of a loaded value, in order (groups of a list-groups value included)."""
    if isinstance(obj, (list, tuple)):
        return [leaf for item in obj for leaf in _leaves(item)]
    if isinstance(obj, fkt.ofListGroups):
        return _leaves(obj.groups)
    value = getattr(obj, "value", None)
    if isinstance(value, (list, tuple)):
        return _leaves(value)
    return [obj]


def _items(text, key):
    """Source tokens of the value of `key` without brackets."""
    toks = _raw(text)
    return [t for t in toks[toks.index(key) + 1 :] if t not in ("(", ")")]


def _rows(rows):
    return [
        pytest.param(
            text,
            key,
            cont,
            id=f"{rid}-{cont}",
        )
        for rid, text, key in rows
        for cont in CONTAINERS
    ]


# - (id, text, key).  The `_` token has to be a word.
SCALAR_ROWS = [
    ("int", "x 1_0;\n", "x"),
    ("plus-int", "x +1_0;\n", "x"),
    ("float-thousands", "x 1_000.5;\n", "x"),
    ("float-fraction", "x 1.5_0;\n", "x"),
    ("neg-exponent", "x -2_5e1_0;\n", "x"),
    ("exponent", "x 1_0e5;\n", "x"),
]
LIST_ROWS = [
    ("one-line", "l (1_0 2 3_0.5);\n", "l"),
    ("vector", "v (1_0 0 0);\n", "v"),
    ("multi-line", "x\n(\n1_0\n2\n);\n", "x"),
    ("groups", "c (1_0 2) (3 4);\n", "c"),
    ("box", "box (1_0 0 0) (1 1 1);\n", "box"),
]
# - Entries that load as an ofStr, or raise FoamKitError naming file and line.
FLEX_ROWS = [
    ("uniform-scalar", "v uniform 1_0;\n", "v"),
    ("uniform-vector", "v uniform (1_0 0 0);\n", "v"),
    ("dimensioned-value", "nu [0 2 -1 0 0 0 0] 1_0;\n", "nu"),
    ("dimension-set", "nu [0 2 -1_0 0 0 0 0] 1;\n", "nu"),
    ("counted-list", "t\n1_0\n(\na\nb\n);\n", "t"),
]
# - Word spellings that already load as an ofStr and are written as read.
WORD_ROWS = [
    ("double-underscore", "x 1__0;\n", "x"),
    ("leading", "x _10;\n", "x"),
    ("trailing", "x 10_;\n", "x"),
    ("before-exponent", "x 1_e5;\n", "x"),
    ("hex", "x 0x10;\n", "x"),
    ("two-words", "x 1_0 2;\n", "x"),
    ("glued-count", "t 1_0(a b);\n", "t"),
    ("doubled-nu", "nu nu [0 2 -1 0 0 0 0] 1_0;\n", "nu"),
    (
        "nonuniform",
        "internalField nonuniform List<scalar> 3(1_0 2 3);\n",
        "internalField",
    ),
]


def _cycle_ok(tmp_path, text, cont):
    result = _cycle(tmp_path, _wrap(text, cont))
    assert result is not None, "unexpected FoamKitError"
    return result


def _assert_written_as_read(text, cont, text1, text2):
    assert _raw(_body(text1)) == _raw(_wrap(text, cont))
    assert text1 == text2


@pytest.mark.parametrize(("text", "key", "cont"), _rows(SCALAR_ROWS))
def test_scalar_with_underscore_is_a_word(tmp_path, text, key, cont):
    first, second, _, _ = _cycle_ok(tmp_path, text, cont)
    for d in (first, second):
        entry = _entry(d, key, cont)
        assert isinstance(entry, fkt.ofStr)
        assert entry.value == _items(text, key)[0]


@pytest.mark.parametrize(
    ("text", "key", "cont"),
    _rows(SCALAR_ROWS + LIST_ROWS[:3])
    # - (T-071 already keeps the number text of list groups and boxes)
    + _rows(LIST_ROWS[3:]),
)
def test_value_with_underscore_is_written_as_read(tmp_path, text, key, cont):
    _, _, text1, text2 = _cycle_ok(tmp_path, text, cont)
    _assert_written_as_read(text, cont, text1, text2)


@pytest.mark.parametrize(("text", "key", "cont"), _rows(LIST_ROWS))
def test_list_item_with_underscore_is_a_word_and_others_stay_numbers(
    tmp_path, text, key, cont
):
    first, second, _, _ = _cycle_ok(tmp_path, text, cont)
    toks = _items(text, key)
    for d in (first, second):
        leaves = _leaves(_entry(d, key, cont))
        assert len(leaves) == len(toks)
        for leaf, tok in zip(leaves, toks):
            if "_" in tok:
                assert isinstance(leaf, fkt.ofStr), tok
                assert leaf.value == tok
            else:
                assert isinstance(leaf, NUMBERS), tok


@pytest.mark.parametrize("cont", CONTAINERS)
def test_box_with_underscore_is_a_plain_list_groups_on_both_reads(tmp_path, cont):
    first, second, _, _ = _cycle_ok(tmp_path, "box (1_0 0 0) (1 1 1);\n", cont)
    for d in (first, second):
        entry = _entry(d, "box", cont)
        assert type(entry) is fkt.ofListGroups
        assert len(entry.groups) == 2
        assert all(len(g.value) == 3 for g in entry.groups)


@pytest.mark.parametrize(("text", "key", "cont"), _rows(FLEX_ROWS))
def test_flex_entry_with_underscore_is_a_word_or_a_located_error(
    tmp_path, text, key, cont
):
    result = _cycle(tmp_path, _wrap(text, cont))
    if result is None:
        # - (_cycle checked that the FoamKitError names the file and a line)
        return
    first, second, text1, text2 = result
    for d in (first, second):
        entry = _entry(d, key, cont)
        assert isinstance(entry, fkt.ofStr)
    _assert_written_as_read(text, cont, text1, text2)


# --- controls: pass today ---------------------------------------------------------------------
@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize(
    ("text", "cls"),
    [
        ("x 1e5;\n", fkt.ofFloat),
        ("x 1E5;\n", fkt.ofFloat),
        ("x -1.5;\n", fkt.ofFloat),
        ("x 10;\n", fkt.ofInt),
        ("x nan;\n", fkt.ofFloat),
        ("x inf;\n", fkt.ofFloat),
        ("x -Infinity;\n", fkt.ofFloat),
    ],
)
def test_plain_numbers_stay_numbers(tmp_path, text, cls, cont):
    first, second, _, _ = _cycle_ok(tmp_path, text, cont)
    for d in (first, second):
        assert isinstance(_entry(d, "x", cont), cls)


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize("text", ["x 1e5;\n", "x 1E5;\n"])
def test_exponent_numbers_load_as_100000(tmp_path, text, cont):
    first, _, _, _ = _cycle_ok(tmp_path, text, cont)
    assert _entry(first, "x", cont).value == 100000.0


@pytest.mark.parametrize(("text", "key", "cont"), _rows(WORD_ROWS))
def test_existing_words_stay_words_written_as_read(tmp_path, text, key, cont):
    first, second, text1, text2 = _cycle_ok(tmp_path, text, cont)
    for d in (first, second):
        assert isinstance(_entry(d, key, cont), fkt.ofStr)
    _assert_written_as_read(text, cont, text1, text2)


@pytest.mark.parametrize("cont", CONTAINERS)
def test_normal_box_stays_a_bound_box(tmp_path, cont):
    text = "box (0 0 0) (1 1 1);\n"
    first, second, text1, text2 = _cycle_ok(tmp_path, text, cont)
    for d in (first, second):
        assert type(_entry(d, "box", cont)) is fkt.ofBoundBox
    _assert_written_as_read(text, cont, text1, text2)


@pytest.mark.parametrize("cont", CONTAINERS)
def test_list_without_underscore_keeps_number_items(tmp_path, cont):
    first, _, _, _ = _cycle_ok(tmp_path, "l (1 2 3.5);\n", cont)
    leaves = _leaves(_entry(first, "l", cont))
    assert [type(i) for i in leaves] == [fkt.ofInt, fkt.ofInt, fkt.ofFloat]
