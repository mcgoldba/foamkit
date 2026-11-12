"""Specification tests for T-083 (issue #111): an edit inside a sub-dict changes only its lines.

Spec: docs/tickets/T-083-preserve-layout-inside-edited-subdicts.md (the nested half of T-020;
T-020a's top-level tests are in `test_preserve_layout.py`).  Editing one entry inside a
sub-dict at any depth changes only that entry's lines.  The keyword line, braces, blank lines,
`//` comments and untouched siblings keep their source text.  A dict is regenerated as a whole
when it is a one-line block or was moved to another depth.

Layout of this module:
- real files: pitzDaily `fvSolution`, `0/U`, `controlDict` and the `foundation-11` heatedDuct
  `snappyHexMeshDict`; each assertion is the exact diff against the source.
- hand-written files: comments, blank lines and padding of untouched siblings, one-line blocks,
  added and deleted keys, rename, move to another depth.
- corpus: every loading file of `tests/releases/` and pitzDaily; an unedited write is the
  source, and a one-number edit of a nested entry changes one line.
- write 1 == write 2, `_preserve=False`, and the `.params` cache (also an old cache that has
  no nested records).
"""

import difflib
import json
import re

import pytest

import foamkit.functions as pf
import foamkit.types as pt
from conftest import FIXTURES, TESTS
from test_preserve_layout import CORPUS, _id

RELEASES = TESTS / "releases"
PITZ = FIXTURES / "pitzDaily"
SNAPPY = RELEASES / "foundation-11.heatedDuct.snappyHexMeshDict"

_HEAD = (
    "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
    "    class       dictionary;\n    object      t;\n}\n\n"
)


def _load(path):
    return pt.DictFileParser(path).readDictFile()


def _reload(text, tmp_path, name="t"):
    path = tmp_path / name
    path.write_text(text)
    return _load(path)


def _source(path):
    return path.read_text(encoding="utf-8")


def _ops(src, out):
    a, b = src.split("\n"), out.split("\n")
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return a, b, [op for op in sm.get_opcodes() if op[0] != "equal"]


def _one_line_replaced(src, out, old_key, new_words, indent):
    """Exactly one source line (`old_key ...`) became one line with `new_words`."""
    a, b, ops = _ops(src, out)
    assert len(ops) == 1, f"expected one changed hunk, got {ops}"
    tag, i1, i2, j1, j2 = ops[0]
    assert (tag, i2 - i1, j2 - j1) == ("replace", 1, 1), ops[0]
    assert a[i1].split()[0] == old_key, a[i1]
    assert b[j1].split() == new_words, b[j1]
    assert b[j1].startswith(" " * indent + new_words[0]), repr(b[j1])


# --------------------------------------------------------------------------------------
# real files: the exact diff
# --------------------------------------------------------------------------------------


def _edit_solvers_p_tolerance(d):
    d.solvers.p.tolerance = 1e-7


def _edit_inlet_value(d):
    d.boundaryField.inlet.value.value = pt.ofVector(value=[11, 0, 0])


def _edit_probes_write_interval(d):
    d.functions.probes.writeInterval = 5


# id -> (file, edit, old key, new words, indent)
REAL_EDITS = {
    "fvSolution-solvers.p.tolerance": (
        PITZ / "system" / "fvSolution",
        _edit_solvers_p_tolerance,
        "tolerance",
        ["tolerance", "1e-07;"],
        8,
    ),
    "U-boundaryField.inlet.value": (
        PITZ / "0" / "U",
        _edit_inlet_value,
        "value",
        ["value", "uniform", "(11", "0", "0);"],
        8,
    ),
    "controlDict-functions.probes.writeInterval": (
        PITZ / "system" / "controlDict",
        _edit_probes_write_interval,
        "writeInterval",
        ["writeInterval", "5;"],
        8,
    ),
}


@pytest.mark.parametrize("key", sorted(REAL_EDITS))
def test_editing_one_nested_entry_changes_one_line(key):
    path, edit, old_key, words, indent = REAL_EDITS[key]
    src = _source(path)
    d = _load(path)
    edit(d)
    _one_line_replaced(src, d.toString(), old_key, words, indent)


def test_the_boundary_field_edit_reads_back_as_the_new_value(tmp_path):
    # - (the edit helper itself is sound: the new value is written, not dropped)
    path, edit, *_ = REAL_EDITS["U-boundaryField.inlet.value"]
    d = _load(path)
    edit(d)
    back = _reload(d.toString(), tmp_path, "U")
    assert list(back.boundaryField.inlet.value.value.value) == [11, 0, 0]


@pytest.mark.parametrize("key", sorted(REAL_EDITS))
def test_a_nested_edit_is_written_with_the_new_value(key, tmp_path):
    path, edit, old_key, words, _ = REAL_EDITS[key]
    d = _load(path)
    edit(d)
    out = d.toString()
    assert " ".join(words) in " ".join(out.split())


def test_editing_a_function_object_setting_keeps_the_include_lines_as_read():
    path = PITZ / "system" / "controlDict"
    d = _load(path)
    d.functions.probes.writeInterval = 5
    assert (
        "    #includeFunc streamlines\n    #includeFunc writeObjects(kEpsilon:G)\n"
        in (d.toString())
    )


def test_a_sibling_dict_of_the_edited_one_keeps_its_source_text():
    # - the regex-named solver block after `p` is untouched: padding and blank line stay
    path = PITZ / "system" / "fvSolution"
    d = _load(path)
    d.solvers.p.tolerance = 1e-7
    out = d.toString()
    assert (
        '    }\n\n    "(U|k|epsilon|omega|f|v2)"\n    {\n        solver          '
        "smoothSolver;\n"
    ) in out


# --- the one-line block of the foundation-11 heatedDuct dictionary ---------------------


def _snappy_edit(d):
    d.geometry.heatedDuct.regions.metalInlet.name = "metalInletX"


def test_editing_a_one_line_block_changes_only_that_source_line():
    src = _source(SNAPPY)
    d = _load(SNAPPY)
    _snappy_edit(d)
    a, b, ops = _ops(src, d.toString())
    assert len(ops) == 1, f"expected one changed hunk, got {len(ops)}"
    tag, i1, i2, j1, j2 = ops[0]
    assert i2 - i1 == 1 and a[i1].split()[:2] == ["metalInlet", "{"], ops[0]
    # - written as the standard multi-line block (blank lines may come with it)
    assert [x.split() for x in b[j1:j2] if x.strip()] == [
        ["metalInlet"],
        ["{"],
        ["name", "metalInletX;"],
        ["}"],
    ]
    # - the sibling lines stay as read
    for sibling in ("heaterInlet    { name heaterInlet;    }", "fluidInlet     {"):
        assert any(sibling in ln for ln in b)


def test_editing_a_one_line_block_is_written_with_the_new_value(tmp_path):
    d = _load(SNAPPY)
    _snappy_edit(d)
    back = _reload(d.toString(), tmp_path, "snappy")
    assert back.geometry.heatedDuct.regions.metalInlet.name.value == "metalInletX"
    assert back.geometry.heatedDuct.regions.heaterInlet.name.value == "heaterInlet"


# --------------------------------------------------------------------------------------
# hand-written files: what must survive around the edited entry
# --------------------------------------------------------------------------------------

NESTED = (
    _HEAD
    + "sub // air\n"
    + "{\n"
    + "    // leading note\n"
    + "    a       1;   // trailing a\n"
    + "\n"
    + "    b          2;\n"
    + "    // between b and c\n"
    + "\n"
    + "    c   3;\n"
    + "\n"
    + "    inner // inner keyword note\n"
    + "    {\n"
    + "        x   1;   // keep x\n"
    + "\n"
    + "        y        2;\n"
    + "        deep\n"
    + "        {\n"
    + "            q    1;   // deepest\n"
    + "            r  2;\n"
    + "        }\n"
    + "    }\n"
    + "\n"
    + "    after   5;\n"
    + "}; // end of sub\n"
    + "\n"
    + "other      1;\n"
)


@pytest.fixture
def nested(tmp_path):
    d = _reload(NESTED, tmp_path)
    assert d.toString() == NESTED
    return d


# id -> (edit, source line replaced (stripped), words of the new line, indent)
NESTED_EDITS = {
    "depth-1": (lambda d: setattr(d.sub, "b", 20), "b          2;", ["b", "20;"], 4),
    "depth-2": (
        lambda d: setattr(d.sub.inner, "y", 20),
        "y        2;",
        ["y", "20;"],
        8,
    ),
    "depth-3": (
        lambda d: setattr(d.sub.inner.deep, "r", 20),
        "r  2;",
        ["r", "20;"],
        12,
    ),
}


def _nested_params():
    return [pytest.param(k, id=k) for k in sorted(NESTED_EDITS)]


@pytest.mark.parametrize("key", _nested_params())
def test_a_nested_edit_changes_only_its_line_at_any_depth(nested, key):
    edit, old, words, indent = NESTED_EDITS[key]
    edit(nested)
    out = nested.toString()
    a, b, ops = _ops(NESTED, out)
    assert len(ops) == 1, f"expected one changed hunk, got {len(ops)}"
    tag, i1, i2, j1, j2 = ops[0]
    assert (tag, i2 - i1, j2 - j1) == ("replace", 1, 1), ops[0]
    assert a[i1].strip() == old
    assert b[j1].split() == words
    assert b[j1].startswith(" " * indent + words[0])


@pytest.mark.parametrize("key", _nested_params())
def test_a_nested_edit_is_written_and_read_back(nested, tmp_path, key):
    edit, old, words, indent = NESTED_EDITS[key]
    edit(nested)
    out = nested.toString()
    assert old not in out
    back = _reload(out, tmp_path, "back")
    assert back.sub.a.value == 1 and back.sub.inner.deep.q.value == 1


_FRAGMENTS = {
    "keyword-comment-and-leading-note": "sub // air\n{\n    // leading note\n",
    "trailing-comment-of-a-sibling": "    a       1;   // trailing a\n\n",
    "full-line-comment-between-siblings": "    // between b and c\n\n    c   3;\n\n",
    "inner-keyword-comment-and-sibling-comment": (
        "    inner // inner keyword note\n    {\n        x   1;   // keep x\n\n"
    ),
    "deepest-sibling-comment": "            q    1;   // deepest\n",
    "closing-line-and-what-follows": (
        "    }\n\n    after   5;\n}; // end of sub\n\nother      1;\n"
    ),
}


_FRAGMENT_PARAMS = [pytest.param(k, id=k) for k in sorted(_FRAGMENTS)]


@pytest.mark.parametrize("name", _FRAGMENT_PARAMS)
def test_comments_blank_lines_and_braces_around_an_edit_keep_their_text(nested, name):
    nested.sub.inner.y = 20
    assert _FRAGMENTS[name] in nested.toString()


def test_a_comment_on_an_unedited_sibling_survives_an_edit_next_to_it(nested):
    nested.sub.inner.deep.r = 20
    out = nested.toString()
    assert "// keep x" in out and "// deepest" in out and "// trailing a" in out


REVERTS = {
    "depth-1": lambda d: setattr(d.sub, "b", 2),
    "depth-2": lambda d: setattr(d.sub.inner, "y", 2),
    "depth-3": lambda d: setattr(d.sub.inner.deep, "r", 2),
}


@pytest.mark.parametrize("key", _nested_params())
def test_the_edit_reverted_writes_the_source_again(nested, key):
    NESTED_EDITS[key][0](nested)
    REVERTS[key](nested)
    assert nested.toString() == NESTED


# --- an added key and a deleted key ---------------------------------------------------


def test_an_added_key_is_inserted_before_the_closing_brace_of_its_dict(nested):
    nested.sub.inner.added = 7
    out = nested.toString()
    a, b, ops = _ops(NESTED, out)
    assert all(op[0] == "insert" for op in ops), ops
    inserted = [ln for _, _, _, j1, j2 in ops for ln in b[j1:j2] if ln.strip()]
    assert [ln.split() for ln in inserted] == [["added", "7;"]]
    assert inserted[0].startswith("        added")
    # - it comes after the last entry of `inner` and right before its `}`
    after = [ln for ln in b[b.index(inserted[0]) + 1 :] if ln.strip()]
    assert after[0] == "    }"


def test_an_added_key_in_a_real_sub_dict_only_adds_lines():
    path = PITZ / "system" / "fvSolution"
    src = _source(path)
    d = _load(path)
    d.solvers.p.maxIter = 50
    a, b, ops = _ops(src, d.toString())
    assert all(op[0] == "insert" for op in ops), ops
    inserted = [ln for _, _, _, j1, j2 in ops for ln in b[j1:j2] if ln.strip()]
    assert [ln.split() for ln in inserted] == [["maxIter", "50;"]]
    # - the inserted entry sits right before the `}` of `p`
    assert a[ops[0][1]] == "    }"


def test_an_added_key_in_a_sub_dict_reads_back(nested, tmp_path):
    nested.sub.inner.added = 7
    back = _reload(nested.toString(), tmp_path, "back")
    assert back.sub.inner.added.value == 7
    assert back.sub.inner.y.value == 2


def test_deleting_a_key_removes_only_its_lines_and_its_leading_blank_lines(nested):
    # - `c` follows a comment and a blank line (its gap, removed with it); the blank line
    # - after `c` is `inner`'s gap and stays
    del nested.sub.c
    out = nested.toString()
    assert out == NESTED.replace("\n    c   3;\n", "", 1)
    a, b, ops = _ops(NESTED, out)
    assert all(op[0] == "delete" for op in ops), ops
    removed = [ln for i1, i2 in [(o[1], o[2]) for o in ops] for ln in a[i1:i2]]
    assert [ln for ln in removed if ln.strip()] == ["    c   3;"]


def test_deleting_a_key_in_a_real_sub_dict_removes_one_line():
    path = PITZ / "system" / "fvSolution"
    src = _source(path)
    d = _load(path)
    del d.solvers.p.relTol
    a, b, ops = _ops(src, d.toString())
    assert [(op[0], op[2] - op[1]) for op in ops] == [("delete", 1)], ops
    assert a[ops[0][1]].split() == ["relTol", "0.1;"]


def test_a_deleted_key_is_gone_after_reading_back(nested, tmp_path):
    del nested.sub.inner.y
    back = _reload(nested.toString(), tmp_path, "back")
    assert getattr(back.sub.inner, "y", None) is None
    assert back.sub.inner.x.value == 1


# --- rename and `_comment_keyword` ----------------------------------------------------


def test_renaming_a_sub_dict_changes_only_its_keyword_line(nested):
    nested.sub.inner._name = "renamed"
    a, b, ops = _ops(NESTED, nested.toString())
    assert len(ops) == 1, f"expected one changed hunk, got {len(ops)}"
    tag, i1, i2, j1, j2 = ops[0]
    assert (tag, i2 - i1, j2 - j1) == ("replace", 1, 1), ops[0]
    assert a[i1].split()[0] == "inner"
    assert b[j1].split()[0] == "renamed"


def test_renaming_a_real_sub_dict_changes_only_its_keyword_line():
    path = PITZ / "0" / "U"
    src = _source(path)
    d = _load(path)
    d.boundaryField.outlet._name = "outletRenamed"
    a, b, ops = _ops(src, d.toString())
    assert [(op[0], op[2] - op[1], op[4] - op[3]) for op in ops] == [("replace", 1, 1)]
    assert b[ops[0][3]].split() == ["outletRenamed"]


def test_changing_the_keyword_comment_changes_only_the_keyword_line(nested):
    nested.sub.inner._comment_keyword = " renamed note"
    a, b, ops = _ops(NESTED, nested.toString())
    assert len(ops) == 1, f"expected one changed hunk, got {len(ops)}"
    tag, i1, i2, j1, j2 = ops[0]
    assert (tag, i2 - i1, j2 - j1) == ("replace", 1, 1), ops[0]
    assert a[i1].split()[0] == "inner" and "renamed note" in b[j1]


def test_a_renamed_sub_dict_reads_back_under_the_new_name(nested, tmp_path):
    nested.sub.inner._name = "renamed"
    back = _reload(nested.toString(), tmp_path, "back")
    assert back.sub.renamed.x.value == 1


# --- a dict that cannot be partly preserved is regenerated as a whole -----------------

ONE_LINE = (
    _HEAD
    + "outer\n{\n"
    + "    p { type patch; }\n"
    + "    q       {  type   wall;   }\n"
    + "    keep      1;\n"
    + "    multi\n    {\n        a    1;\n        b       2;\n    }\n"
    + "}\n"
)


@pytest.fixture
def one_line(tmp_path):
    d = _reload(ONE_LINE, tmp_path)
    assert d.toString() == ONE_LINE
    return d


def test_editing_a_one_line_block_leaves_the_other_lines_of_its_parent_alone(one_line):
    one_line.outer.p.type = "wall"
    out = one_line.toString()
    a, b, ops = _ops(ONE_LINE, out)
    assert len(ops) == 1, ops
    assert a[ops[0][1]].split()[:2] == ["p", "{"] and ops[0][2] - ops[0][1] == 1
    for kept in (
        "    q       {  type   wall;   }\n",
        "    keep      1;\n",
        "        b       2;\n",
    ):
        assert kept in out


def test_the_edited_one_line_block_is_written_as_a_multi_line_block(one_line, tmp_path):
    one_line.outer.p.type = "wall"
    out = one_line.toString()
    assert "p { type patch; }" not in out
    assert re.search(r"^    p\n    \{\n        type\s+wall;\n    \}\n", out, re.M)
    assert _reload(out, tmp_path, "back").outer.p.type.value == "wall"


def test_a_one_line_block_next_to_an_edited_entry_keeps_its_text(one_line):
    # - the edit is in `multi`; the one-line blocks before it stay as read
    one_line.outer.multi.b = 20
    out = one_line.toString()
    assert "    p { type patch; }\n    q       {  type   wall;   }\n" in out
    assert "        a    1;\n" in out


def test_a_one_line_block_with_a_comment_after_the_brace_is_regenerated(tmp_path):
    src = _HEAD + "outer\n{\n    p { d 1; // note\n    }\n    keep    1;\n}\n"
    d = _reload(src, tmp_path)
    d.outer.p.d = 2
    out = d.toString()
    assert "    keep    1;\n" in out
    assert _reload(out, tmp_path, "back").outer.p.d.value == 2


def _moved_up(d):
    d.inner = d.outer.inner
    del d.outer.inner


def _moved_down(d):
    d.outer.deep = d.outer.inner
    d.outer.deep._name = (
        "deep"  # - (assigning does not rename: the old name is written)
    )
    del d.outer.inner


MOVE = (
    _HEAD
    + "outer\n{\n    inner\n    {\n        x      1;\n        y   2;\n    }\n\n"
    + "    z   3;\n}\n"
)


@pytest.mark.parametrize(
    "move", [_moved_up, _moved_down], ids=["to-the-top-level", "one-level-deeper"]
)
def test_a_sub_dict_moved_to_another_depth_has_no_text_with_the_old_indentation(
    move, tmp_path
):
    d = _reload(MOVE, tmp_path)
    move(d)
    out = d.toString()
    # - `x` was read with 6 spaces of padding at depth 2; a moved block is regenerated
    assert "x      1;" not in out
    assert "y   2;" not in out
    back = _reload(out, tmp_path, "back")
    holder = back.inner if move is _moved_up else back.outer.deep
    assert holder.x.value == 1 and holder.y.value == 2


@pytest.mark.parametrize(
    "move", [_moved_up, _moved_down], ids=["to-the-top-level", "one-level-deeper"]
)
def test_the_parent_of_a_moved_sub_dict_keeps_its_other_entry(move, tmp_path):
    d = _reload(MOVE, tmp_path)
    move(d)
    assert _reload(d.toString(), tmp_path, "back").outer.z.value == 3


def test_a_sub_dict_edited_in_a_second_dict_does_not_bring_text_of_the_first(tmp_path):
    # - a dict assigned from another file: the source text of file one must not appear in
    # - file two (the record belongs to the file it was read from)
    one = _reload(_HEAD + "sub\n{\n    a      1;\n    b   2;\n}\n", tmp_path, "one")
    two = _reload(_HEAD + "other   3;\n", tmp_path, "two")
    two.sub = one.sub
    two.sub.b = 5
    out = two.toString()
    assert "a      1;" not in out
    assert _reload(out, tmp_path, "back").sub.b.value == 5


# --------------------------------------------------------------------------------------
# write 1 == write 2; _preserve=False
# --------------------------------------------------------------------------------------


def _all_edits():
    out = [pytest.param(p, e, id=k) for k, (p, e, *_) in sorted(REAL_EDITS.items())]
    out.append(pytest.param(SNAPPY, _snappy_edit, id="snappy-one-line-block"))
    return out


@pytest.mark.parametrize("path,edit", _all_edits())
def test_write_two_equals_write_one_after_a_nested_edit(path, edit, tmp_path):
    d = _load(path)
    edit(d)
    first = d.toString()
    assert d.toString() == first
    second = _reload(first, tmp_path, path.name).toString()
    assert second == first


@pytest.mark.parametrize("key", _nested_params())
def test_write_two_equals_write_one_after_an_edit_of_the_hand_written_file(
    nested, tmp_path, key
):
    NESTED_EDITS[key][0](nested)
    first = nested.toString()
    assert nested.toString() == first
    assert _reload(first, tmp_path, "again").toString() == first


@pytest.mark.parametrize(
    "edit",
    [
        lambda d: setattr(d.sub, "added", 7),
        lambda d: delattr(d.sub, "c"),
        lambda d: setattr(d.sub.inner, "_name", "renamed"),
    ],
    ids=["added", "deleted", "renamed"],
)
def test_write_two_equals_write_one_after_a_structural_edit(nested, tmp_path, edit):
    edit(nested)
    first = nested.toString()
    assert _reload(first, tmp_path, "again").toString() == first


def _drop_records(obj, seen=None):
    """Remove every source-layout record, at any depth."""
    seen = set() if seen is None else seen
    if id(obj) in seen or not isinstance(obj, pt.ofDict):
        return
    seen.add(id(obj))
    if isinstance(obj, pt.ofDictFile):
        obj.__dict__["_srcLayout"] = None
    else:
        obj.__dict__.pop("_srcLayout", None)
    for v in list(obj.__dict__.values()):
        _drop_records(v, seen)


@pytest.mark.parametrize("path,edit", _all_edits())
def test_preserve_false_regenerates_the_whole_file_after_a_nested_edit(path, edit):
    d = _load(path)
    edit(d)
    out = d.toString(_preserve=False)
    # - nothing of the source padding is left (`tolerance       1e-06;` style)
    plain = _load(path)
    edit(plain)
    _drop_records(plain)
    assert out == plain.toString()


def test_preserve_false_does_not_keep_the_text_of_untouched_siblings():
    path = PITZ / "system" / "fvSolution"
    d = _load(path)
    d.solvers.p.tolerance = 1e-7
    out = d.toString(_preserve=False)
    assert "solver          GAMG;" not in out
    assert "relTol          0.1;" not in out


def test_preserve_false_on_an_unedited_nested_file_is_not_the_source():
    path = PITZ / "system" / "fvSolution"
    assert _load(path).toString(_preserve=False) != _source(path)


def test_preserve_false_ignores_the_nested_records_after_the_source_changed(nested):
    nested.sub.inner.y = 20
    d_plain = nested.toString(_preserve=False)
    assert "    a       1;" not in d_plain
    _drop_records(nested)
    assert nested.toString() == d_plain


# --------------------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------------------

_SCALARS = (pt.ofInt, pt.ofFloat)


def _first_nested_scalar(d):
    """(path of keys, entry) of the first int/float below the top level, or None."""

    def walk(node, trail):
        for k, v in node.__dict__.items():
            if k in node._CLASS_VARS:
                continue
            if isinstance(v, pt.ofDict):
                found = walk(v, trail + [k])
                if found:
                    return found
            elif trail and isinstance(v, _SCALARS) and type(v.value) in (int, float):
                return trail + [k], v
        return None

    return walk(d, [])


def _entry_line_count(src, key, value):
    """How many source lines are `key <value>;` as a whole line (one-line entries)."""
    pattern = re.compile(
        rf"^\s*{re.escape(key)}\s+{re.escape(str(value))}\s*;\s*$", re.M
    )
    return len(pattern.findall(src))


def _corpus_edit_params():
    out = []
    for p in CORPUS:
        d = _load(p)
        found = _first_nested_scalar(d)
        if found is None:
            continue
        trail, entry = found
        src = _source(p)
        raw = re.search(
            rf"^[ \t]*{re.escape(trail[-1])}[ \t]+(\S+?)[ \t]*;[ \t]*$", src, re.M
        )
        if raw is None or _entry_line_count(src, trail[-1], raw.group(1)) != 1:
            continue
        out.append(pytest.param(p, trail, raw.group(1), id=_id(p)))
    return out


CORPUS_EDITS = _corpus_edit_params()


def test_the_corpus_has_nested_entries_to_edit():
    assert len(CORPUS_EDITS) >= 10


@pytest.mark.parametrize("path", [pytest.param(p, id=_id(p)) for p in CORPUS])
def test_an_unedited_write_is_the_source_with_nested_records_in_place(path):
    assert _load(path).toString() == _source(path)


@pytest.mark.parametrize("path,trail,raw", CORPUS_EDITS)
def test_a_nested_number_edit_changes_one_line_in_the_corpus(path, trail, raw):
    src = _source(path)
    d = _load(path)
    node = d
    for k in trail[:-1]:
        node = getattr(node, k)
    entry = getattr(node, trail[-1])
    setattr(node, trail[-1], entry.value + 1)
    out = d.toString()
    a, b, ops = _ops(src, out)
    changed_src = sum(i2 - i1 for _, i1, i2, _, _ in ops)
    changed_out = sum(j2 - j1 for _, _, _, j1, j2 in ops)
    assert changed_src == 1 and changed_out == 1


@pytest.mark.parametrize("path,trail,raw", CORPUS_EDITS)
def test_a_nested_number_edit_then_revert_writes_the_source(path, trail, raw):
    src = _source(path)
    d = _load(path)
    node = d
    for k in trail[:-1]:
        node = getattr(node, k)
    old = getattr(node, trail[-1]).value
    setattr(node, trail[-1], old + 1)
    setattr(node, trail[-1], old)
    assert d.toString() == src


# --------------------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------------------


def _case_dict(c, rel):
    folder = "t_0" if rel.parts[0] == "0" else rel.parts[0]
    return c[folder][rel.parts[1]]


def _strip_nested_records(node, depth=0):
    """Make a cache like the one an older version wrote: records only at file level."""
    if isinstance(node, dict):
        if depth > 2:
            node.pop("_srcLayout", None)
        for v in node.values():
            _strip_nested_records(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _strip_nested_records(v, depth + 1)


@pytest.mark.parametrize("key", sorted(REAL_EDITS))
def test_cache_round_trip_writes_the_source_before_any_edit(key, case):
    path = REAL_EDITS[key][0]
    rel = path.relative_to(PITZ)
    pf.init(path=case).save(path=case)
    c = pf.load(path=case)
    assert _case_dict(c, rel).toString() == _source(case / rel)


@pytest.mark.parametrize("key", sorted(REAL_EDITS))
def test_cache_round_trip_gives_the_same_nested_edit_diff(key, case):
    path, edit, old_key, words, indent = REAL_EDITS[key]
    rel = path.relative_to(PITZ)
    src = _source(case / rel)
    pf.init(path=case).save(path=case)
    c = pf.load(path=case)
    d = _case_dict(c, rel)
    edit(d)
    _one_line_replaced(src, d.toString(), old_key, words, indent)


@pytest.mark.parametrize("key", sorted(REAL_EDITS))
def test_cache_round_trip_and_fresh_read_write_the_same_text_after_a_nested_edit(
    key, case
):
    path, edit, *_ = REAL_EDITS[key]
    rel = path.relative_to(PITZ)
    fresh = _load(case / rel)
    edit(fresh)
    pf.init(path=case).save(path=case)
    d = _case_dict(pf.load(path=case), rel)
    edit(d)
    assert d.toString() == fresh.toString()


@pytest.mark.parametrize("key", sorted(REAL_EDITS))
def test_an_old_cache_without_nested_records_loads_and_writes_the_source(key, case):
    path = REAL_EDITS[key][0]
    rel = path.relative_to(PITZ)
    pf.init(path=case).save(path=case)
    cache = case / ".params" / "_case.json"
    data = json.loads(cache.read_text())
    _strip_nested_records(data)
    cache.write_text(json.dumps(data))
    c = pf.load(path=case)
    assert _case_dict(c, rel).toString() == _source(case / rel)


@pytest.mark.parametrize("key", sorted(REAL_EDITS))
def test_an_old_cache_writes_a_nested_edit_correctly(key, case, tmp_path):
    path, edit, old_key, words, indent = REAL_EDITS[key]
    rel = path.relative_to(PITZ)
    pf.init(path=case).save(path=case)
    cache = case / ".params" / "_case.json"
    data = json.loads(cache.read_text())
    _strip_nested_records(data)
    cache.write_text(json.dumps(data))
    d = _case_dict(pf.load(path=case), rel)
    edit(d)
    out = d.toString()
    assert " ".join(words) in " ".join(out.split())
    # - the edited entry is written once, and the other top-level entries stay as read
    src = _source(case / rel)
    assert out.count("FoamFile") == src.count("FoamFile")
    back = _reload(out, tmp_path, "back")
    assert back.toString() == out


def test_an_old_cache_nested_edit_keeps_the_top_level_entries_as_read(case):
    rel = PITZ.joinpath("system", "fvSolution").relative_to(PITZ)
    src = _source(case / rel)
    pf.init(path=case).save(path=case)
    cache = case / ".params" / "_case.json"
    data = json.loads(cache.read_text())
    _strip_nested_records(data)
    cache.write_text(json.dumps(data))
    d = _case_dict(pf.load(path=case), rel)
    d.solvers.p.tolerance = 1e-7
    out = d.toString()
    # - the entries after `solvers` are written from the top-level record
    assert out.endswith(src[src.index("SIMPLE\n{") :])


# --------------------------------------------------------------------------------------
# fingerprints of top-level dictionaries stay as T-020a wrote them (old caches)
# --------------------------------------------------------------------------------------

# - recorded in a `.params` cache written by T-020a (origin/main before T-083)
OLD_PRINTS = [
    ("system/fvSolution", "solvers", "b17d677301d10be54ae925b46b3bdb0b"),
    ("system/fvSolution", "SIMPLE", "4df9c08f4510b6c804100d6b11227241"),
    ("system/fvSolution", "relaxationFactors", "a1c6380d6800b7865d7d3fd439044d04"),
    ("0/U", "boundaryField", "6b9d138f9c0fac8bbf095cbdcea7c332"),
]


@pytest.mark.parametrize("rel,key,print_", OLD_PRINTS)
def test_the_fingerprint_of_a_top_level_dict_is_the_one_an_old_cache_holds(
    rel, key, print_
):
    d = _load(PITZ / rel)
    assert pt._fingerprint(key, d.__dict__[key]) == print_
