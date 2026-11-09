"""Specification tests for T-020a (issue #27): an unedited read -> write keeps the source.

Spec: docs/tickets/T-020-preserve-unedited-entry-layout.md (gap table, design note and the
narrowed acceptance criteria).  Scope is the top level of a file, the FoamFile block and the
file tail.  Inside an edited top-level sub-dict the whole block is regenerated (T-083 is out
of scope).

Layout of this module:
- corpus: every file of `tests/releases/` that loads plus every pitzDaily dictionary;
  unedited `toString()` equals the source (read with universal newlines), the number of
  changed lines is 0, and a second write equals the first.  Files that do not load yet are
  listed in `NOT_LOADING` with the blocking ticket and are picked up once they load.
- edits: an edit changes only the lines of the top-level entry that holds it.
- every way to edit is detected (the design compares value fingerprints at write time, so a
  missed edit would silently write stale text).  These pass today and must keep passing.
- cache: `init` -> `save` -> `load` -> write keeps the source, an edit after `load` is written.

Tests marked `xfail(strict=True)` fail on main today for the reason in the marker; the
implementation of T-020a removes the marks.
"""

import difflib
import re
import warnings

import pytest

import foamkit.functions as pf
import foamkit.types as pt
from conftest import FIXTURES, TESTS

RELEASES = TESTS / "releases"
PITZ = FIXTURES / "pitzDaily"

# - Files of `tests/releases/` that do not load on main: file name -> blocking ticket.
# - A file that starts to load must be removed from here (its test below fails to say so);
# - it then joins the corpus automatically.
NOT_LOADING = {
    "esi-v2606.good-if1.dict": "T-026",
    "esi-v2606.good-if3.dict": "T-026",
    "esi-v2606.squareBend.blockMeshDict": "T-026",
    "foundation-14.cylinder.fvSchemes": "T-026",
    "foundation-13.aerofoilNACA0012Steady.U": "T-027",
    "foundation-14.aerofoilNACA0012Steady.U": "T-027",
    "foundation-14.cylinder.blockMeshDict": "T-027",
    "foundation-14.rotatingCube.blockMeshDict": "T-027",
    "esi-v2606.good-word-expand.dict": "T-028",
    "foundation-14.trayedPipe.createZonesDict": "T-028",
    "foundation-14.engine2Valve2D.fvConstraints": "T-029",
    "esi-v2606.freePiston.U": "T-030",
    "foundation-14.floatingBeam.blockMeshDict": "T-030",
    "esi-v2606.potentialFoam-cylinder.blockMeshDict": "T-031",
    "esi-v2606.flange.faceSetDict": "T-046",
    "foundation-14.SandiaD_LTS.radiationProperties": "T-057",
}


def _load(path):
    """The parsed dictionary file, or None if it does not load (FoamKitError is a SystemExit)."""
    try:
        return pt.DictFileParser(path).readDictFile()
    except (Exception, SystemExit):
        return None


def _source(path):
    # - universal newlines, as the ticket says (Gap note 4)
    return path.read_text(encoding="utf-8")


_RELEASE_FILES = sorted(
    p for p in RELEASES.iterdir() if p.is_file() and not p.name.startswith(".")
)
_PITZ_FILES = sorted(
    p for p in PITZ.rglob("*") if p.is_file() and "postProcessing" not in p.parts
)


def _id(path):
    root = PITZ if PITZ in path.parents else RELEASES
    prefix = "pitzDaily/" if root is PITZ else ""
    return prefix + path.relative_to(root).as_posix()


CORPUS = [p for p in _PITZ_FILES if _load(p) is not None] + [
    p for p in _RELEASE_FILES if p.name not in NOT_LOADING and _load(p) is not None
]
FAILING_RELEASES = [p for p in _RELEASE_FILES if _load(p) is None]

_NOT_YET = pytest.mark.xfail(
    strict=True,
    reason="T-020: unedited entries are re-formatted on write, not kept as read",
)


def _corpus_params(xfail_ids=None):
    """Corpus parameters; those in `xfail_ids` (if given) are marked xfail."""
    out = []
    for p in CORPUS:
        marks = [_NOT_YET] if xfail_ids is not None and _id(p) in xfail_ids else []
        out.append(pytest.param(p, id=_id(p), marks=marks))
    return out


def _opcodes(src, out):
    a, b = src.split("\n"), out.split("\n")
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return a, b, [op for op in sm.get_opcodes() if op[0] != "equal"]


def _changed_lines(src, out):
    """(source lines changed or lost, output lines that differ)."""
    _, _, ops = _opcodes(src, out)
    return sum(i2 - i1 for _, i1, i2, _, _ in ops), sum(
        j2 - j1 for _, _, _, j1, j2 in ops
    )


def _reload(text, tmp_path, name="reloaded"):
    path = tmp_path / name
    path.write_text(text)
    d = _load(path)
    assert d is not None, f"the written text does not load:\n{text}"
    return d


# --------------------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------------------


def test_corpus_is_not_empty():
    # - 25 loading release files + 9 pitzDaily dictionaries on main
    assert len(CORPUS) >= 34


@pytest.mark.parametrize("name", sorted(NOT_LOADING))
def test_not_loading_file_still_fails_to_load(name):
    path = RELEASES / name
    assert path.is_file(), f"{name} is gone from tests/releases/"
    assert _load(path) is None, (
        f"{name} now loads ({NOT_LOADING[name]} landed?): remove it from NOT_LOADING; it "
        "then joins the corpus and must round-trip byte-identically"
    )


def test_every_release_file_that_fails_to_load_is_listed():
    unlisted = [p.name for p in FAILING_RELEASES if p.name not in NOT_LOADING]
    assert unlisted == [], (
        f"these files do not load; list them in NOT_LOADING: {unlisted}"
    )


@pytest.mark.parametrize("path", _corpus_params())
def test_unedited_write_equals_source(path):
    d = _load(path)
    assert d.toString() == _source(path)


@pytest.mark.parametrize("path", _corpus_params())
def test_unedited_write_changes_no_line(path):
    src = _source(path)
    lost, differ = _changed_lines(src, _load(path).toString())
    n_src = len(src.split("\n"))
    assert lost == 0, (
        f"{_id(path)}: {lost} of {n_src} source lines are changed or lost "
        f"({differ} output lines differ)"
    )


# - Files whose second write differs from the first today (the first write still normalizes
# - formatting, e.g. `libs ("lib.so");`, T-045); every other file already converges at once.
_CONVERGE_FAILS_TODAY = set()


@pytest.mark.parametrize("path", _corpus_params(_CONVERGE_FAILS_TODAY))
def test_second_write_equals_first(path, tmp_path):
    first = _load(path).toString()
    second = _reload(first, tmp_path, path.name).toString()
    assert second == first


# --------------------------------------------------------------------------------------
# tail and gaps (hand-written inputs)
# --------------------------------------------------------------------------------------

_HEAD = (
    "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
    "    class       dictionary;\n    object      t;\n}\n\n"
)

LAYOUTS = {
    "odd-padding": _HEAD + "a        1;\nbb   2;\n\n\n\nccc\t3;\n",
    "no-final-newline": _HEAD + "a 1;\nb 2;",
    "blank-lines-at-end": _HEAD + "a 1;\nb 2;\n\n\n",
    "padding-in-foamfile": "FoamFile\n{\n  version  2.0;\n  format   ascii;\n"
    "  class    dictionary;\n  object   t;\n}\n\na 1;\n",
    "list-on-one-line": _HEAD + "l  (1   2 3);\nw (a b);\n",
    "semicolon-after-block": _HEAD + "sub\n{\n    a  1;\n};\n",
    "one-line-block": _HEAD + "sub { a 1; b 2; }\nc  3;\n",
    "number-spelling": _HEAD + "t 1e-6;\nu 1e-2;\nv (0 0 0);\n",
}


@pytest.mark.parametrize("name", sorted(LAYOUTS))
def test_hand_written_layout_round_trips(name, tmp_path):
    d = _reload(LAYOUTS[name], tmp_path)
    assert d.toString() == LAYOUTS[name]


# --------------------------------------------------------------------------------------
# edits change only the lines of the edited top-level entry
# --------------------------------------------------------------------------------------


def _single_line_change(src, out, key, new_text):
    """Exactly one source line (`key ...;`) was replaced by one line holding `new_text`."""
    a, b, ops = _opcodes(src, out)
    assert len(ops) == 1, f"expected one changed hunk, got {ops}"
    tag, i1, i2, j1, j2 = ops[0]
    assert (tag, i2 - i1, j2 - j1) == ("replace", 1, 1), ops[0]
    assert a[i1].split()[0] == key
    assert new_text in b[j1].split()


@pytest.mark.parametrize(
    "path,key,new,new_text",
    [
        (PITZ / "system" / "controlDict", "endTime", 3000, "3000;"),
        (RELEASES / "foundation-11.controlDict", "endTime", 0.5, "0.5;"),
        (
            PITZ / "constant" / "transportProperties",
            "transportModel",
            "BirdCarreau",
            "BirdCarreau;",
        ),
    ],
    ids=["pitzDaily-endTime", "foundation-11-endTime", "pitzDaily-transportModel"],
)
def test_editing_a_scalar_entry_changes_only_its_line(path, key, new, new_text):
    src = _source(path)
    d = _load(path)
    d[key] = new
    _single_line_change(src, d.toString(), key, new_text)


@pytest.mark.parametrize(
    "name",
    [
        "foundation-14.helmholtzResonance.blockMeshDict",
        "esi-v2606.helmholtzResonance.blockMeshDict",
    ],
)
def test_editing_one_member_of_a_shared_line_regenerates_only_that_line(name):
    path = RELEASES / name
    src = _source(path)
    d = _load(path)
    d.x3 = 30
    a, b, ops = _opcodes(src, d.toString())
    shared = next(i for i, ln in enumerate(a) if ln.startswith("x1 "))
    assert all(i1 >= shared and i2 <= shared + 1 for _, i1, i2, _, _ in ops), ops
    # - one line per member (x1..x5), x3 with its new value
    written = [ln.split() for ln in b]
    for key, val in (
        ("x1", "14;"),
        ("x2", "6;"),
        ("x3", "30;"),
        ("x4", "6;"),
        ("x5", "4;"),
    ):
        assert [key, val] in [w[:2] for w in written], key
    assert "x3  20;" not in d.toString()


def test_editing_inside_a_top_level_sub_dict_regenerates_only_that_block():
    path = PITZ / "system" / "fvSolution"
    src = _source(path)
    d = _load(path)
    d.solvers.p.tolerance = 1e-5
    out = d.toString()
    start = src.index("solvers\n{")
    end = src.index("\n}\n", start) + len("\n}\n")
    assert out.startswith(src[:start]), "entries before the edited block changed"
    assert out.endswith(src[end:]), "entries after the edited block changed"
    block = out[len(src[:start]) : len(out) - len(src[end:])]
    assert block.startswith("solvers")
    assert "1e-05" in block or "1e-5" in block or "0.00001" in block
    assert block != src[start:end]


def test_deleting_an_entry_removes_only_its_lines_and_its_gap():
    path = PITZ / "system" / "controlDict"
    src = _source(path)
    d = _load(path)
    del d.deltaT
    gap_and_entry = "\ndeltaT          1;\n"
    assert src.count(gap_and_entry) == 1
    assert d.toString() == src.replace(gap_and_entry, "")


def test_deleting_a_member_of_a_shared_line_regenerates_the_others():
    path = RELEASES / "foundation-14.helmholtzResonance.blockMeshDict"
    src = _source(path)
    d = _load(path)
    del d.x2
    a, b, ops = _opcodes(src, d.toString())
    shared = next(i for i, ln in enumerate(a) if ln.startswith("x1 "))
    assert all(i1 >= shared and i2 <= shared + 1 for _, i1, i2, _, _ in ops), ops
    assert "x2" not in [ln.split()[0] for ln in b if ln.split()]


@pytest.mark.parametrize("name", ["controlDict-plain", "tail-without-newline"])
def test_a_new_entry_is_appended_before_the_tail(name, tmp_path):
    # - the source is kept up to the last entry; the new entry follows in today's style; the
    # - tail (here: blank lines, or none) stays last
    texts = {
        "controlDict-plain": _HEAD + "a        1;\nb   2;\n\n\n",
        "tail-without-newline": _HEAD + "a        1;\nb   2;",
    }
    src = texts[name]
    d = _reload(src, tmp_path)
    d.newEntry = 5
    out = d.toString()
    last = src.rstrip("\n")
    assert out.startswith(last), "the source entries changed"
    added = out[len(last) :]
    assert added.split() == ["newEntry", "5;"]
    # - the entry comes before the tail: trailing blank lines are not lost
    assert len(out) - len(out.rstrip("\n")) >= len(src) - len(last)


def test_editing_then_reverting_writes_the_source_again():
    path = PITZ / "system" / "controlDict"
    d = _load(path)
    d.endTime = 3000
    assert d.toString() != _source(path)
    d.endTime = 2000
    assert d.toString() == _source(path)


def test_editing_then_reverting_through_value_writes_the_source_again():
    path = PITZ / "system" / "controlDict"
    d = _load(path)
    d.endTime.value = 3000
    assert d.toString() != _source(path)
    d.endTime.value = 2000
    assert d.toString() == _source(path)


def test_edited_file_loads_with_the_new_value(tmp_path):
    d = _load(PITZ / "system" / "controlDict")
    d.endTime = 3000
    assert _reload(d.toString(), tmp_path).endTime.value == 3000


# --------------------------------------------------------------------------------------
# every way to edit is detected: the new value is written, never the old text.
# These pass today (everything is regenerated) and must keep passing.
# --------------------------------------------------------------------------------------

EDIT_SOURCE = (
    _HEAD
    + "scalar       10;\n"
    + "count        4;\n"
    + "word         alpha;\n"
    + "lst          (1   2 3);\n"
    + "grp          (1 2 3)  (4 5 6)  (7 8 9);\n"
    + "box          (0 0 0)   (1 2 3);\n"
    + "sub // air\n{\n    keep    1;\n    inner\n    {\n        y   1;\n    }\n}\n"
    + "other        1;\n"
)


@pytest.fixture
def edit_file(tmp_path):
    d = _reload(EDIT_SOURCE, tmp_path, "editSource")
    assert d.toString() is not None
    return d


def _written(d, tmp_path):
    """The written text and the dictionary read back from it."""
    out = d.toString()
    return out, _reload(out, tmp_path, "written")


def test_fixture_has_the_expected_types(edit_file):
    assert isinstance(edit_file.scalar, pt.ofInt)
    assert type(edit_file.grp) is pt.ofListGroups
    assert type(edit_file.box) is pt.ofBoundBox
    assert isinstance(edit_file.lst, pt.ofList)


def test_assignment_is_detected(edit_file, tmp_path):
    edit_file.scalar = 20
    out, back = _written(edit_file, tmp_path)
    assert back.scalar.value == 20
    assert "scalar       10;" not in out


def test_value_setter_is_detected(edit_file, tmp_path):
    edit_file.scalar.value = 21
    out, back = _written(edit_file, tmp_path)
    assert back.scalar.value == 21
    assert "scalar       10;" not in out


def test_word_assignment_is_detected(edit_file, tmp_path):
    edit_file.word = "beta"
    out, back = _written(edit_file, tmp_path)
    assert back.word.value == "beta"
    assert "alpha" not in out


def test_list_append_is_detected(edit_file, tmp_path):
    edit_file.lst.value.append(pt.ofInt(value=4))
    out, back = _written(edit_file, tmp_path)
    assert [x.value for x in back.lst.value] == [1, 2, 3, 4]
    assert "(1   2 3)" not in out


def test_list_item_replacement_is_detected(edit_file, tmp_path):
    edit_file.lst.value[1] = pt.ofInt(value=9)
    out, back = _written(edit_file, tmp_path)
    assert [x.value for x in back.lst.value] == [1, 9, 3]
    assert "(1   2 3)" not in out


def test_list_item_value_edit_is_detected(edit_file, tmp_path):
    edit_file.lst.value[2].value = 8
    out, back = _written(edit_file, tmp_path)
    assert [x.value for x in back.lst.value] == [1, 2, 8]
    assert "(1   2 3)" not in out


def test_list_groups_group_replacement_is_detected(edit_file, tmp_path):
    edit_file.grp.groups[1] = pt.ofList(value=[pt.ofInt(value=v) for v in (40, 50, 60)])
    out, back = _written(edit_file, tmp_path)
    assert [[x.value for x in g.value] for g in back.grp.groups] == [
        [1, 2, 3],
        [40, 50, 60],
        [7, 8, 9],
    ]
    assert "(4 5 6)" not in out


def test_list_groups_group_value_edit_is_detected(edit_file, tmp_path):
    edit_file.grp.groups[0].value = [pt.ofInt(value=v) for v in (10, 20, 30)]
    out, back = _written(edit_file, tmp_path)
    assert [[x.value for x in g.value] for g in back.grp.groups] == [
        [10, 20, 30],
        [4, 5, 6],
        [7, 8, 9],
    ]
    assert "(1 2 3)" not in out.split("grp")[1].split("box")[0]


def test_list_groups_item_edit_is_detected(edit_file, tmp_path):
    edit_file.grp.groups[2].value[1].value = 80
    out, back = _written(edit_file, tmp_path)
    assert [x.value for x in back.grp.groups[2].value] == [7, 80, 9]
    assert "(7 8 9)" not in out


def test_nested_assignment_is_detected(edit_file, tmp_path):
    edit_file.sub.inner.y = 2
    out, back = _written(edit_file, tmp_path)
    assert back.sub.inner.y.value == 2
    assert back.sub.keep.value == 1
    assert "y   1;" not in out


def test_new_key_in_sub_dict_is_detected(edit_file, tmp_path):
    edit_file.sub.added = 7
    _, back = _written(edit_file, tmp_path)
    assert back.sub.added.value == 7


def test_bound_box_value_setter_is_detected(edit_file, tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        edit_file.box.value = [[0, 0, 0], [2, 2, 2]]
    out, back = _written(edit_file, tmp_path)
    assert [[x.value for x in g.value] for g in back.box.groups] == [
        [0, 0, 0],
        [2, 2, 2],
    ]
    assert "(11 12 13)" not in out


def test_bound_box_group_edit_is_detected(edit_file, tmp_path):
    edit_file.box.groups[1].value = [pt.ofInt(value=v) for v in (5, 5, 5)]
    out, back = _written(edit_file, tmp_path)
    assert [x.value for x in back.box.groups[1].value] == [5, 5, 5]
    assert "(11 12 13)" not in out


def test_keyword_comment_change_is_detected(edit_file, tmp_path):
    edit_file.sub._comment_keyword = " water"
    out, _ = _written(edit_file, tmp_path)
    assert "water" in out
    assert "air" not in out


def test_int_to_equal_valued_float_is_detected(edit_file, tmp_path):
    # - (`d.count = 4.0` and `d.count.value = 4.0` coerce to an int today; an explicit ofFloat
    # - is the way to get 4.0 into the file)
    edit_file.count = pt.ofFloat(value=4.0)
    out, back = _written(edit_file, tmp_path)
    assert isinstance(back.count, pt.ofFloat)
    assert "count        4;" not in out


def test_deletion_is_detected(edit_file, tmp_path):
    del edit_file.other
    out, back = _written(edit_file, tmp_path)
    assert "other" not in out
    assert not hasattr(back, "other") or back.other is None


# --------------------------------------------------------------------------------------
# cache: init -> save -> load
# --------------------------------------------------------------------------------------

PITZ_DICTS = [
    ("0", "U"),
    ("0", "p"),
    ("constant", "momentumTransport"),
    ("constant", "transportProperties"),
    ("system", "blockMeshDict"),
    ("system", "controlDict"),
    ("system", "fvSchemes"),
    ("system", "fvSolution"),
    ("system", "setFieldsDict"),
]


def _case_dict(c, folder, name):
    # - the folder "0" is stored as `t_0`
    return c["t_0" if folder == "0" else folder][name]


@pytest.mark.parametrize("folder,name", PITZ_DICTS, ids=lambda v: v)
def test_cache_round_trip_writes_the_source(case, folder, name):
    pf.init(path=case).save(path=case)
    loaded = pf.load(path=case)
    assert _case_dict(loaded, folder, name).toString() == _source(case / folder / name)


def test_init_without_cache_writes_the_source(case):
    c = pf.init(path=case)
    assert c.system.controlDict.toString() == _source(case / "system" / "controlDict")


def test_edit_after_cache_load_is_written(case):
    pf.init(path=case).save(path=case)
    c = pf.load(path=case)
    c.system.controlDict.endTime = 500
    out = c.system.controlDict.toString()
    assert re.search(r"^endTime\s+500;$", out, re.M)
    assert "2000" not in out


def test_nested_edit_after_cache_load_is_written(case):
    pf.init(path=case).save(path=case)
    c = pf.load(path=case)
    c.system.fvSolution.solvers.p.relTol = 0.25
    out = c.system.fvSolution.toString()
    assert "0.25" in out


def test_list_edit_after_cache_load_is_written(case):
    pf.init(path=case).save(path=case)
    c = pf.load(path=case)
    c.system.controlDict.cacheTemporaryObjects.value.append(
        pt.ofWord(value="extraField")
    )
    assert "extraField" in c.system.controlDict.toString()


def test_edit_after_cache_load_changes_only_that_line(case):
    src = _source(case / "system" / "controlDict")
    pf.init(path=case).save(path=case)
    c = pf.load(path=case)
    c.system.controlDict.endTime = 500
    _single_line_change(src, c.system.controlDict.toString(), "endTime", "500;")


def test_written_case_files_equal_the_source_after_load(case):
    sources = {(f, n): _source(case / f / n) for f, n in PITZ_DICTS}
    pf.init(path=case).save(path=case)
    pf.load(path=case).write()
    for (folder, name), src in sources.items():
        assert _source(case / folder / name) == src, f"{folder}/{name}"


# --------------------------------------------------------------------------------------
# the private hook for T-050, groups, the cache record and the "new" paths
# --------------------------------------------------------------------------------------

REGENERATED = [
    PITZ / "system" / "controlDict",
    PITZ / "system" / "fvSolution",
    RELEASES / "foundation-14.helmholtzResonance.blockMeshDict",
    RELEASES / "foundation-11.damBreak.fvSchemes",
]


@pytest.mark.parametrize(
    "path", REGENERATED, ids=lambda p: p.parent.name + "." + p.name
)
def test_preserve_false_gives_the_regenerated_style(path):
    # - the golden files were written with the writer of origin/main (before T-020a)
    from conftest import assert_golden

    name = (
        "pitzDaily." + path.parent.name + "." if PITZ in path.parents else ""
    ) + path.name
    assert_golden(f"regenerated/{name}.txt", _load(path).toString(_preserve=False))


@pytest.mark.parametrize(
    "path", REGENERATED, ids=lambda p: p.parent.name + "." + p.name
)
def test_preserve_false_ignores_the_record_after_the_source_changed(path):
    d = _load(path)
    assert d.toString(_preserve=False) != d.toString()
    d._srcLayout = None
    assert d.toString(_preserve=False) == d.toString()


def test_a_regenerated_shared_line_group_keeps_its_gap(tmp_path):
    src = _HEAD + "a 1;\n\n\nx1  14; x2   6;\nb  3;\n"
    d = _reload(src, tmp_path)
    assert d.toString() == src
    d.x2 = 7
    assert (
        d.toString()
        == _HEAD
        + "a 1;\n\n\n"
        + d.x1.toString(ofRep=True)
        + d.x2.toString(ofRep=True)
        + "b  3;\n"
    )


def test_deleting_the_first_member_of_a_group_regenerates_the_others(tmp_path):
    src = _HEAD + "a 1;\n\nx1  14; x2   6;\nb  3;\n"
    d = _reload(src, tmp_path)
    del d.x1
    out = d.toString()
    assert out.endswith("b  3;\n")
    assert [ln.split() for ln in out.split("\n") if ln.startswith("x")] == [
        ["x2", "6;"]
    ]
    assert "x2   6;" not in out


def test_src_layout_is_json_serialisable_and_survives_a_round_trip():
    import json

    path = PITZ / "system" / "fvSolution"
    d = _load(path)
    layout = d._srcLayout
    assert json.loads(json.dumps(layout)) == layout
    # - what the cache loader does: construct without arguments, then set every attribute
    fresh = pt.ofDictFile()
    for key, value in d.__dict__.items():
        if key == "_srcLayout":
            value = json.loads(json.dumps(value))
        setattr(fresh, key, value)
    assert fresh.toString() == _source(path)
    fresh.solvers.p.tolerance = 1e-3
    assert fresh.toString() != _source(path)


def test_a_dictionary_without_a_record_is_written_in_the_standard_style():
    d = pt.ofDictFile(_name="t")
    d.a = 1
    d.b = "word"
    assert d.toString() == d.toString(_preserve=False)
    assert d._srcLayout is None


def test_deleting_a_key_and_adding_it_again_writes_the_new_entry_anew(tmp_path):
    src = _HEAD + "a        1;\nb   2;\n"
    d = _reload(src, tmp_path)
    del d.a
    d.a = 5
    out = d.toString()
    assert "a        1;" not in out
    assert out.endswith(
        "\n" + pt.ofInt(name="a", value=5).toString(ofRep=True).rstrip("\n") + "\n"
    )
    assert _reload(out, tmp_path, "again").a.value == 5


def test_an_entry_object_copied_into_another_file_does_not_bring_its_text(tmp_path):
    one = _reload(_HEAD + "a        1;\n", tmp_path, "one")
    two = _reload(_HEAD + "b   2;\n", tmp_path, "two")
    two.a = one.a
    out = two.toString()
    assert "a        1;" not in out
    assert out.startswith(_HEAD + "b   2;\n")
    assert out.split()[-2:] == ["a", "1;"]
    # - under a key that has a record, an equal value keeps the target's own text
    two.b = pt.ofInt(name="b", value=2)
    assert two.toString().startswith(_HEAD + "b   2;\n")


def test_a_new_key_goes_before_the_tail_after_a_reordering(tmp_path):
    src = _HEAD + "a 1;\n\nb 2;\n\n\n"
    d = _reload(src, tmp_path)
    d.c = 3
    out = d.toString()
    assert out.startswith(src.rstrip("\n"))
    assert out.endswith("\n\n\n")
    assert out.index("c") < len(out.rstrip("\n"))


def test_a_file_without_a_foamfile_block_round_trips(tmp_path):
    header = (
        "/*--------------------------------*- C++ -*----------------------------------*\\\n"
        "| =========                 |                                                 |\n"
        "\\*---------------------------------------------------------------------------*/\n"
    )
    src = header + "\n// note\nx   1;\n\ny  2;\n"
    d = _reload(src, tmp_path)
    assert d.toString() == src
    d.y = 3
    assert d.toString().startswith(header + "\n// note\nx   1;\n\n")


def test_layout_is_kept_for_a_deep_copy():
    import copy

    path = PITZ / "system" / "controlDict"
    d = _load(path)
    assert copy.deepcopy(d).toString() == _source(path)
