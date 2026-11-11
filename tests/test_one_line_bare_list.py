"""A one-line bare list between entries no longer hides the next entry (T-090, issue #124).

Specification tests for docs/tickets/T-090-one-line-bare-list-keeps-next-entry.md.
`a 1;` / `( x y )` / `b 2;` loads today as `a` and `_ = ['x y )', 'b 2']`: `b` is
silently gone.  Every "yes" row of the ticket's table is tested at the top level and
in a sub-dictionary.  The multi-line form (the reference) and the real files stay as
they are (characterization, passing today).
"""

import re

import pytest

from foamkit import FoamKitError
from conftest import FIXTURES, TESTS
from test_directives import HEADER
from test_several_lists_value import _load

RELEASES = TESTS / "releases"
BARE_FILES = [
    RELEASES / "foundation-13.parcelInBox.cloudPositions",
    RELEASES / "foundation-11.filter.parcelInjectionProperties",
    RELEASES / "foundation-11.iglooWithFridges.fridgeA.eMesh",
]

# id -> (body after the header, expected entries as (key, value) in order)
# - a list value is the list of its items' values
XY = ["x", "y"]
ROWS = {
    "between": ("a 1;\n( x y )\nb 2;\n", [("a", 1), ("unnamed_1", XY), ("b", 2)]),
    "numbers": (
        "a 1;\n( 1 2 3 )\nb 2;\n",
        [("a", 1), ("unnamed_1", [1, 2, 3]), ("b", 2)],
    ),
    "list-first": (
        "( x y )\na 1;\nb 2;\n",
        [("unnamed_1", XY), ("a", 1), ("b", 2)],
    ),
    "two-entries-after": (
        "a 1;\n( x y )\nb 2;\nc 3;\n",
        [("a", 1), ("unnamed_1", XY), ("b", 2), ("c", 3)],
    ),
    "trailing-comment": (
        "a 1;\n( x y ) // c\nb 2;\n",
        [("a", 1), ("unnamed_1", XY), ("b", 2)],
    ),
    "all-on-one-line": (
        "a 1; ( x y ) b 2;\n",
        [("a", 1), ("unnamed_1", XY), ("b", 2)],
    ),
    "with-semicolon": (
        "a 1;\n( x y );\nb 2;\n",
        [("a", 1), ("unnamed_1", XY), ("b", 2)],
    ),
}
# - bodies whose list is not on the first line: where `b` sits (for the edit tests)
# - these rows already write the same text twice today (guard, not xfail)
EDITABLE = [k for k, (_, e) in ROWS.items() if any(n == "b" for n, _ in e)]


def _sub(body):
    """The same lines as the content of a sub-dictionary `s`."""
    lines = "".join("    " + ln + "\n" for ln in body.splitlines())
    return "s\n{\n" + lines + "}\n"


def _case(where, row):
    body, entries = ROWS[row]
    if where == "top":
        return HEADER + body, entries
    return HEADER + _sub(body), entries


def _write(tmp_path, text, name="src"):
    path = tmp_path / name
    path.write_bytes(text.encode())
    return path


def _entries(holder, keys):
    out = []
    for k in keys:
        v = getattr(holder, k)
        val = v.value
        if isinstance(val, list):
            val = [i.value for i in val]
        out.append((k, val))
    return out


def _keys(d):
    return [k for k in d.__dict__ if not k.startswith("_")]


def _holder(d, where):
    return d if where == "top" else d.s


WHERE = ["top", "sub"]
CASES = [pytest.param(w, r, id=f"{w}-{r}") for w in WHERE for r in ROWS]
# - the unedited write is already byte-identical today (T-020a); a guard
CASES_BYTES = [pytest.param(w, r, id=f"{w}-{r}") for w in WHERE for r in ROWS]


# --- the model: every entry is loaded ---------------------------------------------------


@pytest.mark.parametrize("where, row", CASES)
def test_every_entry_loads_with_the_list_as_unnamed_1(tmp_path, where, row):
    text, entries = _case(where, row)
    d = _load(_write(tmp_path, text))
    holder = _holder(d, where)
    assert _keys(holder) == [k for k, _ in entries]
    assert _entries(holder, _keys(holder)) == entries


@pytest.mark.parametrize("where, row", CASES)
def test_no_underscore_entry_is_created(tmp_path, where, row):
    text, _ = _case(where, row)
    d = _load(_write(tmp_path, text))
    assert "_" not in _holder(d, where).__dict__


# --- unedited write: byte for byte -------------------------------------------------------


@pytest.mark.parametrize("where, row", CASES_BYTES)
def test_unedited_write_is_byte_identical(tmp_path, where, row):
    text, _ = _case(where, row)
    path = _write(tmp_path, text)
    assert _load(path).toString().encode() == path.read_bytes()


def test_unedited_write_keeps_crlf_line_endings(tmp_path):
    text = (HEADER + ROWS["between"][0]).replace("\n", "\r\n")
    path = _write(tmp_path, text)
    d = _load(path)
    # toString() ends lines with LF; the case writer applies the file's own `_newline`
    assert d._newline == "\r\n"
    assert d.toString().replace("\n", d._newline).encode() == path.read_bytes()


# --- editing the entry after the list ----------------------------------------------------


@pytest.mark.parametrize(
    "where, row",
    [
        pytest.param(
            w,
            r,
            id=f"{w}-{r}",
            marks=(
                pytest.mark.xfail(
                    strict=True,
                    raises=AssertionError,
                    reason="T-083: regenerating a sub-dict drops a comment after a list "
                    "(also for a named list, on main)",
                )
                if (w, r) == ("sub", "trailing-comment")
                else ()
            ),
        )
        for w in WHERE
        for r in EDITABLE
    ],
)
def test_edit_of_b_gives_one_b_and_the_list_as_read(tmp_path, where, row):
    text, _ = _case(where, row)
    d = _load(_write(tmp_path, text))
    holder = _holder(d, where)
    try:
        holder.b.value = 5
    except AttributeError as e:
        raise AssertionError(f"`b` is not an entry: {e}") from e
    out = d.toString()
    assert len(re.findall(r"\bb\s+5;", out)) == 1
    assert not re.search(r"\bb\s+2;", out)
    # the list text is unchanged: the written file differs only in `b 2` -> `b 5`
    # (an edited entry is written padded, as for any entry, so compare ignoring whitespace)
    back = re.sub(r"\bb\s+5;", "b 2;", out)
    assert re.sub(r"\s+", " ", back) == re.sub(r"\s+", " ", text)
    assert "unnamed_" not in out and "_ " not in out


@pytest.mark.parametrize(
    "where, row",
    [pytest.param(w, r, id=f"{w}-{r}") for w in WHERE for r in EDITABLE],
)
def test_edited_write_one_equals_write_two(tmp_path, where, row):
    text, _ = _case(where, row)
    d = _load(_write(tmp_path, text))
    try:
        _holder(d, where).b.value = 5
    except AttributeError as e:
        raise AssertionError(f"`b` is not an entry: {e}") from e
    first = d.toString()
    second = _load(_write(tmp_path, first, "wa")).toString()
    assert second == first


@pytest.mark.parametrize("where, row", [("top", "between"), ("sub", "between")])
def test_regenerated_write_one_equals_write_two(tmp_path, where, row):
    text, _ = _case(where, row)
    d = _load(_write(tmp_path, text))
    first = d.toString(_preserve=False)
    assert "unnamed_" not in first
    assert _load(_write(tmp_path, first, "wa")).toString(_preserve=False) == first


# --- two one-line lists ------------------------------------------------------------------

TWO = {
    "with-semicolon": "a 1;\n( x y );\n( p q );\nb 2;\n",
    "no-semicolon": "( x y )\nb 2;\n( p q )\nc 3;\n",
}


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize(
    "kind",
    list(TWO),
)
def test_two_one_line_lists_are_unnamed_1_and_unnamed_2(tmp_path, where, kind):
    body = TWO[kind]
    text = HEADER + (body if where == "top" else _sub(body))
    holder = _holder(_load(_write(tmp_path, text)), where)
    keys = _keys(holder)
    assert "unnamed_1" in keys and "unnamed_2" in keys
    assert [i.value for i in holder.unnamed_1.value] == XY
    assert [i.value for i in holder.unnamed_2.value] == ["p", "q"]
    assert "b" in keys
    assert ("c" in keys) == ("c 3;" in body)


@pytest.mark.parametrize(
    "where, kind",
    [pytest.param(w, k, id=f"{w}-{k}") for w in WHERE for k in TWO],
)
def test_two_one_line_lists_unedited_write_is_byte_identical(tmp_path, where, kind):
    body = TWO[kind]
    path = _write(tmp_path, HEADER + (body if where == "top" else _sub(body)))
    assert _load(path).toString().encode() == path.read_bytes()


# --- nested one-line list: loads as one list, or a located error -------------------------

NESTED = "a 1;\n((1 2) (3 4))\nb 2;\n"


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize(
    "bad",
    [pytest.param(False, id="not-silent")],
)
def test_nested_one_line_list_loads_with_b_or_raises_a_located_error(
    tmp_path, where, bad
):
    text = HEADER + (NESTED if where == "top" else _sub(NESTED))
    path = _write(tmp_path, text, "nestedList")
    try:
        d = _load(path)
    except FoamKitError as e:
        assert "nestedList" in str(e)
        assert re.search(r"line \d+", str(e))
        return
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"bare {type(e).__name__}: {e}") from e
    holder = _holder(d, where)
    keys = _keys(holder)
    assert "a" in keys and "b" in keys, f"entries missing: {keys}"
    lists = [k for k in keys if k.startswith("unnamed_")]
    assert len(lists) == 1, f"the nested list is missing or split: {keys}"
    inner = getattr(holder, lists[0]).value
    assert len(inner) == 2


# --- unchanged: the multi-line form and the real files ----------------------------------

MULTI = {
    "multi-line": "a 1;\n(\n    x\n    y\n)\nb 2;\n",
    "multi-line-semicolon": "a 1;\n(\n    x\n    y\n);\nb 2;\n",
}


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize("kind", list(MULTI))
def test_multi_line_bare_list_still_loads_every_entry(tmp_path, where, kind):
    body = MULTI[kind]
    text = HEADER + (body if where == "top" else _sub(body))
    path = _write(tmp_path, text)
    holder = _holder(_load(path), where)
    assert _keys(holder) == ["a", "unnamed_1", "b"]
    assert _entries(holder, ["a", "unnamed_1", "b"]) == [
        ("a", 1),
        ("unnamed_1", XY),
        ("b", 2),
    ]
    assert _load(path).toString().encode() == path.read_bytes()


@pytest.mark.parametrize("path", BARE_FILES, ids=lambda p: p.name)
def test_real_bare_list_files_write_unchanged(path):
    assert _load(path).toString().encode() == path.read_bytes()


@pytest.mark.parametrize(
    "path",
    sorted(p for p in (FIXTURES / "pitzDaily").rglob("*") if p.is_file()),
    ids=lambda p: p.name,
)
def test_pitzdaily_fixture_files_write_unchanged(path):
    try:
        d = _load(path)
    except FoamKitError:
        pytest.skip("not a dictionary file FoamKit reads today")
    assert d.toString().encode() == path.read_bytes()


def test_a_list_last_in_the_file_without_semicolon_still_raises_with_file_and_line(
    tmp_path,
):
    # the loud row of the table (guard): must stay loud
    path = _write(tmp_path, HEADER + "a 1;\nb 2;\n( x y )\n", "listLast")
    with pytest.raises(FoamKitError) as exc:
        _load(path)
    assert "listLast" in str(exc.value)
    assert re.search(r"line \d+", str(exc.value))


def test_a_lone_one_line_list_still_raises_with_file_and_line(tmp_path):
    path = _write(tmp_path, HEADER + "( x y )\n", "listAlone")
    with pytest.raises(FoamKitError) as exc:
        _load(path)
    assert "listAlone" in str(exc.value)
    assert re.search(r"line \d+", str(exc.value))


# --- items of a multi-line list that start with '(' are items, not bare lists -----------

ITEM_LISTS = {
    "numbers": "(1 2 3)\n    (4 5 6)",
    "var": "($x 0 1)\n    (1 2 3)",
    "eval": "(#eval{$xcore + $xside} 0 $zmin)\n    (1 2 3)",
}


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize("kind", ITEM_LISTS)
def test_items_of_a_multi_line_list_starting_with_a_paren_load(tmp_path, where, kind):
    block = f"vertices\n(\n    {ITEM_LISTS[kind]}\n);\nb 2;\n"
    if where == "sub":
        lines = "".join("    " + ln + "\n" for ln in block.splitlines())
        block = "s\n{\n" + lines + "}\n"
    path = _write(tmp_path, HEADER + block)
    d = _load(path)
    holder = _holder(d, where)
    assert len(holder.vertices.value) == 2
    if where == "top":
        assert holder.b.value == 2
    assert d.toString().encode() == path.read_bytes()


# --- a bare list inside a dict that is an item of a multi-line list ---------------------

DICT_ITEM_BARE = {
    "one-line": "( x y )",
    "one-line-semicolon": "( x y );",
}


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize("kind", DICT_ITEM_BARE)
def test_bare_list_inside_dict_item_of_a_list_keeps_next_entry(tmp_path, where, kind):
    block = (
        "L\n(\n    {\n        a 1;\n"
        f"        {DICT_ITEM_BARE[kind]}\n"
        "        b 2;\n    }\n);\nc 3;\n"
    )
    if where == "sub":
        lines = "".join("    " + ln + "\n" for ln in block.splitlines())
        block = "s\n{\n" + lines + "}\n"
    path = _write(tmp_path, HEADER + block)
    try:
        d = _load(path)
    except FoamKitError as exc:
        # a loud, located error is acceptable; a hidden entry is not
        assert path.name in str(exc)
        assert re.search(r"line \d+", str(exc))
        return
    holder = _holder(d, where)
    item = holder.L.value[0]
    assert item.a.value == 1
    assert item.b.value == 2
    assert holder.c.value == 3
    assert len(holder.L.value) == 1
    assert d.toString().encode() == path.read_bytes()
