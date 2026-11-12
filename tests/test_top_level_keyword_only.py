"""A keyword-only entry (`print;`, `box ;`) at the top level loads (T-079, issue #106).

Specification tests for docs/tickets/T-079-top-level-keyword-only-entries.md (option A:
the same representation as in a sub-dictionary today: an `ofWord` holding the keyword,
stored under an `unnamed_<n>` key, written `keyword;`).  Every input row of the ticket's
table is tested at the top level and in a sub-dictionary, alone, between entries and as the
last entry.  The top level crashes today with a bare `AttributeError`
(`'ofWord' object has no attribute '_name'`); the loader helper reports that as an
`AssertionError`, so every failing test fails with `AssertionError`.  The sub-dictionary
rows are characterization (passing today) and pinned.

Differences to the ticket's table (reproduced there on f8590d8; checked on main 647cb84):
- the sub-dictionary rows now also write byte for byte what was read (`x ;` stays `x ;`,
  T-020), not just `x;`; write 1 == write 2 still holds;
- the one-line block `s { x; y; }` is now refused with `FoamKitError` naming file and line
  (T-084); the ticket lists only the multi-line form as loading; both are pinned;
- `print;` / `print;` gives `unnamed_1` and `unnamed_2` in a sub-dictionary today.

Real file (byte-exact copy in tests/releases/, outside the golden glob; `git hash-object`
of the copy equals the blob in the upstream tree):

foundation-14.filter.createZonesDict   (`print;`, line 52)
  https://github.com/OpenFOAM/OpenFOAM-14, master at 64cfdf5481e156d52872271e913b273260375e84,
  tutorials/multicomponentFluid/filter/system/createZonesDict
  blob 0689d70162c341b327795f1f578316846a8a0b2a
"""

import pytest

from foamkit import FoamKitError
from conftest import TESTS
from test_directives import HEADER
from test_several_lists_value import _load

REAL = TESTS / "releases" / "foundation-14.filter.createZonesDict"

# id -> (body after the header, expected entries as (key, type name, value) in order)
W = "ofWord"
INT = "ofInt"
ROWS = {
    "box-space": ("box ;\n", [("unnamed_1", W, "box")]),
    "box": ("box;\n", [("unnamed_1", W, "box")]),
    "x-space": ("x ;\n", [("unnamed_1", W, "x")]),
    "x-two-spaces": ("x  ;\n", [("unnamed_1", W, "x")]),
    "x-comment": ("x; // c\n", [("unnamed_1", W, "x")]),
    "between": (
        "a 1;\nx ;\nb 2;\n",
        [("a", INT, 1), ("unnamed_1", W, "x"), ("b", INT, 2)],
    ),
    "last": ("a 1;\nx;\n", [("a", INT, 1), ("unnamed_1", W, "x")]),
    "first": ("print;\nb 2;\n", [("unnamed_1", W, "print"), ("b", INT, 2)]),
    "blank-lines": (
        "\nprint;\n\nb 2;\n",
        [("unnamed_1", W, "print"), ("b", INT, 2)],
    ),
    "duplicates": (
        "print;\nprint;\n",
        [("unnamed_1", W, "print"), ("unnamed_2", W, "print")],
    ),
    "two-kinds": (
        "x;\na 1;\ny;\n",
        [("unnamed_1", W, "x"), ("a", INT, 1), ("unnamed_2", W, "y")],
    ),
}
# bodies with a `b` entry, for the edit tests
EDITABLE = [k for k, (_, e) in ROWS.items() if any(n == "b" for n, _, _ in e)]
WHERE = ["top", "sub"]


def _sub(body):
    """The same lines as the content of a multi-line sub-dictionary `s`."""
    lines = "".join("    " + ln + "\n" if ln else "\n" for ln in body.splitlines())
    return "s\n{\n" + lines + "}\n"


def _text(where, row):
    body = ROWS[row][0]
    return HEADER + (body if where == "top" else _sub(body))


def _write(tmp_path, text, name="src"):
    path = tmp_path / name
    path.write_bytes(text.encode())
    return path


def _read(path):
    """Load; a bare exception (the bug) is reported as an AssertionError."""
    try:
        return _load(path)
    except FoamKitError:
        raise
    except Exception as e:
        raise AssertionError(f"bare {type(e).__name__}: {e}") from e


def _holder(d, where):
    return d if where == "top" else d.s


def _keys(d):
    return [k for k in d.__dict__ if not k.startswith("_")]


def _entries(holder):
    return [
        (k, type(getattr(holder, k)).__name__, getattr(holder, k).value)
        for k in _keys(holder)
    ]


def _words(row):
    return [e[2] for e in ROWS[row][1] if e[1] == W]


def _cases(rows=ROWS):
    return [pytest.param(w, r, id=f"{w}-{r}") for w in WHERE for r in rows]


# --- the model: same type and key scheme as in a sub-dictionary ----------------------------


@pytest.mark.parametrize("where, row", _cases())
def test_entries_load_as_words_in_order_under_unnamed_keys(tmp_path, where, row):
    d = _read(_write(tmp_path, _text(where, row)))
    assert _entries(_holder(d, where)) == ROWS[row][1]


@pytest.mark.parametrize("where, row", _cases())
def test_keyword_only_entry_is_not_named_after_its_keyword(tmp_path, where, row):
    holder = _holder(_read(_write(tmp_path, _text(where, row))), where)
    assert [w for w in _words(row) if w in holder.__dict__] == []


# --- write: keyword followed by `;`, write 1 == write 2 ------------------------------------


@pytest.mark.parametrize("where, row", _cases())
def test_unedited_write_is_byte_identical(tmp_path, where, row):
    path = _write(tmp_path, _text(where, row))
    assert _read(path).toString().encode() == path.read_bytes()


@pytest.mark.parametrize("where, row", _cases())
def test_write_one_equals_write_two(tmp_path, where, row):
    first = _read(_write(tmp_path, _text(where, row))).toString()
    assert _read(_write(tmp_path, first, "wa")).toString() == first


@pytest.mark.parametrize("where, row", _cases())
def test_every_keyword_is_written_with_its_semicolon(tmp_path, where, row):
    out = _read(_write(tmp_path, _text(where, row))).toString()
    lines = [ln.strip().split("//")[0].strip() for ln in out.splitlines()]
    for word in set(_words(row)):
        expected = _words(row).count(word)
        found = sum(ln.replace(" ", "") == f"{word};" for ln in lines)
        assert found == expected


def test_top_level_crlf_file_loads_and_keeps_its_line_endings(tmp_path):
    text = (HEADER + ROWS["between"][0]).replace("\n", "\r\n")
    path = _write(tmp_path, text)
    d = _read(path)
    assert d._newline == "\r\n"
    assert d.toString().replace("\n", d._newline).encode() == path.read_bytes()


# --- editing a neighbour keeps the keyword-only entry --------------------------------------


@pytest.mark.parametrize("where, row", _cases(EDITABLE))
def test_edit_of_b_keeps_the_keyword_only_entries(tmp_path, where, row):
    d = _read(_write(tmp_path, _text(where, row)))
    _holder(d, where).b.value = 5
    out = d.toString()
    lines = [ln.strip().replace(" ", "") for ln in out.splitlines()]
    assert lines.count("b5;") == 1 and "b2;" not in lines
    assert lines.count("print;") == _words(row).count("print")
    assert _entries(_holder(_read(_write(tmp_path, out, "wa")), where))[-1][2] == 5
    assert _read(_write(tmp_path, out, "wb")).toString() == out


# --- pinned rows that already behave as the ticket wants -----------------------------------


@pytest.mark.parametrize(
    "body, key, type_name, value",
    [
        ("box ( );\n", "box", "ofSplitList", []),
        ('x "";\n', "x", "ofStr", '""'),
    ],
    ids=["empty-list", "empty-string"],
)
@pytest.mark.parametrize("where", WHERE)
def test_empty_value_entries_stay_named_and_round_trip(
    tmp_path, where, body, key, type_name, value
):
    path = _write(tmp_path, HEADER + (body if where == "top" else _sub(body)))
    d = _read(path)
    entry = getattr(_holder(d, where), key)
    assert type(entry).__name__ == type_name
    assert entry.value == value
    assert d.toString().encode() == path.read_bytes()


def test_multi_line_sub_dict_of_keyword_only_entries_loads(tmp_path):
    path = _write(tmp_path, HEADER + "s\n{\n    x;\n    y;\n}\n")
    d = _read(path)
    assert _entries(d.s) == [("unnamed_1", W, "x"), ("unnamed_2", W, "y")]
    assert d.toString().encode() == path.read_bytes()


def test_one_line_sub_dict_of_keyword_only_entries_names_file_and_line(tmp_path):
    # T-084: refused loudly, nothing dropped; pinned
    path = _write(tmp_path, HEADER + "s { x; y; }\n")
    with pytest.raises(FoamKitError) as info:
        _load(path)
    msg = str(info.value)
    assert str(path) in msg and f"Line {HEADER.count(chr(10)) + 1}" in msg


# --- no bare exception ----------------------------------------------------------------------


@pytest.mark.parametrize("where, row", _cases())
def test_row_either_loads_or_raises_foamkiterror_naming_file_and_line(
    tmp_path, where, row
):
    path = _write(tmp_path, _text(where, row))
    try:
        _load(path)
    except FoamKitError as e:
        assert str(path) in str(e) and "Line " in str(e)
    except Exception as e:
        raise AssertionError(f"bare {type(e).__name__}: {e}") from e


# --- the Foundation 14 file -----------------------------------------------------------------


def test_real_file_copy_is_the_upstream_bytes():
    data = REAL.read_bytes()
    assert b"\r" not in data and b"\nprint;\n" in data and len(data) == 1142


def test_real_file_loads_with_print_as_the_last_entry():
    d = _read(REAL)
    assert _keys(d) == [
        "filter",
        "leftFluid",
        "rightFluid",
        "cycLeft",
        "cycRight",
        "unnamed_1",
    ]
    assert d.unnamed_1.value == "print"


def test_real_file_unedited_write_is_byte_identical():
    assert _read(REAL).toString().encode() == REAL.read_bytes()
