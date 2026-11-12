"""`.value = None` writes the keyword-only entry `count;` with a warning (T-087, issue #115).

Specification tests for docs/tickets/T-087-value-none-writes-keyword-only.md (maintainer
decision: `.value = None` writes `count;` and raises a warning).  The entry keeps its class
and key, reads `.value is None`, prints exactly one `WARNING:` line naming it (`userMsg`
prints through rich to stdout, so `capsys` captures it), and is written `name;` (indented in
a sub-dictionary, no padding, a `// comment` kept).  `d.count = None` on a value entry does
the same on the same object; a new key, a sub-dictionary and a list item raise
`FoamKitError` and change nothing.  Written text is read back as an `ofWord` under
`unnamed_<n>` and written again unchanged.

A bare exception and "no exception" are reported as `AssertionError` by the helpers, so
every failing test fails with `AssertionError`.

Rows that are not reachable from a file are built with the constructors: `ofList` and
`ofVector` (a loaded list is an `ofSplitList`), and the tensor types (they only take
`value=`; the name is set afterwards, and their writers are broken for other reasons, so
only the setter is tested for them).  The dimensioned vector and tensor types of the ticket
cannot be built with a name and a value today and are not tested (see the report).
"""

import json
import re

import pytest

import foamkit.functions as pf
import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import FIXTURES, TESTS
from test_directives import HEADER
from test_several_lists_value import _load

PITZ = FIXTURES / "pitzDaily"
RELEASES = TESTS / "releases"

# id -> (source line of the entry `k`, class name)
LOADED = {
    "int": ("k 4;", "ofInt"),
    "float": ("k 1.5;", "ofFloat"),
    "str": ("k abc;", "ofStr"),
    "str-quoted": ('k "q";', "ofStr"),
    "bool": ("k on;", "ofBool"),
    "var": ("k $a;", "ofVar"),
    "split-list": ("k (1 2 3);", "ofSplitList"),
    "list-groups": ("k (1 2) (3 4);", "ofListGroups"),
    "bound-box": ("k (0 0 0) (1 2 3);", "ofBoundBox"),
    "dimensioned-scalar": ("k [0 2 -1 0 0 0 0] 1e-05;", "ofDimensionedScalar"),
    "uniform-field": ("k uniform (0 0 0);", "ofUniformField"),
}

# id -> (factory of an entry named `k`, class name)
BUILT = {
    "list": (lambda: fkt.ofList(name="k", value=[1, 2]), "ofList"),
    "vector": (lambda: fkt.ofVector(name="k", value=[1, 0, 0]), "ofVector"),
}
TENSORS = {
    "spherical-tensor": (fkt.ofSphericalTensor, [2]),
    "symm-tensor": (fkt.ofSymmTensor, [1, 0, 0, 1, 0, 1]),
    "tensor": (fkt.ofTensor, [1, 0, 0, 0, 1, 0, 0, 0, 1]),
}
WHERE = ["top", "sub"]
ROWS = list(LOADED) + list(BUILT)


# test name -> parameter ids that fail today (None: the test has no parameters)
XFAIL = {
    "test_value_none_keeps_class_key_and_reads_none": {
        "var-top",
        "var-sub",
        "split-list-top",
        "split-list-sub",
        "list-groups-top",
        "list-groups-sub",
        "bound-box-top",
        "bound-box-sub",
        "list-top",
        "list-sub",
        "vector-top",
        "vector-sub",
    },
    "test_value_none_prints_exactly_one_warning_naming_the_entry": {
        "int-top",
        "int-sub",
        "float-top",
        "float-sub",
        "str-top",
        "str-sub",
        "str-quoted-top",
        "str-quoted-sub",
        "bool-top",
        "bool-sub",
        "var-top",
        "var-sub",
        "split-list-top",
        "split-list-sub",
        "list-groups-top",
        "list-groups-sub",
        "bound-box-top",
        "bound-box-sub",
        "dimensioned-scalar-top",
        "dimensioned-scalar-sub",
        "uniform-field-top",
        "uniform-field-sub",
        "list-top",
        "list-sub",
        "vector-top",
        "vector-sub",
    },
    "test_value_none_is_written_as_a_keyword_only_entry": {
        "int-top",
        "int-sub",
        "float-top",
        "float-sub",
        "str-top",
        "str-sub",
        "str-quoted-top",
        "str-quoted-sub",
        "bool-top",
        "bool-sub",
        "var-top",
        "var-sub",
        "split-list-top",
        "split-list-sub",
        "list-groups-top",
        "list-groups-sub",
        "bound-box-top",
        "bound-box-sub",
        "dimensioned-scalar-top",
        "dimensioned-scalar-sub",
        "uniform-field-top",
        "uniform-field-sub",
        "list-top",
        "list-sub",
        "vector-top",
        "vector-sub",
    },
    "test_value_none_keeps_a_trailing_comment": {
        "int-top",
        "int-sub",
        "float-top",
        "float-sub",
        "str-top",
        "str-sub",
        "str-quoted-top",
        "str-quoted-sub",
        "bool-top",
        "bool-sub",
        "var-top",
        "var-sub",
        "split-list-top",
        "split-list-sub",
        "list-groups-top",
        "list-groups-sub",
        "bound-box-top",
        "bound-box-sub",
        "dimensioned-scalar-top",
        "dimensioned-scalar-sub",
        "uniform-field-top",
        "uniform-field-sub",
    },
    "test_value_none_leaves_the_neighbours_unchanged": {
        "bound-box-top",
        "bound-box-sub",
    },
    "test_tensor_value_none_keeps_class_and_reads_none_with_one_warning": {
        "spherical-tensor",
        "symm-tensor",
        "tensor",
    },
    "test_assigning_none_to_an_entry_acts_like_value_none_on_the_same_object": {
        "int-top",
        "int-sub",
        "float-top",
        "float-sub",
        "str-top",
        "str-sub",
        "str-quoted-top",
        "str-quoted-sub",
        "bool-top",
        "bool-sub",
        "var-top",
        "var-sub",
        "split-list-top",
        "split-list-sub",
        "list-groups-top",
        "list-groups-sub",
        "bound-box-top",
        "bound-box-sub",
        "dimensioned-scalar-top",
        "dimensioned-scalar-sub",
        "uniform-field-top",
        "uniform-field-sub",
        "list-top",
        "list-sub",
        "vector-top",
        "vector-sub",
    },
    "test_assigning_none_twice_warns_once": {
        "top",
        "sub",
    },
    "test_assigning_none_to_a_new_key_raises_and_changes_nothing": {
        "top",
        "sub",
    },
    "test_assigning_none_to_a_sub_dictionary_raises_and_keeps_it": None,
    "test_assigning_none_to_a_missing_value_entry_of_a_sub_dictionary_raises": None,
    "test_none_for_a_list_item_raises_and_keeps_the_old_value": {
        "top",
        "sub",
    },
    "test_written_keyword_only_entry_reads_back_and_writes_the_same_text": {
        "int-top",
        "int-sub",
        "float-top",
        "float-sub",
        "str-top",
        "str-sub",
        "str-quoted-top",
        "str-quoted-sub",
        "var-top",
        "var-sub",
        "split-list-top",
        "split-list-sub",
        "bound-box-top",
        "bound-box-sub",
        "dimensioned-scalar-top",
        "dimensioned-scalar-sub",
        "uniform-field-top",
        "uniform-field-sub",
        "list-top",
        "list-sub",
        "vector-top",
        "vector-sub",
    },
    "test_pitzdaily_delta_t_none_survives_save_load_and_is_written": None,
    "test_pitzdaily_write_without_save_gives_the_same_deltat_line": None,
    "test_built_entry_without_a_value_is_written_keyword_only_and_silent": None,
    "test_cache_load_accepts_a_null_value_for_a_list": {
        "ofList",
        "ofSplitList",
    },
}


@pytest.fixture(autouse=True)
def _expected_failure(request):
    """Mark the rows that fail until T-087 is implemented (strict: they must start passing)."""
    ids = XFAIL.get(request.node.originalname, ())
    callspec = getattr(request.node, "callspec", None)
    if ids is None or (callspec is not None and callspec.id in ids):
        request.applymarker(
            pytest.mark.xfail(
                strict=True, raises=AssertionError, reason="T-087: not implemented yet"
            )
        )


# --- helpers ------------------------------------------------------------------------------


def _call(fn):
    """Run `fn`; a bare (non-FoamKit) exception becomes an AssertionError."""
    try:
        return fn()
    except FoamKitError:
        raise
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"bare {type(e).__name__}: {str(e)[:100]!r}") from e


def _any(fn):
    """Run `fn`; any exception (a loud FoamKitError too) becomes an AssertionError."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"{type(e).__name__}: {str(e)[:100]!r}") from e


def _expect_error(fn):
    """The FoamKitError raised by `fn`; AssertionError if nothing or a bare exception."""
    try:
        fn()
    except FoamKitError as e:
        return e
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"bare {type(e).__name__}: {str(e)[:100]!r}") from e
    raise AssertionError("no FoamKitError was raised")


def _sub(body):
    lines = "".join("    " + ln + "\n" for ln in body.split("\n"))
    return "s\n{\n" + lines + "}\n"


def _src(where, line):
    """File text with the entry `line` (and a neighbour) at the top level or in `s`."""
    body = "a 1;\n" + line + "\nb 2;"
    return HEADER + (body + "\n" if where == "top" else _sub(body))


def _path(tmp_path, text, name="src"):
    path = tmp_path / name
    path.write_bytes(text.encode())
    return path


def _holder(d, where):
    return d if where == "top" else d.s


def _make(tmp_path, where, row, comment=""):
    """(dictionary, holder, entry `k`) of a loaded or built row."""
    if row in LOADED:
        d = _load(_path(tmp_path, _src(where, LOADED[row][0] + comment)))
        return d, _holder(d, where), _holder(d, where).k
    d = _load(_path(tmp_path, _src(where, "z 3;" + comment)))
    entry = BUILT[row][0]()
    _holder(d, where).update(entry)
    return d, _holder(d, where), _holder(d, where).k


def _class(row):
    return (LOADED.get(row) or BUILT[row])[1]


def _line(where, key="k", tail=""):
    return re.compile(
        rf"^{'' if where == 'top' else '    '}{key};{re.escape(tail)}$", re.MULTILINE
    )


def _warnings(capsys):
    """The warning text printed so far (whitespace folded), and how many there were."""
    out = " ".join(capsys.readouterr().out.split())
    return out, out.count("WARNING:")


def _keys(d):
    return [k for k in d.__dict__ if not k.startswith("_")]


# --- sanity: the capture sees userMsg -------------------------------------------------------


def test_user_message_warning_is_captured_by_capsys(capsys):
    import foamkit

    foamkit.userMsg("probe", "WARNING")
    assert _warnings(capsys) == ("WARNING: probe", 1)


# --- `.value = None`: class and key kept, value None, one warning, written `k;` -----------


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize("row", ROWS)
def test_value_none_keeps_class_key_and_reads_none(tmp_path, where, row):
    d, holder, entry = _make(tmp_path, where, row)
    _any(lambda: setattr(entry, "value", None))
    assert holder.k is entry and type(entry).__name__ == _class(row)
    assert entry.value is None
    assert "k" in _keys(holder) and "unnamed_1" not in _keys(holder)


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize("row", ROWS)
def test_value_none_prints_exactly_one_warning_naming_the_entry(
    tmp_path, capsys, where, row
):
    d, holder, entry = _make(tmp_path, where, row)
    capsys.readouterr()
    _any(lambda: setattr(entry, "value", None))
    out, count = _warnings(capsys)
    assert count == 1, out
    assert "'k'" in out and "keyword-only" in out and "None" in out


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize("row", ROWS)
def test_value_none_is_written_as_a_keyword_only_entry(tmp_path, where, row):
    d, holder, entry = _make(tmp_path, where, row)
    _any(lambda: setattr(entry, "value", None))
    out = _call(d.toString)
    assert _line(where).search(out), out[-160:]
    assert "None" not in out.split("}")[-1] and "$None" not in out


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize("row", list(LOADED))
def test_value_none_keeps_a_trailing_comment(tmp_path, where, row):
    d, holder, entry = _make(tmp_path, where, row, comment=" // note")
    _any(lambda: setattr(entry, "value", None))
    out = _call(d.toString)
    assert _line(where, tail=" // note").search(out), out[-160:]


def _neighbours(d):
    """The `a` and `b` lines, padding folded (an edit may re-pad a sub-dictionary)."""
    lines = d.toString().splitlines()
    return [" ".join(ln.split()) for ln in lines if re.match(r"\s*[ab] ", ln)]


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize("row", ROWS)
def test_value_none_leaves_the_neighbours_unchanged(tmp_path, where, row):
    d, holder, entry = _make(tmp_path, where, row)
    before = _neighbours(d)
    _any(lambda: setattr(entry, "value", None))
    after = _neighbours(d)
    assert after == before and len(after) == 2


@pytest.mark.parametrize("row", ["int", "float", "str", "bool", "list", "vector"])
def test_value_assigned_after_none_is_written_as_a_named_entry(tmp_path, row):
    d, holder, entry = _make(tmp_path, "sub", row)
    _any(lambda: setattr(entry, "value", None))
    new = {"int": 5, "float": 2.5, "str": "q", "bool": False}.get(row)
    if row == "list":
        new = [7, 8]
    if row == "vector":
        new = [0, 1, 0]
    _call(lambda: setattr(entry, "value", new))
    assert entry.value is not None
    assert not _line("sub").search(d.toString())
    assert re.search(r"^    k\s+\S", d.toString(), re.MULTILINE)


@pytest.mark.parametrize("name", TENSORS)
def test_tensor_value_none_keeps_class_and_reads_none_with_one_warning(capsys, name):
    cls, value = TENSORS[name]
    entry = cls(value=value)
    entry._name = "k"
    capsys.readouterr()
    _any(lambda: setattr(entry, "value", None))
    assert type(entry) is cls and entry.value is None
    out, count = _warnings(capsys)
    assert count == 1, out


# --- `d.count = None` -----------------------------------------------------------------------


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize("row", ROWS)
def test_assigning_none_to_an_entry_acts_like_value_none_on_the_same_object(
    tmp_path, capsys, where, row
):
    d, holder, entry = _make(tmp_path, where, row)
    capsys.readouterr()
    _any(lambda: setattr(holder, "k", None))
    assert holder.k is entry and type(entry).__name__ == _class(row)
    assert entry.value is None
    out, count = _warnings(capsys)
    assert count == 1 and "'k'" in out, out
    assert _line(where).search(_call(d.toString))


@pytest.mark.parametrize("where", WHERE)
def test_assigning_none_twice_warns_once(tmp_path, capsys, where):
    d, holder, entry = _make(tmp_path, where, "int")
    capsys.readouterr()
    _any(lambda: setattr(holder, "k", None))
    _any(lambda: setattr(holder, "k", None))
    assert _warnings(capsys)[1] == 1


# --- refused: new key, sub-dictionary, list item --------------------------------------------


def _snapshot(d):
    return _keys(d), d.toString()


@pytest.mark.parametrize("where", WHERE)
def test_assigning_none_to_a_new_key_raises_and_changes_nothing(tmp_path, where):
    d, holder, _ = _make(tmp_path, where, "int")
    before = _snapshot(holder), d.toString()
    err = _expect_error(lambda: setattr(holder, "new", None))
    assert "new" in str(err) and "del" in str(err)
    assert (_snapshot(holder), d.toString()) == before
    assert "new" not in holder.__dict__


def test_assigning_none_to_a_sub_dictionary_raises_and_keeps_it(tmp_path):
    d, _, _ = _make(tmp_path, "sub", "int")
    sub, before = d.s, d.toString()
    err = _expect_error(lambda: setattr(d, "s", None))
    assert "'s'" in str(err) or " s " in str(err)
    assert d.s is sub and d.toString() == before


def test_assigning_none_to_a_missing_value_entry_of_a_sub_dictionary_raises(tmp_path):
    d, _, _ = _make(tmp_path, "sub", "int")
    before = d.toString()
    err = _expect_error(lambda: setattr(d.s, "value", None))
    assert "value" in str(err)
    assert d.toString() == before and "value" not in d.s.__dict__


@pytest.mark.parametrize("where", WHERE)
def test_none_for_a_list_item_raises_and_keeps_the_old_value(tmp_path, where):
    d, holder, entry = _make(tmp_path, where, "split-list")
    item = entry.value[0]
    old, before = item.value, d.toString()
    err = _expect_error(lambda: setattr(item, "value", None))
    assert "list item" in str(err).lower()
    assert item.value == old and d.toString() == before


# --- write 1 == write 2, re-read as an `ofWord` under `unnamed_<n>` -------------------------


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize("row", ROWS)
def test_written_keyword_only_entry_reads_back_and_writes_the_same_text(
    tmp_path, where, row
):
    d, holder, entry = _make(tmp_path, where, row)
    _any(lambda: setattr(entry, "value", None))
    first = _call(d.toString)
    d2 = _any(lambda: _load(_path(tmp_path, first, "again")))
    holder2 = _holder(d2, where)
    assert "k" not in holder2.__dict__
    words = [
        (k, type(v).__name__, v.value)
        for k, v in holder2.__dict__.items()
        if k.startswith("unnamed_")
    ]
    assert words == [("unnamed_1", "ofWord", "k")]
    assert d2.toString() == first


# --- pitzDaily: deltaT, init -> edit -> save -> load -> write -------------------------------


def test_pitzdaily_delta_t_none_survives_save_load_and_is_written(case, capsys):
    c = pf.init(path=case)
    _any(lambda: setattr(c.system.controlDict.deltaT, "value", None))
    capsys.readouterr()
    c.save(path=case)
    loaded = pf.load(path=case)
    out, count = _warnings(capsys)
    assert count == 0, out
    assert loaded.system.controlDict.deltaT.value is None
    loaded.write()
    text = (case / "system" / "controlDict").read_text()
    assert re.search(r"^deltaT;$", text, re.MULTILINE), text[:400]
    assert "deltaT  " not in text and "None" not in text


def test_pitzdaily_write_without_save_gives_the_same_deltat_line(case):
    c = pf.init(path=case)
    _any(lambda: setattr(c.system.controlDict.deltaT, "value", None))
    c.write()
    text = (case / "system" / "controlDict").read_text()
    assert re.search(r"^deltaT;$", text, re.MULTILINE), text[:400]


# --- nothing prints and nothing changes where no value was replaced -------------------------


@pytest.mark.parametrize("row", ROWS)
def test_constructor_without_a_value_prints_no_warning(capsys, row):
    capsys.readouterr()
    cls = getattr(fkt, _class(row))
    cls(name="n")
    assert _warnings(capsys) == ("", 0)


@pytest.mark.parametrize("name", ["ofInt", "ofFloat", "ofStr", "ofBool"])
def test_scalar_constructor_without_a_value_leaves_none_and_is_silent(capsys, name):
    capsys.readouterr()
    entry = getattr(fkt, name)(name="n")
    assert entry.value is None
    assert _warnings(capsys) == ("", 0)


def test_var_constructor_without_a_value_holds_the_word_none_today(capsys):
    # pinned quirk (not desired behaviour): `$None`; reported to the coordinator
    capsys.readouterr()
    assert fkt.ofVar(name="n").value == "None"
    assert _warnings(capsys) == ("", 0)


def test_list_constructor_default_stays_an_empty_list():
    assert fkt.ofList().value == []
    assert fkt.ofSplitList().value == []


def test_vector_constructor_default_stays_zeros():
    assert fkt.ofVector().value == [0.0, 0.0, 0.0]


def test_built_entry_without_a_value_is_written_keyword_only_and_silent(capsys):
    d = fkt.ofDictFile(name="d")
    d.update(fkt.ofInt(name="n"))
    capsys.readouterr()
    text = d.toString()
    assert re.search(r"^n;$", text, re.MULTILINE), text[-80:]
    assert _warnings(capsys) == ("", 0)


def _case_files():
    files = sorted(p for p in RELEASES.iterdir() if p.is_file())
    files += sorted(p for p in PITZ.rglob("*") if p.is_file())
    return [pytest.param(p, id=f"{p.parent.name}-{p.name}") for p in files]


@pytest.mark.parametrize("path", _case_files())
def test_loading_and_writing_a_shipped_file_prints_no_warning_and_keeps_the_text(
    capsys, path
):
    capsys.readouterr()
    try:
        d = _load(path)
    except Exception as e:  # noqa: BLE001  (FoamKitError or a bare load bug, not T-087)
        pytest.skip(f"does not load today ({type(e).__name__}); not this ticket")
    text = d.toString()
    out, count = _warnings(capsys)
    assert count == 0, out
    assert text.encode() == path.read_bytes().replace(b"\r\n", b"\n")


# --- the `.params` cache ---------------------------------------------------------------------


def _list_nodes(o, found):
    if isinstance(o, dict):
        if o.get("_type") in ("ofList", "ofSplitList") and "_value" in o:
            found.append(o)
        for v in o.values():
            _list_nodes(v, found)
    elif isinstance(o, list):
        for v in o:
            _list_nodes(v, found)
    return found


@pytest.mark.parametrize("type_name", ["ofList", "ofSplitList"])
def test_cache_load_accepts_a_null_value_for_a_list(case, capsys, type_name):
    pf.init(path=case).save(path=case)
    cache = case / ".params" / "_case.json"
    data = json.loads(cache.read_text())
    nodes = _list_nodes(data, [])
    assert nodes, "the pitzDaily cache holds a list entry"
    node = nodes[0]
    node["_type"], node["_value"] = type_name, None
    name = node["_name"]
    cache.write_text(json.dumps(data))
    capsys.readouterr()
    loaded = _call(lambda: pf.load(path=case))
    out, count = _warnings(capsys)
    assert count == 0, out
    found = [n for n in _list_nodes_loaded(loaded) if getattr(n, "_name", None) == name]
    assert found and found[0].value is None


def _list_nodes_loaded(node, seen=None):
    seen = set() if seen is None else seen
    if id(node) in seen:
        return []
    seen.add(id(node))
    out = [node] if isinstance(node, fkt.ofList) else []
    if hasattr(node, "__dict__"):
        for v in list(vars(node).values()):
            if isinstance(v, (fkt.ofDict, fkt.ofList)) or hasattr(v, "__dict__"):
                out += _list_nodes_loaded(v, seen)
    return out


def test_pitzdaily_unedited_init_save_load_write_prints_no_warning(case, capsys):
    before = {p: p.read_bytes() for p in sorted(case.rglob("*")) if p.is_file()}
    capsys.readouterr()
    pf.init(path=case).save(path=case)
    pf.load(path=case).write()
    out, count = _warnings(capsys)
    assert count == 0, out
    after = {p: p.read_bytes() for p in before}
    assert after == before
