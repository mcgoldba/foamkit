"""A bare list (`cloudPositions`, `*.eMesh`) is written without an invented `unnamed_1` (T-084, issue #112).

Specification tests for docs/tickets/T-084-bare-top-level-list-keeps-no-keyword.md.  A
file (or a sub-dictionary) holding a list with no keyword is read as the entry
`unnamed_<n>` (read side unchanged: `d.unnamed_1` keeps working), but the writer must
not print that internal key as a keyword, and must keep the `;` or the lack of one that
the source had.

Re-check on main 401bb6c (after T-020a, T-014, T-086), `toString()` unedited, then
`toString(_preserve=False)` (regenerated) and an edited write (append an item):

    shape                       unedited          regenerated / edited
    real cloudPositions         as read           `unnamed_1` and `;` added
    parcelInjectionProperties   as read           `unnamed_1` added, `;` kept
    two bare lists              as read           both keywords added, both `;` added
                                                  (editing one leaves the other as read)
    bare list between entries   as read           `unnamed_1` added
    bare list in a sub-dict     as read           `unnamed_1` added (+ blank lines, T-083)
    bare `{ a 1; }`             as read           `unnamed_1` added
    counted `2` / `(...)`       as read           key `t_2`; `;` added (T-080, pinned)
    `((1 2 3) (4 5 6))`         FoamKitError "Could not find end of statement" (guard)

Write 1 == write 2 holds for every shape today (the keyword is added once, then read
back as a named list).  The cache round trip (`init`, `save`, `load`, `write`) keeps
`unnamed_1`, writes an unedited file as read and an edited one with the keyword.

Other findings of the re-check (not fixed by T-084's keyword rule, reported):
`a 1;` / `( x y )` / `b 2;` (list on ONE line, between entries) loads as the single entry
`a` and silently loses `b`; a top-level `print;` raises a bare `AttributeError`.

Real files (byte-exact copies in tests/releases/, LF; `git hash-object` of each copy equals
the blob in the upstream tree):

foundation-13.parcelInBox.cloudPositions  (see tests/test_glued_parens_in_list.py for its source)
foundation-11.filter.parcelInjectionProperties   (one bare list ending in `);`)
foundation-11.iglooWithFridges.fridgeA.eMesh     (two bare lists, `// Points`, `// Edges`)
  Shallow clone of https://github.com/OpenFOAM/OpenFOAM-11, commit
  9cbf94f3339dd49286633b303c4155fd10ea8200, extracted with `git show HEAD:<path>`:
  tutorials/multicomponentFluid/filter/constant/parcelInjectionProperties
  blob a77bf6c033894ad5454ea07966fa1ddd89d4c186
  tutorials/fluid/iglooWithFridges/constant/geometry/fridgeA.eMesh
  blob 0e8e1ed91e77041028a831bcdceafd46403043f0
"""

import re

import pytest

import foamkit.functions as pf
import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import FIXTURES, TESTS
from test_directives import HEADER
from test_several_lists_value import _load

RELEASES = TESTS / "releases"
CLOUD = RELEASES / "foundation-13.parcelInBox.cloudPositions"
PARCEL = RELEASES / "foundation-11.filter.parcelInjectionProperties"
EMESH = RELEASES / "foundation-11.iglooWithFridges.fridgeA.eMesh"
MARKER = 987654


_FLOAT_XFAIL = pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="T-032 (number text, not T-084): the regenerated text writes 0.10 as 0.1 "
    "(and -0.10 as -0.1); the bare list itself is written correctly",
)


def _keys(d):
    return [k for k in d.__dict__ if not k.startswith("_")]


def _norm(text):
    """The text after the FoamFile block, without comments and white space."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    text = text.split("}", 1)[1]
    return re.sub(r"\s+", "", text)


# - id -> (body after the header, attribute path of the entry to edit, edit kind)
SHAPES = {
    "parcel-injection": (
        "(\n    (0 0 0) 1\n    (1 1 1) 2\n);\n",
        ("unnamed_1",),
        "append",
    ),
    "between-entries": ("a 1;\n(\n    x\n    y\n)\nb 2;\n", ("unnamed_1",), "append"),
    "between-entries-semicolon": (
        "a 1;\n(\n    x\n    y\n);\nb 2;\n",
        ("unnamed_1",),
        "append",
    ),
    "in-sub-dict": (
        "s\n{\n    a 1;\n    (\n        1\n        2\n    )\n    b 2;\n}\n",
        ("s", "unnamed_1"),
        "append",
    ),
    "two-edit-first": (
        "// Points\n(\n(0 0 0)\n(1 1 1)\n)\n\n// Edges\n(\n(0 1)\n)\n",
        ("unnamed_1",),
        "append",
    ),
    "two-edit-second": (
        "// Points\n(\n(0 0 0)\n(1 1 1)\n)\n\n// Edges\n(\n(0 1)\n)\n",
        ("unnamed_2",),
        "append",
    ),
    "bare-dict": ("{ a 1; }\n", ("unnamed_1", "a"), "set"),
}
REAL = "real-cloud-positions"
# - Real files: id -> (file in tests/releases/, attribute path of the entry to edit)
REAL_FILES = {
    REAL: (CLOUD, ("unnamed_1",)),
    "real-parcel-injection-properties": (PARCEL, ("unnamed_1",)),
    "real-emesh-edit-points": (EMESH, ("unnamed_1",)),
    "real-emesh-edit-edges": (EMESH, ("unnamed_2",)),
}
IDS = [*REAL_FILES, *SHAPES]
# - the parcel file regenerates 0.10 as 0.1 (T-032), which these two tests compare
IDS_FLOAT_XFAIL = [
    pytest.param(s, marks=_FLOAT_XFAIL)
    if s == "real-parcel-injection-properties"
    else s
    for s in IDS
]


def _body(shape):
    if shape in REAL_FILES:
        return REAL_FILES[shape][0].read_text()
    return HEADER + SHAPES[shape][0]


def _edit_path(shape):
    return REAL_FILES[shape][1] if shape in REAL_FILES else SHAPES[shape][1]


def _is_set(shape):
    return shape in SHAPES and SHAPES[shape][2] == "set"


def _write_source(tmp_path, shape, name="src"):
    path = tmp_path / name
    path.write_text(_body(shape))
    return path


def _edit(d, shape):
    """Edit the list (append an item) or the dict (set `a`)."""
    *parents, last = _edit_path(shape)
    holder = d
    for p in parents:
        holder = getattr(holder, p)
    if _is_set(shape):
        setattr(holder, last, MARKER)
    else:
        getattr(holder, last).value.append(fkt.ofInt(value=MARKER))


def _undo(text, shape):
    """Remove the edit again, so that the text can be compared with the source."""
    back = "1" if _is_set(shape) else ""
    return text.replace(str(MARKER), back)


# --- unedited writes (T-020a guard) ------------------------------------------------------


@pytest.mark.parametrize("shape", IDS)
def test_unedited_write_is_byte_identical(tmp_path, shape):
    path = _write_source(tmp_path, shape)
    assert _load(path).toString() == path.read_text()


# --- the keyword is not invented on the regenerate path ----------------------------------


@pytest.mark.parametrize("shape", IDS)
def test_regenerated_write_has_no_unnamed_keyword(tmp_path, shape):
    path = _write_source(tmp_path, shape)
    assert "unnamed_" not in _load(path).toString(_preserve=False)


@pytest.mark.parametrize("shape", IDS_FLOAT_XFAIL)
def test_regenerated_write_keeps_the_sources_tokens_and_semicolons(tmp_path, shape):
    path = _write_source(tmp_path, shape)
    text = _load(path).toString(_preserve=False)
    assert _norm(text) == _norm(path.read_text())


@pytest.mark.parametrize("shape", IDS)
def test_regenerated_write_one_equals_write_two(tmp_path, shape):
    path = _write_source(tmp_path, shape)
    text1 = _load(path).toString(_preserve=False)
    out = tmp_path / "wa"
    out.write_text(text1)
    assert _load(out).toString(_preserve=False) == text1


@pytest.mark.parametrize("shape", IDS)
def test_regenerated_write_reads_back_with_the_same_entries(tmp_path, shape):
    path = _write_source(tmp_path, shape)
    first = _load(path)
    out = tmp_path / "wa"
    out.write_text(first.toString(_preserve=False))
    second = _load(out)
    assert _keys(second) == _keys(first)


# --- an edited entry ---------------------------------------------------------------------


@pytest.mark.parametrize("shape", IDS)
def test_edited_write_has_no_unnamed_keyword(tmp_path, shape):
    d = _load(_write_source(tmp_path, shape))
    _edit(d, shape)
    assert "unnamed_" not in d.toString()


@pytest.mark.parametrize("shape", IDS_FLOAT_XFAIL)
def test_edited_write_differs_from_the_source_only_by_the_edit(tmp_path, shape):
    path = _write_source(tmp_path, shape)
    d = _load(path)
    _edit(d, shape)
    text = d.toString()
    assert str(MARKER) in text
    assert _norm(_undo(text, shape)) == _norm(path.read_text())


@pytest.mark.parametrize("shape", IDS)
def test_edited_item_is_in_the_written_file(tmp_path, shape):
    d = _load(_write_source(tmp_path, shape))
    _edit(d, shape)
    out = tmp_path / "wa"
    out.write_text(d.toString())
    holder = _load(out)
    for p in _edit_path(shape)[:-1]:
        holder = getattr(holder, p)
    entry = getattr(holder, _edit_path(shape)[-1])
    assert str(MARKER) in repr(entry)


@pytest.mark.parametrize("shape", IDS)
def test_edited_write_one_equals_write_two(tmp_path, shape):
    d = _load(_write_source(tmp_path, shape))
    _edit(d, shape)
    text1 = d.toString()
    out = tmp_path / "wa"
    out.write_text(text1)
    text2 = _load(out).toString()
    # the keyword-free text must be re-read as the same bare list, so it is stable
    assert "unnamed_" not in text1
    assert text2 == text1


# --- the read side is unchanged ----------------------------------------------------------


def test_read_side_real_file_is_reachable_as_unnamed_1(tmp_path):
    d = _load(_write_source(tmp_path, REAL))
    assert _keys(d) == ["unnamed_1"]
    assert len(d.unnamed_1.value) == 1


def test_read_side_two_lists_are_unnamed_1_and_unnamed_2(tmp_path):
    d = _load(_write_source(tmp_path, "two-edit-first"))
    assert len(d.unnamed_1.value) == 2
    assert len(d.unnamed_2.value) == 1


def test_read_side_bare_list_in_sub_dict_is_s_unnamed_1(tmp_path):
    d = _load(_write_source(tmp_path, "in-sub-dict"))
    assert [i.value for i in d.s.unnamed_1.value] == [1, 2]


def test_read_side_bare_list_keeps_its_place_between_entries(tmp_path):
    d = _load(_write_source(tmp_path, "between-entries"))
    assert _keys(d) == ["a", "unnamed_1", "b"]


# --- the .params cache round trip --------------------------------------------------------


def _make_case(tmp_path, shape):
    case = tmp_path / "case"
    (case / "constant").mkdir(parents=True)
    (case / "system").mkdir()
    (case / "system" / "controlDict").write_text(
        (FIXTURES / "pitzDaily" / "system" / "controlDict").read_text()
    )
    target = case / "constant" / "cloudPositions"
    target.write_text(_body(shape))
    return case, target


CASE_SHAPES = [
    REAL,
    "real-parcel-injection-properties",
    "real-emesh-edit-points",
    "parcel-injection",
    "two-edit-first",
    "between-entries",
]


@pytest.mark.parametrize("shape", CASE_SHAPES)
def test_cache_round_trip_keeps_unnamed_entries_and_unedited_write(tmp_path, shape):
    case, target = _make_case(tmp_path, shape)
    pf.init(path=case).save(path=case)
    loaded = pf.load(path=case)
    entries = [
        k for k in loaded.constant.cloudPositions.__dict__ if k.startswith("unnamed_")
    ]
    assert entries[0] == "unnamed_1"
    before = target.read_text()
    loaded.write()
    assert target.read_text() == before


@pytest.mark.parametrize("shape", CASE_SHAPES)
def test_cache_round_trip_edited_write_has_no_keyword(tmp_path, shape):
    case, target = _make_case(tmp_path, shape)
    pf.init(path=case).save(path=case)
    loaded = pf.load(path=case)
    loaded.constant.cloudPositions.unnamed_1.value.append(fkt.ofInt(value=MARKER))
    loaded.write()
    text = target.read_text()
    assert str(MARKER) in text
    assert "unnamed_" not in text


def test_edited_item_reaches_disk_through_case_write(tmp_path):
    case, target = _make_case(tmp_path, REAL)
    pf.init(path=case).save(path=case)
    loaded = pf.load(path=case)
    loaded.constant.cloudPositions.unnamed_1.value.append(fkt.ofInt(value=MARKER))
    loaded.write()
    assert str(MARKER) in target.read_text()


# --- files written by FoamKit before the fix (ticket risk: they are repaired) ------------


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("unnamed_1\n(\n    (0 0 0)\n);\n", id="with-semicolon"),
    ],
)
def test_a_file_written_with_the_keyword_is_regenerated_without_it(tmp_path, text):
    path = tmp_path / "old"
    path.write_text(HEADER + text)
    assert "unnamed_" not in _load(path).toString(_preserve=False)


# --- pinned today: counted bare lists belong to T-080 ------------------------------------

COUNTED = "2\n(\n(1 2 3)\n(4 5 6)\n)\n"


def test_counted_bare_list_is_read_as_the_key_t_2(tmp_path):
    # T-080 owns counted lists: today the count is read as a keyword.
    path = tmp_path / "counted"
    path.write_text(HEADER + COUNTED)
    assert [k for k in _load(path).__dict__ if not k.startswith("_")] == ["t_2"]


def test_counted_bare_list_regenerated_adds_a_semicolon(tmp_path):
    # Pinned for T-080; T-084 must not change it.
    path = tmp_path / "counted"
    path.write_text(HEADER + COUNTED)
    text = _load(path).toString(_preserve=False)
    assert text.endswith("2\n(\n    (1 2 3)\n    (4 5 6)\n);\n\n")
    assert "unnamed_" not in text


# --- T-079 keyword-only entries are untouched --------------------------------------------


def test_keyword_only_entry_in_a_sub_dict_is_written_as_a_keyword(tmp_path):
    path = tmp_path / "kw"
    path.write_text(HEADER + "s\n{\n    print;\n    a 1;\n}\n")
    text = _load(path).toString(_preserve=False)
    assert "    print;\n" in text
    assert "unnamed_" not in text


# --- loud errors -------------------------------------------------------------------------


def test_one_line_nested_bare_list_raises_foamkiterror_with_file_and_line(tmp_path):
    path = tmp_path / "oneLine"
    path.write_text(HEADER + "((1 2 3) (4 5 6))\n")
    with pytest.raises(FoamKitError) as exc:
        _load(path)
    msg = str(exc.value)
    assert "oneLine" in msg
    assert re.search(r"line \d+", msg)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "a 1;\n( x y )\nb 2;\n",
            marks=pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="T-090 (not T-084): a one-line bare list silently "
                "swallows the next entry",
            ),
            id="one-line-list-between-entries",
        ),
    ],
)
def test_one_line_bare_list_either_loads_every_entry_or_raises(tmp_path, text):
    # Found by the T-084 re-check: `b` is lost without any message.  Loud error
    # or full load are both acceptable; silent loss is not.
    path = tmp_path / "oneLineList"
    path.write_text(HEADER + text)
    try:
        d = _load(path)
    except FoamKitError as e:
        assert "oneLineList" in str(e)
        return
    assert "b" in d.__dict__, "entry `b` was silently dropped"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="T-079 (#106, not T-084): a top-level keyword-only entry raises a bare AttributeError "
    "('ofWord' object has no attribute '_name') instead of loading or FoamKitError",
)
def test_top_level_keyword_only_entry_never_raises_a_bare_exception(tmp_path):
    path = tmp_path / "kwTop"
    path.write_text(HEADER + "a 1;\nprint;\nb 2;\n")
    try:
        _load(path)
    except FoamKitError:
        return
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"bare {type(e).__name__}: {e}") from e


# --- the closing ';' follows the source, also through the cache (T-084 review) ---------


@pytest.mark.parametrize(
    "shape",
    [
        "between-entries",  # no ';' after the bare list
        "two-edit-first",  # no ';'
        "real-emesh-edit-points",  # no ';'
        REAL,  # ';' after the bare list
        "parcel-injection",  # ';'
    ],
)
def test_cache_round_trip_edited_write_keeps_the_sources_semicolon(tmp_path, shape):
    """`init` -> `save` -> `load` -> edit -> `write`: the list ends as its source did."""
    case, target = _make_case(tmp_path, shape)
    pf.init(path=case).save(path=case)
    loaded = pf.load(path=case)
    loaded.constant.cloudPositions.unnamed_1.value.append(fkt.ofInt(value=MARKER))
    loaded.write()
    assert _norm(_undo(target.read_text(), shape)) == _norm(_body(shape))


def test_a_named_list_always_gets_its_semicolon(tmp_path):
    """Only a generated (bare) key can lose the ';'; a keyword list never does."""
    path = tmp_path / "f"
    path.write_text(HEADER + "l (1 2 3);\n")
    d = _load(path)
    d.l._semicolon = False
    assert _norm(d.toString(_preserve=False)) == "l(123);"


def test_a_hand_written_generated_looking_key_is_written_bare(tmp_path):
    """
    Known limitation, not wanted behaviour: a key the user wrote as `unnamed_<n>`
    is indistinguishable from one the reader generated, so regenerating the
    entry writes the list without its keyword, and nothing warns.  It repairs
    files that older FoamKit versions wrote with the keyword
    (`unnamed_1 (...);`).  A reader-side marker for generated keys would remove
    the ambiguity (T-092).
    """
    path = tmp_path / "f"
    path.write_text(HEADER + "a 1;\nunnamed_3 (1 2 3);\nb 2;\n")
    text = _load(path).toString(_preserve=False)
    assert "unnamed_3" not in text
    assert _norm(text) == "a1;(123);b2;"


@pytest.mark.parametrize(
    "shape, flag, delta",  # delta: the change in the number of `);` written
    [
        ("between-entries", True, 1),
        ("parcel-injection", False, -1),
        ("in-sub-dict", True, 1),
    ],
)
def test_changing_the_semicolon_flag_is_an_edit(tmp_path, shape, flag, delta):
    """The edit check sees the flag through the entry text, with no name of its own."""
    d = _load(_write_source(tmp_path, shape))
    assert d.toString() == _body(shape)
    entry = d
    for name in _edit_path(shape):
        entry = getattr(entry, name)
    entry._semicolon = flag
    text = d.toString()
    assert text != _body(shape)
    assert text.count(");") == _body(shape).count(");") + delta


def test_the_flag_on_a_named_list_never_drops_its_semicolon(tmp_path):
    """The flag is an edit (the entry is regenerated), but a keyword list keeps its ';'."""
    path = tmp_path / "f"
    path.write_text(HEADER + "l (1 2 3);\n")
    d = _load(path)
    d.l._semicolon = False
    assert _norm(d.toString()) == "l(123);"
