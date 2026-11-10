"""A fractional value given to an integer entry is kept as a float, with a warning (T-086).

Specification tests for docs/tickets/T-086-warn-on-int-truncation.md (issue #114, option B).
`d.deltaT.value = 0.001` on an `ofInt` used to store `0` silently.  Now the entry is changed
in place into an `ofFloat` holding the exact value, one `WARNING:` line is printed through
`userMsg`, and values that are not numbers raise `FoamKitError` naming the entry.

How the warning is captured: `userMsg(msg, 'WARNING')` prints one `WARNING: ...` line to
stdout through the rich console, so the tests use `capsys` and count `WARNING:` occurrences
(the rich console may wrap a long line, so the output is whitespace-normalised first).

Tests of bad values go
through `_error_of`, which turns "no error" and "a bare ValueError/KeyError/..." into an
AssertionError, so a bare exception from the code under test cannot count as the expected
failure by accident.
"""

import copy
import difflib
import pickle
import re
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pytest

import foamkit.functions as pf
import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import FIXTURES
from test_directives import HEADER
from test_preserve_layout import CORPUS, _id
from test_several_lists_value import CONTAINERS, _scope, _wrap

PITZ = FIXTURES / "pitzDaily"

BODY = "count 4;\nx 1.5;\nflag on;\nl (1 2 3);\ng (1 2) (3 4);\nbox (0 0 0) (1 2 3);\n"


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------


def _read(tmp_path, body, cont, name="case"):
    path = tmp_path / name
    path.write_text(HEADER + _wrap(body, cont))
    return fkt.DictFileParser(path).readDictFile()


def _out(capsys):
    """Everything printed so far, whitespace-normalised (rich may wrap long lines)."""
    return " ".join(capsys.readouterr().out.split())


def _warning_count(out):
    return out.count("WARNING:")


def _mentions_value(out, given):
    """The warning names the value given (as written, or as the float that is stored)."""
    return str(given) in out or repr(float(given)) in out


def _error_of(entry, value):
    """The FoamKitError raised by `entry.value = value`.

    "No error" and a bare exception are both reported as AssertionError."""
    try:
        entry.value = value
    except FoamKitError as err:
        return err
    except Exception as err:  # noqa: BLE001 - the point is to report any bare exception
        raise AssertionError(f"bare {type(err).__name__}: {err}") from None
    raise AssertionError(f"no error; the entry now holds {entry.value!r}")


def _set(entry, value):
    """`entry.value = value`; a bare exception (today: ValueError for '4.5') is an AssertionError."""
    try:
        entry.value = value
    except Exception as err:  # noqa: BLE001
        raise AssertionError(f"bare {type(err).__name__}: {err}") from None


FRACTIONAL = [
    pytest.param(4.5, id="float-4.5"),
    pytest.param(4.000000001, id="float-4.000000001"),
    pytest.param(np.float64(4.5), id="np.float64-4.5"),
    pytest.param(Decimal("4.5"), id="Decimal-4.5"),
    pytest.param(Fraction(9, 2), id="Fraction-9/2"),
    pytest.param("4.5", id="str-4.5"),
]

# - values that are whole numbers: stay ofInt, silently
WHOLE = [
    pytest.param(4.0, id="float-4.0"),
    pytest.param("4", id="str-4"),
    pytest.param(np.int64(4), id="np.int64-4"),
    pytest.param(4, id="int-4"),
]


# --------------------------------------------------------------------------------------
# named entry: `.value = <fractional>`
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize("v", FRACTIONAL)
def test_fractional_value_makes_the_same_entry_an_offloat(tmp_path, capsys, cont, v):
    d = _read(tmp_path, BODY, cont)
    entry = _scope(d, cont).count
    capsys.readouterr()
    _set(entry, v)
    assert type(entry) is fkt.ofFloat
    assert _scope(d, cont).count is entry
    assert entry._type == "ofFloat"


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize("v", FRACTIONAL)
def test_fractional_value_is_stored_exactly(tmp_path, cont, v):
    d = _read(tmp_path, BODY, cont)
    entry = _scope(d, cont).count
    _set(entry, v)
    assert entry.value == float(v)


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize("v", FRACTIONAL)
def test_fractional_value_is_written_exactly(tmp_path, cont, v):
    d = _read(tmp_path, BODY, cont)
    _set(_scope(d, cont).count, v)
    assert re.search(rf"^\s*count\s+{re.escape(repr(float(v)))};$", d.toString(), re.M)


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize("v", FRACTIONAL)
def test_fractional_value_prints_exactly_one_warning_naming_entry_and_value(
    tmp_path, capsys, cont, v
):
    d = _read(tmp_path, BODY, cont)
    capsys.readouterr()
    _set(_scope(d, cont).count, v)
    out = _out(capsys)
    assert _warning_count(out) == 1, out
    assert "count" in out
    assert _mentions_value(out, v), out
    assert "float" in out.lower()


@pytest.mark.parametrize("cont", CONTAINERS)
def test_fractional_edit_leaves_the_other_entries_alone(tmp_path, cont):
    """Guard (passes today and after): neighbours keep their type and value."""
    d = _read(tmp_path, BODY, cont)
    _scope(d, cont).count.value = 4.5
    s = _scope(d, cont)
    assert (type(s.x), s.x.value) == (fkt.ofFloat, 1.5)
    assert type(s.flag) is fkt.ofBool


# --------------------------------------------------------------------------------------
# constructors
# --------------------------------------------------------------------------------------

CONSTRUCTORS = [
    pytest.param(lambda: fkt.ofInt(value=4.5), None, id="keyword-value"),
    pytest.param(lambda: fkt.ofInt("n", 4.5), "n", id="name-and-value"),
]


@pytest.mark.parametrize("make,name", CONSTRUCTORS)
def test_constructor_with_fractional_value_returns_an_offloat(capsys, make, name):
    obj = make()
    assert type(obj) is fkt.ofFloat
    assert obj.value == 4.5
    assert obj._type == "ofFloat"


@pytest.mark.parametrize("make,name", CONSTRUCTORS)
def test_constructor_with_fractional_value_prints_one_warning(capsys, make, name):
    make()
    out = _out(capsys)
    assert _warning_count(out) == 1, out
    assert "4.5" in out
    if name is not None:
        assert name in out


# --------------------------------------------------------------------------------------
# list items and group items
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("cont", CONTAINERS)
def test_list_item_becomes_an_offloat_in_place_and_is_written(tmp_path, cont):
    d = _read(tmp_path, BODY, cont)
    holder = _scope(d, cont).l
    item = holder.value[0]
    assert type(item) is fkt.ofInt
    item.value = 2.5
    assert type(item) is fkt.ofFloat
    assert holder.value[0] is item
    assert item.value == 2.5
    assert re.search(r"^\s*l\s*\(\s*2\.5\s+2\s+3\s*\);$", d.toString(), re.M)


@pytest.mark.parametrize("cont", CONTAINERS)
def test_list_item_prints_one_warning_for_an_unnamed_item(tmp_path, capsys, cont):
    d = _read(tmp_path, BODY, cont)
    capsys.readouterr()
    _scope(d, cont).l.value[0].value = 2.5
    out = _out(capsys)
    assert _warning_count(out) == 1, out
    assert "Integer list item" in out
    assert "2.5" in out


@pytest.mark.parametrize("cont", CONTAINERS)
def test_list_groups_item_becomes_an_offloat_in_place_and_is_written(tmp_path, cont):
    d = _read(tmp_path, BODY, cont)
    group = _scope(d, cont).g.groups[0]
    item = group.value[0]
    assert type(item) is fkt.ofInt
    item.value = 2.5
    assert type(item) is fkt.ofFloat
    assert _scope(d, cont).g.groups[0].value[0] is item
    assert item.value == 2.5
    assert re.search(r"^\s*g\s+\(2\.5 2\) \(3 4\);$", d.toString(), re.M)


@pytest.mark.parametrize("cont", CONTAINERS)
def test_bound_box_item_becomes_an_offloat_in_place_and_is_written(tmp_path, cont):
    d = _read(tmp_path, BODY, cont)
    box = _scope(d, cont).box
    item = box.groups[1].value[0]
    assert type(item) is fkt.ofInt
    item.value = 2.5
    assert type(item) is fkt.ofFloat
    assert _scope(d, cont).box.groups[1].value[0] is item
    assert item.value == 2.5
    assert re.search(r"^\s*box\s+\(0 0 0\) \(2\.5 2 3\);$", d.toString(), re.M)


@pytest.mark.parametrize("cont", CONTAINERS)
def test_bound_box_other_group_keeps_its_source_text(tmp_path, cont):
    d = _read(tmp_path, "box (0.0 0 0e0) (1 2 3);\n", cont)
    _scope(d, cont).box.groups[1].value[0].value = 2.5
    assert re.search(r"^\s*box\s+\(0\.0 0 0e0\) \(2\.5 2 3\);$", d.toString(), re.M), (
        d.toString()
    )


@pytest.mark.parametrize("which", ["g", "box"])
@pytest.mark.parametrize("cont", CONTAINERS)
def test_group_item_prints_one_warning_for_an_unnamed_item(
    tmp_path, capsys, cont, which
):
    d = _read(tmp_path, BODY, cont)
    capsys.readouterr()
    getattr(_scope(d, cont), which).groups[1].value[0].value = 2.5
    out = _out(capsys)
    assert _warning_count(out) == 1, out
    assert "Integer list item" in out
    assert "2.5" in out


# --------------------------------------------------------------------------------------
# silent rows
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize("v", WHOLE)
def test_whole_value_stays_an_ofint_silently(tmp_path, capsys, cont, v):
    d = _read(tmp_path, BODY, cont)
    entry = _scope(d, cont).count
    capsys.readouterr()
    entry.value = v
    assert type(entry) is fkt.ofInt
    assert entry.value == 4
    assert type(entry.value) is int
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("cont", CONTAINERS)
def test_whole_list_item_stays_an_ofint_silently(tmp_path, capsys, cont):
    d = _read(tmp_path, BODY, cont)
    item = _scope(d, cont).l.value[0]
    capsys.readouterr()
    item.value = 2.0
    assert type(item) is fkt.ofInt
    assert item.value == 2
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("path", CORPUS, ids=_id)
def test_loading_and_writing_the_corpus_prints_no_warning(path, capsys):
    capsys.readouterr()
    fkt.DictFileParser(path).readDictFile().toString()
    out = capsys.readouterr().out
    assert "WARNING:" not in out


def test_init_save_load_of_pitzdaily_prints_no_warning(case, capsys):
    capsys.readouterr()
    pf.init(path=case).save(path=case)
    pf.load(path=case)
    assert "WARNING:" not in capsys.readouterr().out


# --------------------------------------------------------------------------------------
# `_parseValue`: exact integrality, no isclose tolerance
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("cont", CONTAINERS)
def test_assigning_a_nearly_whole_float_stores_an_offloat_silently(
    tmp_path, capsys, cont
):
    d = _read(tmp_path, BODY, cont)
    capsys.readouterr()
    _scope(d, cont).count = 4.000000001
    entry = _scope(d, cont).count
    assert type(entry) is fkt.ofFloat
    assert entry.value == 4.000000001
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("cont", CONTAINERS)
def test_assigning_a_list_with_a_nearly_whole_item_stores_an_offloat_item(
    tmp_path, capsys, cont
):
    d = _read(tmp_path, BODY, cont)
    capsys.readouterr()
    _scope(d, cont).l = [1, 4.000000001]
    items = _scope(d, cont).l.value
    assert [type(i) for i in items] == [fkt.ofInt, fkt.ofFloat]
    assert items[1].value == 4.000000001
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize(
    "v,cls", [(4.0, fkt.ofInt), (4.5, fkt.ofFloat), (4, fkt.ofInt)]
)
def test_assigning_a_value_keeps_the_exact_type_rule(tmp_path, capsys, cont, v, cls):
    """Guard (passes today and after): whole numbers are ints, the rest floats."""
    d = _read(tmp_path, BODY, cont)
    _scope(d, cont).count = v
    assert type(_scope(d, cont).count) is cls
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------------------
# bool, and values that are not numbers
# --------------------------------------------------------------------------------------

BAD = [
    # (id, entry name, kind of entry, value)
    pytest.param("count", True, id="ofInt-True"),
    pytest.param("count", False, id="ofInt-False"),
    pytest.param("count", "abc", id="ofInt-abc"),
    pytest.param("count", float("nan"), id="ofInt-nan"),
    pytest.param("count", float("inf"), id="ofInt-inf"),
    pytest.param("count", [1], id="ofInt-list"),
    pytest.param("x", True, id="ofFloat-True"),
    pytest.param("x", False, id="ofFloat-False"),
    pytest.param("x", "abc", id="ofFloat-abc"),
    pytest.param("x", "1.5x", id="ofFloat-1.5x"),
    pytest.param("flag", 2, id="ofBool-2"),
    pytest.param("flag", 0, id="ofBool-0"),
    pytest.param("flag", 1.0, id="ofBool-1.0"),
    pytest.param("flag", "maybe", id="ofBool-maybe"),
]


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize("name,v", BAD)
def test_bad_value_raises_foamkiterror_naming_the_entry(tmp_path, cont, name, v):
    d = _read(tmp_path, BODY, cont)
    err = _error_of(getattr(_scope(d, cont), name), v)
    assert name in str(err)


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize("name,v", BAD)
def test_bad_value_keeps_the_old_value_and_class(tmp_path, capsys, cont, name, v):
    d = _read(tmp_path, BODY, cont)
    entry = getattr(_scope(d, cont), name)
    cls, old = type(entry), entry.value
    before = d.toString()
    _error_of(entry, v)
    assert type(entry) is cls
    assert entry.value == old
    assert type(entry.value) is type(old)
    assert d.toString() == before


def test_bad_ofbool_value_error_lists_the_accepted_words(tmp_path):
    d = _read(tmp_path, BODY, "top")
    err = _error_of(d.flag, "maybe")
    assert "on" in str(err) and "false" in str(err)


def test_bool_on_ofint_suggests_assigning_to_the_dict(tmp_path):
    d = _read(tmp_path, BODY, "top")
    err = _error_of(d.count, True)
    assert "d.count = True" in str(err) or "count = True" in str(err)


def test_valid_ofbool_values_still_work(tmp_path):
    """Guard (passes today and after): True/False and the OpenFOAM words are accepted."""
    d = _read(tmp_path, BODY, "top")
    d.flag.value = False
    assert d.flag.value is False
    d.flag.value = "yes"
    assert d.flag.value is True


# --------------------------------------------------------------------------------------
# the real pitzDaily controlDict
# --------------------------------------------------------------------------------------


def _pitz_controldict():
    return fkt.DictFileParser(PITZ / "system" / "controlDict").readDictFile()


def _pitz_source():
    return (PITZ / "system" / "controlDict").read_text(encoding="utf-8")


def test_pitzdaily_deltat_is_an_ofint_today():
    """Guard: the premise of the ticket."""
    d = _pitz_controldict()
    assert type(d.deltaT) is fkt.ofInt
    assert d.deltaT.value == 1


def test_pitzdaily_deltat_is_written_with_the_exact_value_and_only_that_line_changes():
    d = _pitz_controldict()
    d.deltaT.value = 0.001
    out = d.toString()
    assert re.search(r"^deltaT\s+0\.001;$", out, re.M), out
    a, b = _pitz_source().split("\n"), out.split("\n")
    ops = [
        op
        for op in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
        if op[0] != "equal"
    ]
    assert len(ops) == 1, ops
    tag, i1, i2, j1, j2 = ops[0]
    assert (i2 - i1, j2 - j1) == (1, 1)
    assert a[i1].startswith("deltaT")


def test_pitzdaily_deltat_prints_one_warning(capsys):
    d = _pitz_controldict()
    capsys.readouterr()
    d.deltaT.value = 0.001
    out = _out(capsys)
    assert _warning_count(out) == 1, out
    assert "deltaT" in out
    assert "0.001" in out


def test_pitzdaily_deltat_is_an_offloat_after_reading_the_written_file(tmp_path):
    d = _pitz_controldict()
    d.deltaT.value = 0.001
    path = tmp_path / "controlDict"
    path.write_text(d.toString())
    again = fkt.DictFileParser(path).readDictFile()
    assert type(again.deltaT) is fkt.ofFloat
    assert again.deltaT.value == 0.001


def test_pitzdaily_deltat_survives_save_and_load(case):
    c = pf.init(path=case)
    c.system.controlDict.deltaT.value = 0.001
    c.save(path=case)
    loaded = pf.load(path=case)
    entry = loaded.system.controlDict.deltaT
    assert type(entry) is fkt.ofFloat
    assert entry.value == 0.001
    assert re.search(r"^deltaT\s+0\.001;$", loaded.system.controlDict.toString(), re.M)


def test_pitzdaily_deltat_edit_after_cache_load_is_written(case):
    pf.init(path=case).save(path=case)
    c = pf.load(path=case)
    c.system.controlDict.deltaT.value = 0.001
    assert re.search(r"^deltaT\s+0\.001;$", c.system.controlDict.toString(), re.M)


@pytest.mark.parametrize(
    "copier", [copy.deepcopy, lambda o: pickle.loads(pickle.dumps(o))]
)
def test_changed_entry_survives_deepcopy_and_pickle(copier):
    d = _pitz_controldict()
    d.deltaT.value = 0.001
    clone = copier(d.deltaT)
    assert type(clone) is fkt.ofFloat
    assert clone.value == 0.001
