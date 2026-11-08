"""`box (...) (...)` entries: one type, number text kept (T-071, issue #92).

Specification tests for docs/tickets/T-071-boundbox-subclass-of-listgroups.md.  An entry of
exactly two groups of exactly three numbers is an `ofBoundBox`, whatever the spelling of the
numbers (`8e-3`, `1e6`, `-1.5E+2`) or the line breaks; `ofBoundBox` is a subclass of
`ofListGroups`; an unedited entry is written with the source number text; `.value` is a
deprecated float view of the groups; a bad assignment raises `FoamKitError`.

Real files (byte-exact copies in tests/releases/, outside the golden glob; `git hash-object`
of each copy equals the blob in the upstream tree):

foundation-11.capillaryRise.setFieldsDict   (`box (0 0 -1) (1 8e-3 1);`, line 26)
foundation-11.pipeCyclic.topoSetDict        (`box (-1e6 -1e6 -1e6)(1e6 -0.15 0.3);`, line 24)
  Shallow clone of https://github.com/OpenFOAM/OpenFOAM-11, commit
  9cbf94f3339dd49286633b303c4155fd10ea8200, extracted with `git show HEAD:<path>`:
  tutorials/incompressibleVoF/capillaryRise/system/setFieldsDict
  blob c055df24dddb43a3a9447aa360aa655409ee4946
  tutorials/incompressibleFluid/pipeCyclic/system/topoSetDict
  blob 330940f007e37d9d04ba06f9a7b892c55c6f4de7

"""

import re
import shutil
import warnings

import pytest

import foamkit.functions as pf
import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import FIXTURES, TESTS
from test_directives import HEADER
from test_several_lists_value import (
    CONTAINERS,
    _body,
    _cycle,
    _load,
    _scope,
    _tokens,
    _wrap,
)

NL = "\n"
RELEASES = TESTS / "releases"
CAPILLARY = RELEASES / "foundation-11.capillaryRise.setFieldsDict"
PIPE = RELEASES / "foundation-11.pipeCyclic.topoSetDict"

# - (id, text, key).  Two groups of three numbers: an ofBoundBox however they are spelled.
BOX_ROWS = [
    ("plain", "box (0 0 0) (1 2 3);\n", "box"),
    ("other-key", "p1 (0 0 0) (1 1 1);\n", "p1"),
    ("exponent-8e-3", "box (0 0 -1) (1 8e-3 1);\n", "box"),
    ("exponent-1e6", "box (-1e6 -40 -1e6) (1300 40 1e6);\n", "box"),
    ("glued-parens", "box (-1e6 -1e6 -1e6)(1e6 -0.15 0.3);\n", "box"),
    ("upper-E-plus", "box (-1.5E+2 0 0) (1 1 1);\n", "box"),
    ("three-lines", "box\n(0 0 0)\n(1 2 3);\n", "box"),
    ("two-lines", "box (0 0 0)\n(1 2 3);\n", "box"),
]
# - Any other shape stays a plain ofListGroups.
NON_BOX_ROWS = [
    ("two-by-two", "c (1 2) (3 4);\n", "c"),
    ("three-groups", "c (1 2 3) (4 5 6) (7 8 9);\n", "c"),
    ("word-in-group", "c (a b c) (1 2 3);\n", "c"),
    ("three-and-four", "c (1 2 3) (4 5 6 7);\n", "c"),
    (
        "tensor-and-vector",
        "transform (1 0 0 0 1 0 0 0 1) (0.5 0.45 0.1);\n",
        "transform",
    ),
]
INF_ROW = ("inf", "box (-inf 0 0) (inf 1 1);\n", "box")


def _p(test, rows):
    """`pytest.param` for each row and container (`test` names the caller)."""
    return [
        pytest.param(text, key, cont, id=f"{rid}-{cont}")
        for rid, text, key in rows
        for cont in CONTAINERS
    ]


def _raw(text):
    """Tokens of `text` as source text: parentheses, braces and words, no `;`, no number
    normalisation (`8e-3` stays `8e-3`)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return re.findall(r"[(){}]|[^\s(){};]+", text)


def _entry(d, key, cont):
    return getattr(_scope(d, cont), key)


def _dep(fn):
    """Call `fn()`; return (result, the DeprecationWarnings it emitted)."""
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        result = fn()
    return result, [w for w in rec if issubclass(w.category, DeprecationWarning)]


def _quiet_value(entry):
    """`entry.value` with the deprecation warning ignored (the float view)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return entry.value


def _read_quiet(tmp_path, text, cont, name="box"):
    """Load `text` (wrapped for `cont`); no DeprecationWarning is allowed while loading."""
    path = tmp_path / name
    path.write_text(HEADER + _wrap(text, cont))
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        return _load(path)


# --- type ----------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "key", "cont"),
    _p("test_box_is_a_bound_box_and_a_list_groups_on_both_reads", BOX_ROWS),
)
def test_box_is_a_bound_box_and_a_list_groups_on_both_reads(tmp_path, text, key, cont):
    first, second, _, _ = _cycle(tmp_path, _wrap(text, cont))
    for d in (first, second):
        entry = _entry(d, key, cont)
        assert isinstance(entry, fkt.ofBoundBox)
        assert isinstance(entry, fkt.ofListGroups)


@pytest.mark.parametrize(
    ("text", "key", "cont"),
    _p("test_type_does_not_depend_on_spelling_or_line_breaks", BOX_ROWS),
)
def test_type_does_not_depend_on_spelling_or_line_breaks(tmp_path, text, key, cont):
    first, second, _, _ = _cycle(tmp_path, _wrap(text, cont))
    assert type(_entry(first, key, cont)) is fkt.ofBoundBox
    assert type(_entry(second, key, cont)) is fkt.ofBoundBox


@pytest.mark.parametrize(
    ("text", "key", "cont"),
    _p("test_non_box_stays_a_plain_list_groups", NON_BOX_ROWS),
)
def test_non_box_stays_a_plain_list_groups(tmp_path, text, key, cont):
    first, second, _, _ = _cycle(tmp_path, _wrap(text, cont))
    for d in (first, second):
        assert type(_entry(d, key, cont)) is fkt.ofListGroups


@pytest.mark.parametrize("cont", CONTAINERS)
def test_inf_box_has_one_type_on_both_reads_and_round_trips(tmp_path, cont):
    """`inf` is a number by the shared list-value rule (ofFloat), so the box rule may
    accept it; main reads it as ofListGroups.  Whatever type results, it is the same on
    both reads and the text round-trips."""
    _, text, key = INF_ROW
    first, second, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    kinds = {type(_entry(d, key, cont)) for d in (first, second)}
    assert len(kinds) == 1
    assert kinds <= {fkt.ofBoundBox, fkt.ofListGroups}
    assert isinstance(_entry(first, key, cont), fkt.ofListGroups)
    assert _raw(_body(text1)) == _raw(_wrap(text, cont))
    assert text1 == text2


# --- number text and stability --------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "key", "cont"),
    _p(
        "test_unedited_box_is_written_with_the_source_number_text",
        BOX_ROWS + NON_BOX_ROWS + [INF_ROW],
    ),
)
def test_unedited_box_is_written_with_the_source_number_text(tmp_path, text, key, cont):
    _, _, text1, _ = _cycle(tmp_path, _wrap(text, cont))
    assert _raw(_body(text1)) == _raw(_wrap(text, cont))


@pytest.mark.parametrize(
    ("text", "key", "cont"),
    _p("test_second_write_equals_the_first", BOX_ROWS + NON_BOX_ROWS + [INF_ROW]),
)
def test_second_write_equals_the_first(tmp_path, text, key, cont):
    _, _, text1, text2 = _cycle(tmp_path, _wrap(text, cont))
    assert text1 == text2


@pytest.mark.parametrize("cont", CONTAINERS)
def test_neighbouring_entries_are_not_touched_by_a_box(tmp_path, cont):
    body = "before 1;\nbox (0 0 -1) (1 8e-3 1);\nafter 2;\n"
    d = _read_quiet(tmp_path, body, cont)
    assert _scope(d, cont).before.value == 1
    assert _scope(d, cont).after.value == 2


# --- the deprecated float view ---------------------------------------------------------------
VIEW_ROWS = [r for r in BOX_ROWS if r[0] in ("plain", "exponent-8e-3", "glued-parens")]


@pytest.mark.parametrize(
    ("text", "key", "cont"),
    _p("-", VIEW_ROWS),
)
def test_reading_value_emits_one_deprecation_warning(tmp_path, text, key, cont):
    box = _entry(_read_quiet(tmp_path, text, cont), key, cont)
    _, caught = _dep(lambda: box.value)
    assert len(caught) == 1
    assert ".groups" in str(caught[0].message)


@pytest.mark.parametrize(
    ("text", "key", "cont"),
    _p("-", VIEW_ROWS),
)
def test_assigning_value_emits_one_deprecation_warning(tmp_path, text, key, cont):
    box = _entry(_read_quiet(tmp_path, text, cont), key, cont)

    def assign():
        box.value = [[0, 0, 0], [2, 2, 2]]

    _, caught = _dep(assign)
    assert len(caught) == 1
    assert ".groups" in str(caught[0].message)


EXPECTED_FLOATS = {
    "plain": [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]],
    "exponent-8e-3": [[0.0, 0.0, -1.0], [1.0, 0.008, 1.0]],
    "glued-parens": [[-1e6, -1e6, -1e6], [1e6, -0.15, 0.3]],
}


@pytest.mark.parametrize(
    ("text", "key", "cont"), _p("test_value_view_returns_new_float_lists", VIEW_ROWS)
)
def test_value_view_returns_new_float_lists(tmp_path, text, key, cont):
    rid = next(r for r, t, _ in VIEW_ROWS if t == text)
    box = _entry(_read_quiet(tmp_path, text, cont), key, cont)
    expected = EXPECTED_FLOATS[rid]
    view = _quiet_value(box)
    assert view == expected
    assert all(isinstance(x, float) for g in view for x in g)


@pytest.mark.parametrize(
    ("text", "key", "cont"), _p("test_value_view_is_a_new_list_each_time", VIEW_ROWS)
)
def test_value_view_is_a_new_list_each_time(tmp_path, text, key, cont):
    """Each read is a new object (no live float list, no second source of truth)."""
    box = _entry(_read_quiet(tmp_path, text, cont), key, cont)
    first, second = _quiet_value(box), _quiet_value(box)
    assert first == second
    assert first is not second
    assert first[0] is not second[0]


@pytest.mark.parametrize(
    ("text", "key", "cont"), _p("test_value_view_refuses_in_place_edits", VIEW_ROWS)
)
def test_value_view_refuses_in_place_edits(tmp_path, text, key, cont):
    """The view is a read-only copy: an edit raises instead of being lost silently."""
    rid = next(r for r, t, _ in VIEW_ROWS if t == text)
    d = _read_quiet(tmp_path, text, cont)
    box = _entry(d, key, cont)
    before = d.toString()
    view = _quiet_value(box)
    for edit in (
        lambda: view.__setitem__(0, [9.0, 9.0, 9.0]),
        lambda: view[0].__setitem__(0, 99.0),
        lambda: view[0].append(1.0),
        lambda: view.extend([[1.0, 1.0, 1.0]]),
        lambda: view.pop(),
        lambda: view[1].sort(),
        lambda: view.clear(),
    ):
        with pytest.raises(FoamKitError, match="read-only"):
            edit()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(FoamKitError, match="read-only"):
            box.value[0][0] = 5
        with pytest.raises(FoamKitError, match="read-only"):
            box.value[0].append(1)
    assert view == EXPECTED_FLOATS[rid]
    assert _quiet_value(box) == EXPECTED_FLOATS[rid]
    assert d.toString() == before


@pytest.mark.parametrize(
    ("text", "key", "cont"), _p("test_assigned_value_is_written_and_stable", VIEW_ROWS)
)
def test_assigned_value_is_written_and_stable(tmp_path, text, key, cont):
    d = _read_quiet(tmp_path, text, cont)
    box = _entry(d, key, cont)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        box.value = [[0, 0, 0], [2, 2, 2]]
        assert box.value == [[0.0, 0.0, 0.0], [2.0, 2.0, 2.0]]
    text1 = d.toString()
    expected = _wrap(f"{key} (0 0 0) (2 2 2);" + NL, cont)
    assert _tokens(_body(text1)) == _tokens(expected)
    out = tmp_path / "edited"
    out.write_text(text1)
    second = _load(out)
    assert type(_entry(second, key, cont)) is fkt.ofBoundBox
    assert second.toString() == text1


# --- editing through .groups ----------------------------------------------------------------
@pytest.mark.parametrize("cont", CONTAINERS)
def test_editing_groups_replaces_a_group_without_a_warning(tmp_path, cont):
    d = _read_quiet(tmp_path, "box (0 0 -1) (1 8e-3 1);\n", cont)
    box = _entry(d, "box", cont)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        box.groups[1] = fkt.ofList(value=[2, 2, 2])
        text1 = d.toString()
    assert _tokens(_body(text1)) == _tokens(_wrap("box (0 0 -1) (2 2 2);\n", cont))
    # - the first group is untouched and keeps its text
    assert "(0 0 -1)" in text1


@pytest.mark.parametrize("cont", CONTAINERS)
def test_editing_both_groups_one_after_the_other_leaves_no_stale_text(tmp_path, cont):
    d = _read_quiet(tmp_path, "box (0 0 -1) (1 8e-3 1);\n", cont)
    box = _entry(d, "box", cont)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        box.groups[1] = fkt.ofList(value=[2, 2, 2])
        d.toString()
        box.groups[0] = fkt.ofList(value=[3, 3, 3])
        text1 = d.toString()
    assert _tokens(_body(text1)) == _tokens(_wrap("box (3 3 3) (2 2 2);\n", cont))
    assert "8e-3" not in text1


@pytest.mark.parametrize("cont", CONTAINERS)
def test_editing_items_of_a_group_leaves_no_stale_text(tmp_path, cont):
    d = _read_quiet(tmp_path, "box (0 0 -1) (1 8e-3 1);\n", cont)
    box = _entry(d, "box", cont)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        box.groups[1].value = [5, 6, 7]
        text1 = d.toString()
    assert _tokens(_body(text1)) == _tokens(_wrap("box (0 0 -1) (5 6 7);\n", cont))


def test_groups_of_a_plain_list_groups_is_its_value(tmp_path):
    d = _read_quiet(tmp_path, "c (1 2) (3 4);\n", "top", name="c")
    assert d.c.groups is d.c.value
    assert all(isinstance(g, fkt.ofList) for g in d.c.groups)
    assert len(d.c.groups) == 2


# --- bad assignments -------------------------------------------------------------------------
BAD_VALUES = [
    pytest.param([[1, 2], [3, 4]], id="groups-of-two"),
    pytest.param([[0, 0, 0]], id="one-group"),
    pytest.param([[0, 0, 0], [1, "a", 1]], id="string-item"),
    pytest.param([[0, 0, 0], [1, True, 1]], id="bool-item"),
    pytest.param("0 0 0 1 1 1", id="string"),
    pytest.param(5, id="number"),
]


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize("bad", BAD_VALUES)
def test_bad_assignment_raises_foamkiterror_and_keeps_the_old_value(
    tmp_path, bad, cont
):
    d = _read_quiet(tmp_path, "box (0 0 -1) (1 8e-3 1);\n", cont)
    box = _entry(d, "box", cont)
    before = d.toString()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(FoamKitError) as err:
            box.value = bad
    assert "box" in str(err.value)
    assert d.toString() == before


# --- no DeprecationWarning from the library's own code ----------------------------------------
@pytest.mark.parametrize("cont", CONTAINERS)
def test_load_tostring_and_write_emit_no_deprecation_warning(tmp_path, cont):
    # - one entry per name: the same key repeated would be an override, not a new entry
    lines = [
        t.replace("box", f"b{i}", 1) if t.startswith("box") else t
        for i, (_, t, _) in enumerate(BOX_ROWS)
    ]
    text = "".join(lines)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        path = tmp_path / "boxes"
        path.write_text(HEADER + _wrap(text, cont))
        d = _load(path)
        text1 = d.toString()
        assert "b0" in text1
        out = tmp_path / "again"
        out.write_text(text1)
        _load(out).toString()


@pytest.fixture
def box_case(tmp_path):
    """A copy of the pitzDaily case whose setFieldsDict holds boxes."""
    path = tmp_path / "pitzDaily"
    shutil.copytree(FIXTURES / "pitzDaily", path)
    (path / "system" / "setFieldsDict").write_text(
        HEADER
        + "box (0 0 -1) (1 8e-3 1);\n"
        + "sub\n{\n    box (-1e6 -1e6 -1e6)(1e6 -0.15 0.3);\n    p1 (0 0 0) (1 1 1);\n}\n"
    )
    return path


def test_case_init_save_load_and_write_emit_no_deprecation_warning(box_case):
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        c = pf.init(path=box_case)
        c.system.setFieldsDict.toString()
        assert c.toJSON()
        c.save(path=box_case)
        loaded = pf.load(path=box_case)
        loaded.system.setFieldsDict.toString()
        loaded.write()


def test_case_cache_round_trip_keeps_type_and_number_text(box_case):
    c = pf.init(path=box_case)
    c.save(path=box_case)
    loaded = pf.load(path=box_case)
    for case in (c, loaded):
        sf = case.system.setFieldsDict
        assert isinstance(sf.box, fkt.ofBoundBox)
        assert isinstance(sf.sub.box, fkt.ofBoundBox)
        assert isinstance(sf.sub.p1, fkt.ofBoundBox)
        text = sf.toString()
        assert "(0 0 -1) (1 8e-3 1)" in text
        assert "(-1e6 -1e6 -1e6)" in text
    assert loaded.system.setFieldsDict.toString() == c.system.setFieldsDict.toString()


# --- the parser --------------------------------------------------------------------------------
def test_parse_bound_box_value_no_longer_exists():
    assert not hasattr(fkt.DictFileParser, "_parseBoundBoxValue")


# --- real files ----------------------------------------------------------------------------------
REAL = [
    pytest.param(CAPILLARY, "8e-3", id="capillaryRise"),
    pytest.param(PIPE, "1e6", id="pipeCyclic"),
]


@pytest.mark.parametrize(("path", "spelling"), REAL)
def test_real_file_loads(path, spelling):
    assert _load(path) is not None


@pytest.mark.parametrize(
    ("path", "spelling"),
    REAL,
)
def test_real_file_second_write_equals_the_first(tmp_path, path, spelling):
    text1 = _load(path).toString()
    out = tmp_path / path.name
    out.write_text(text1)
    assert _load(out).toString() == text1


@pytest.mark.parametrize(
    ("path", "spelling"),
    REAL,
)
def test_real_file_box_line_keeps_the_source_number_text(path, spelling):
    src = [ln for ln in path.read_text().splitlines() if re.match(r"\s*box\s+\(", ln)]
    assert len(src) == 1 and spelling in src[0]
    written = [
        ln for ln in _load(path).toString().splitlines() if re.match(r"\s*box\s+\(", ln)
    ]
    assert len(written) == 1
    assert _raw(written[0]) == _raw(src[0])
