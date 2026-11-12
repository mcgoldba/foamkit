"""Assigning a dimension set is written back, or raises (T-088, issue #116).

Specification tests for docs/tickets/T-088-dimension-assignment-is-written-or-raises.md.
`d.nu.dimensions = [0, 1, -1, 0, 0, 0, 0]` is either written as `nu [0 1 -1 0 0 0 0] 1e-05;`
or raises `FoamKitError` naming the entry and the expected shape; it never leaves a stray
attribute behind, never writes Python list text and never zeroes the set.

Every bold row of the ticket's three "Today" tables is tested at the top level, in a
sub-dictionary and in a file of the pitzDaily fixture (`0/U` `dimensions`,
`constant/transportProperties` `nu`).  A bare exception (`ValueError`, `AttributeError`,
`TypeError`) and "no exception" are both reported as an `AssertionError` by the helpers, so
every failing test fails with `AssertionError`.

Differences to the ticket's table (reproduced there on 839663c; checked on main cc03aa1):
`nu nu [0 2 -1 0 0 0 0] 1e-05;` now loads as `ofDimensionedScalar` (T-014, with `_dimName`),
not `ofNamedDimension`, so it is tested with the scalar rows.

The acceptance criteria list `None` among the inputs `ofDimension(...)` must refuse, and
also say `ofDimension(None)` keeps the all-zero default.  They are read as: the constructor
default stays (pinned below); `None` is refused where a set already exists (the setter and
the entries).
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
NEW = [0, 1, -1, 0, 0, 0, 0]
OLD = [0, 2, -1, 0, 0, 0, 0]
SCALAR_LINE = "nu [0 2 -1 0 0 0 0] 1e-05;"
NAMED_LINE = "dimensions [0 1 -1 0 0 0 0];"

# id -> (kind, where, source: text body or a fixture path, entry key, old set, entry prefix)
TARGETS = {
    "scalar-top": ("scalar", "top", SCALAR_LINE, "nu", OLD, r"nu\s+"),
    "scalar-sub": ("scalar", "sub", SCALAR_LINE, "nu", OLD, r"nu\s+"),
    "scalar-legacy-nu-nu": (
        "scalar",
        "top",
        "nu nu [0 2 -1 0 0 0 0] 1e-05;",
        "nu",
        OLD,
        r"nu\s+nu\s+",
    ),
    "scalar-transportProperties": (
        "scalar",
        "file",
        PITZ / "constant" / "transportProperties",
        "nu",
        OLD,
        r"nu\s+",
    ),
    "named-top": ("named", "top", NAMED_LINE, "dimensions", NEW, r"dimensions\s+"),
    "named-sub": ("named", "sub", NAMED_LINE, "dimensions", NEW, r"dimensions\s+"),
    "named-pitzDaily-0-U": (
        "named",
        "file",
        PITZ / "0" / "U",
        "dimensions",
        NEW,
        r"dimensions\s+",
    ),
}

# accepted inputs: id -> factory (a fresh object per test)
VALID = {
    "list": lambda: [0, 1, -1, 0, 0, 0, 0],
    "tuple": lambda: (0, 1, -1, 0, 0, 0, 0),
    "string": lambda: "[0 1 -1 0 0 0 0]",
    "string-spaced": lambda: "[ 0 1 -1 0 0 0 0 ]",
    "integral-float": lambda: [0, 1.0, -1, 0, 0, 0, 0],
    "ofDimension": lambda: fkt.ofDimension([0, 1, -1, 0, 0, 0, 0]),
}

# refused inputs
INVALID = {
    "six-exponents-short": [0, 1, -1],
    "word": [0, "a", -1, 0, 0, 0, 0],
    "fraction": [0, 2.5, -1, 0, 0, 0, 0],
    "bool": [0, True, 0, 0, 0, 0, 0],
    "string-a": "a",
    "named-set": "[velocity]",
    "five-exponents": "[0 2 -1 0 0]",
    "none": None,
}

# --- helpers ------------------------------------------------------------------------------


def _attr_axis(target):
    return (
        ["dimensions", "dimension"]
        if TARGETS[target][0] == "scalar"
        else ["dimensions"]
    )


def _targets_with_attr(test, values):
    """(target, attr, value id) combinations."""
    return [
        pytest.param(t, a, v, id=f"{t}-{a}-{v}")
        for t in TARGETS
        for a in _attr_axis(t)
        for v in values
    ]


def _call(fn):
    """Run `fn`; a bare (non-FoamKit) exception becomes an AssertionError."""
    try:
        return fn()
    except FoamKitError:
        raise
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"bare {type(e).__name__}: {str(e)[:80]!r}") from e


def _expect_error(fn):
    """The FoamKitError raised by `fn`; AssertionError if nothing or a bare exception."""
    try:
        fn()
    except FoamKitError as e:
        return e
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"bare {type(e).__name__}: {str(e)[:80]!r}") from e
    raise AssertionError("no FoamKitError was raised")


def _sub(body):
    lines = "".join("    " + ln + "\n" for ln in body.split("\n"))
    return "s\n{\n" + lines + "}\n"


def _setup(tmp_path, target):
    """(path, dictionary, entry) of a loaded target."""
    kind, where, src, key, _, _ = TARGETS[target]
    path = tmp_path / "dimFile"
    if where == "file":
        path.write_bytes(src.read_bytes())
    else:
        body = src + "\n" if where == "top" else _sub(src)
        path.write_bytes((HEADER + body).encode())
    d = _load(path)
    holder = d.s if where == "sub" else d
    return path, d, holder.__dict__[key]


def _dims(entry, kind):
    """The set the entry holds: `.dimensions` (named) or `.dimension.dimensions` (scalar)."""
    return entry.dimensions if kind == "named" else entry.dimension.dimensions


def _line(target, dims_text):
    """Regex of the entry's written line (any spacing between the tokens)."""
    kind, _, _, key, _, prefix = TARGETS[target]
    value = r"\s+1e-05" if kind == "scalar" else ""
    return re.compile(rf"^\s*{prefix}\[{dims_text}\]{value};$", re.MULTILINE)


def _assign(entry, attr, make):
    value = make() if callable(make) else make
    _call(lambda: setattr(entry, attr, value))


def _ids(table):
    return list(table)


# --- accepted inputs: stored, written, reloaded -------------------------------------------


@pytest.mark.parametrize(
    "target, attr, value",
    _targets_with_attr("test_assigned_dimensions_are_stored", _ids(VALID)),
)
def test_assigned_dimensions_are_stored(tmp_path, target, attr, value):
    """The set is read back as a plain list of 7 ints (`1.0` becomes `1`)."""
    kind = TARGETS[target][0]
    _, _, entry = _setup(tmp_path, target)
    _assign(entry, attr, VALID[value])
    got = _call(lambda: _dims(entry, kind))
    assert got == NEW
    assert _call(lambda: entry.dimensions) == NEW
    assert [type(i) for i in got] == [int] * 7


@pytest.mark.parametrize(
    "target, attr, value",
    _targets_with_attr("test_assigned_dimensions_are_written", _ids(VALID)),
)
def test_assigned_dimensions_are_written(tmp_path, target, attr, value):
    """`nu [0 1 -1 0 0 0 0] 1e-05;`, never zeros, never Python list text."""
    _, d, entry = _setup(tmp_path, target)
    _assign(entry, attr, VALID[value])
    out = _call(d.toString)
    assert _line(target, "0 1 -1 0 0 0 0").search(out), out[-200:]
    assert "[0 0 0 0 0 0 0]" not in out
    assert "[0, " not in out


@pytest.mark.parametrize(
    "target, attr, value",
    _targets_with_attr("test_written_text_reloads_with_the_assigned_set", ["list"]),
)
def test_written_text_reloads_with_the_assigned_set(tmp_path, target, attr, value):
    kind, where, _, key, _, _ = TARGETS[target]
    _, d, entry = _setup(tmp_path, target)
    _assign(entry, attr, VALID[value])
    out = _call(d.toString)
    again = tmp_path / "again"
    again.write_bytes(out.encode())
    d2 = _load(again)
    entry2 = (d2.s if where == "sub" else d2).__dict__[key]
    assert _call(lambda: _dims(entry2, kind)) == NEW


@pytest.mark.parametrize("target", [t for t in TARGETS if TARGETS[t][0] == "scalar"])
def test_dimension_attribute_holds_an_ofDimension(tmp_path, target):
    _, _, entry = _setup(tmp_path, target)
    _assign(entry, "dimension", VALID["list"])
    assert type(entry.dimension).__name__ == "ofDimension"


@pytest.mark.parametrize("target", ["scalar-top", "named-top"])
def test_assigning_an_ofDimension_copies_its_list(tmp_path, target):
    _, _, entry = _setup(tmp_path, target)
    source = fkt.ofDimension([0, 1, -1, 0, 0, 0, 0])
    entry.dimensions = source
    source.dimensions[1] = 9
    assert _call(lambda: entry.dimensions) == NEW


@pytest.mark.parametrize("target", [t for t in TARGETS if TARGETS[t][0] == "scalar"])
def test_scalar_value_survives_a_dimension_assignment(tmp_path, target):
    """Guard: the value is untouched by an assignment to the set (`.dimension` path)."""
    _, d, entry = _setup(tmp_path, target)
    entry.dimension = fkt.ofDimension(NEW)
    assert entry.value == 1e-05
    assert "1e-05" in d.toString()


# --- refused inputs: FoamKitError naming the entry and the shape; nothing changes ----------


@pytest.mark.parametrize(
    "target, attr, value",
    _targets_with_attr("test_invalid_assignment_raises_foamkiterror", _ids(INVALID)),
)
def test_invalid_assignment_raises_foamkiterror(tmp_path, target, attr, value):
    """The message names the entry and the expected shape (7 integer exponents)."""
    key = TARGETS[target][3]
    _, _, entry = _setup(tmp_path, target)
    err = _expect_error(lambda: setattr(entry, attr, INVALID[value]))
    msg = str(err)
    assert f"'{key}'" in msg, msg
    assert "7" in msg and "integer" in msg, msg


@pytest.mark.parametrize(
    "target, attr, value",
    _targets_with_attr("test_invalid_assignment_keeps_the_old_set", _ids(INVALID)),
)
def test_invalid_assignment_keeps_the_old_set(tmp_path, target, attr, value):
    kind, _, _, _, old, _ = TARGETS[target]
    _, _, entry = _setup(tmp_path, target)
    _expect_error(lambda: setattr(entry, attr, INVALID[value]))
    assert _call(lambda: _dims(entry, kind)) == old


@pytest.mark.parametrize(
    "target, attr, value",
    _targets_with_attr(
        "test_invalid_assignment_leaves_the_written_text_unchanged", _ids(INVALID)
    ),
)
def test_invalid_assignment_leaves_the_written_text_unchanged(
    tmp_path, target, attr, value
):
    """Both the preserved write and the regenerated write stay as before the attempt."""
    path, d, entry = _setup(tmp_path, target)
    before, before_regen = d.toString(), d.toString(_preserve=False)
    assert before.encode() == path.read_bytes()
    _expect_error(lambda: setattr(entry, attr, INVALID[value]))
    assert d.toString() == before
    assert d.toString(_preserve=False) == before_regen


@pytest.mark.parametrize("target", [t for t in TARGETS if TARGETS[t][0] == "scalar"])
@pytest.mark.parametrize("value", ["short", "word"])
def test_invalid_dimensions_on_a_scalar_leave_no_stray_attribute(
    tmp_path, target, value
):
    _, _, entry = _setup(tmp_path, target)
    bad = INVALID["six-exponents-short"] if value == "short" else INVALID["word"]
    _expect_error(lambda: setattr(entry, "dimensions", bad))
    assert "dimensions" not in vars(entry)


# --- ofDimension itself ------------------------------------------------------------------

CTOR_INVALID = [
    k for k in INVALID if k != "none"
]  # ofDimension(None) is the default (pinned)


def _accepted_inputs():
    """Every accepted input."""
    return [pytest.param(v, id=v) for v in VALID]


@pytest.mark.parametrize("value", CTOR_INVALID)
def test_ofDimension_constructor_rejects_invalid_input(value):
    err = _expect_error(lambda: fkt.ofDimension(INVALID[value]))
    assert "7" in str(err) and "integer" in str(err), str(err)


@pytest.mark.parametrize("value", _ids(INVALID))
def test_ofDimension_setter_rejects_invalid_input_and_keeps_the_old_set(value):
    od = fkt.ofDimension(NEW)
    err = _expect_error(lambda: setattr(od, "dimensions", INVALID[value]))
    assert "7" in str(err) and "integer" in str(err), str(err)
    assert od.dimensions == NEW


@pytest.mark.parametrize("value", _accepted_inputs())
def test_ofDimension_constructor_reads_every_accepted_input(value):
    od = _call(lambda: fkt.ofDimension(VALID[value]()))
    assert od.dimensions == NEW
    assert [type(i) for i in od.dimensions] == [int] * 7
    assert str(od) == "[0 1 -1 0 0 0 0]"


@pytest.mark.parametrize("value", _accepted_inputs())
def test_ofDimension_setter_reads_every_accepted_input(value):
    od = fkt.ofDimension(OLD)
    _call(lambda: setattr(od, "dimensions", VALID[value]()))
    assert od.dimensions == NEW
    assert [type(i) for i in od.dimensions] == [int] * 7


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(lambda: fkt.ofDimension(), id="no-argument"),
        pytest.param(lambda: fkt.ofDimension(None), id="None"),
        pytest.param(lambda: fkt.ofDimension(dimensions=None), id="keyword-None"),
        pytest.param(lambda: fkt.ofNamedDimension(name="x"), id="named-no-set"),
        pytest.param(lambda: fkt.ofDimensionedScalar().dimension, id="scalar-no-set"),
    ],
)
def test_default_dimension_set_is_all_zero(make):
    """Pinned: no explicit value keeps the all-zero default, with no error."""
    assert make().dimensions == [0, 0, 0, 0, 0, 0, 0]


def test_ofDimension_list_input_is_written_as_seven_exponents():
    """Pinned: the existing accepted input keeps working and keeps its text."""
    assert str(fkt.ofDimension([0, 1, -1, 0, 0, 0, 0])) == "[0 1 -1 0 0 0 0]"


@pytest.mark.parametrize(
    "cls",
    ["ofDimensionedSphericalTensor", "ofDimensionedSymmTensor", "ofDimensionedTensor"],
)
def test_dimensioned_tensors_share_the_ofDimension_setter(cls):
    """Pinned: the tensor types inherit the one validating property."""
    assert getattr(fkt, cls).dimensions is fkt.ofDimension.dimensions


@pytest.mark.parametrize("cls", ["ofDimensionedScalar", "ofDimensionedVector"])
def test_dimensioned_scalar_and_vector_have_a_dimensions_property(cls):
    prop = getattr(getattr(fkt, cls), "dimensions", None)
    assert isinstance(prop, property)
    assert prop is fkt.ofDimensionedScalar.dimensions


# --- ofNamedDimension: `.value` and `.dimension` are guarded ------------------------------

NAMED = [t for t in TARGETS if TARGETS[t][0] == "named"]


@pytest.mark.parametrize("target", NAMED)
@pytest.mark.parametrize("attr", ["value", "dimension"])
@pytest.mark.parametrize("what", ["valid-list", "number"])
def test_named_dimension_value_and_dimension_assignment_point_to_dimensions(
    tmp_path, target, attr, what
):
    key = TARGETS[target][3]
    _, _, entry = _setup(tmp_path, target)
    value = NEW if what == "valid-list" else 5
    err = _expect_error(lambda: setattr(entry, attr, value))
    msg = str(err)
    assert f"'{key}'" in msg, msg
    assert ".dimensions" in msg, msg


@pytest.mark.parametrize("target", NAMED)
@pytest.mark.parametrize("attr", ["value", "dimension"])
def test_named_dimension_guard_leaves_no_attribute_and_the_text_unchanged(
    tmp_path, target, attr
):
    path, d, entry = _setup(tmp_path, target)
    _expect_error(lambda: setattr(entry, attr, NEW))
    assert attr not in vars(entry)
    assert d.toString().encode() == path.read_bytes()


# --- case.save() -> load -> write ----------------------------------------------------------


def _saved_case(case, attr, make):
    c = pf.init(path=case)
    nu = c.constant.transportProperties.nu
    _assign(nu, attr, make)
    c.save(path=case)
    return pf.load(path=case)


@pytest.mark.parametrize("attr", ["dimensions", "dimension"])
def test_assigned_set_survives_save_and_load(case, attr):
    loaded = _saved_case(case, attr, VALID["list"])
    nu = loaded.constant.transportProperties.nu
    assert _call(lambda: nu.dimension.dimensions) == NEW
    out = loaded.constant.transportProperties.toString()
    assert re.search(r"^nu\s+\[0 1 -1 0 0 0 0\]\s+1e-05;$", out, re.MULTILINE), out


@pytest.mark.parametrize("attr", ["dimensions", "dimension"])
def test_assigned_set_is_written_to_disk_after_save_and_load(case, attr):
    loaded = _saved_case(case, attr, VALID["list"])
    loaded.write()
    text = (case / "constant" / "transportProperties").read_text()
    assert re.search(r"^nu\s+\[0 1 -1 0 0 0 0\]\s+1e-05;$", text, re.MULTILINE), text
    reread = _read_file(case / "constant" / "transportProperties")
    assert reread.nu.dimension.dimensions == NEW


def _read_file(path):
    return fkt.DictFileParser(path).readDictFile()


# --- an old `.params` cache with a stray `dimensions` key ---------------------------------


def _cache_with_stray(case, stray):
    pf.init(path=case).save(path=case)
    cache = case / ".params" / "_case.json"
    data = json.loads(cache.read_text())
    data["constant"]["transportProperties"]["nu"]["dimensions"] = stray
    cache.write_text(json.dumps(data))


def test_old_cache_with_a_valid_stray_dimensions_key_applies_it(case):
    _cache_with_stray(case, NEW)
    nu = pf.load(path=case).constant.transportProperties.nu
    assert _call(lambda: nu.dimension.dimensions) == NEW
    out = pf.load(path=case).constant.transportProperties.toString()
    assert re.search(r"^nu\s+\[0 1 -1 0 0 0 0\]\s+1e-05;$", out, re.MULTILINE), out


@pytest.mark.parametrize(
    "stray", [[0, 1, -1], [0, "a", -1, 0, 0, 0, 0]], ids=["short", "word"]
)
def test_old_cache_with_an_invalid_stray_dimensions_key_raises_on_load(case, stray):
    _cache_with_stray(case, stray)
    err = _expect_error(lambda: pf.load(path=case))
    assert "'nu'" in str(err), str(err)
    assert "7" in str(err) and "integer" in str(err), str(err)


# --- pinned: loading and writing real and fixture files is unchanged ---------------------

# Files that do not load today, unrelated to T-088 (found while writing these tests):
# - a bare exception (ValueError / TypeError) escapes the load: suspected bugs, not asserted
#   as wanted; strict xfail so a fix shows up
# - an explicit FoamKitError: pinned as loud (a change to silent loss would be a regression)
BARE_ON_LOAD = {
    "esi-v2606.freePiston.U",
    "foundation-13.aerofoilNACA0012Steady.U",
    "foundation-14.aerofoilNACA0012Steady.U",
    "foundation-14.cylinder.blockMeshDict",
    "foundation-14.floatingBeam.blockMeshDict",
    "foundation-14.rotatingCube.blockMeshDict",
}
LOUD_ON_LOAD = {
    "esi-v2606.flange.faceSetDict",
    "esi-v2606.good-if1.dict",
    "esi-v2606.good-if3.dict",
    "esi-v2606.good-word-expand.dict",
    "esi-v2606.potentialFoam-cylinder.blockMeshDict",
    "esi-v2606.squareBend.blockMeshDict",
    "foundation-14.cylinder.fvSchemes",
    "foundation-14.engine2Valve2D.fvConstraints",
    "foundation-14.SandiaD_LTS.radiationProperties",
    "foundation-14.trayedPipe.createZonesDict",
}
_FILES = sorted(
    [p for p in RELEASES.iterdir() if p.is_file() and p.name != ".gitattributes"]
    + [p for p in PITZ.rglob("*") if p.is_file() and "postProcessing" not in p.parts]
)


LOADABLE = [
    pytest.param(p, id=p.relative_to(TESTS).as_posix())
    for p in _FILES
    if p.name not in BARE_ON_LOAD | LOUD_ON_LOAD
]
BARE = [
    pytest.param(
        p,
        id=p.relative_to(TESTS).as_posix(),
        marks=pytest.mark.xfail(
            strict=True,
            raises=(ValueError, TypeError),
            reason="pre-existing bare exception on load, not T-088",
        ),
    )
    for p in _FILES
    if p.name in BARE_ON_LOAD
]
LOUD = [
    pytest.param(p, id=p.relative_to(TESTS).as_posix())
    for p in _FILES
    if p.name in LOUD_ON_LOAD
]


@pytest.mark.parametrize("path", LOADABLE + BARE)
def test_unedited_write_is_byte_identical_for_releases_and_pitzDaily(path):
    """Pinned: the loaded file writes the same text as it was read from."""
    assert _load(path).toString().encode() == path.read_bytes()


@pytest.mark.parametrize("path", LOUD)
def test_unsupported_release_files_still_fail_loudly(path):
    """Pinned: a file FoamKit cannot load raises FoamKitError, never loads partially."""
    with pytest.raises(FoamKitError):
        _load(path)


@pytest.mark.parametrize("name", ["constant/transportProperties", "0/U"])
def test_pitzDaily_regenerated_write_keeps_the_dimension_sets(name):
    """Pinned: the regenerated write of the two dimension-bearing fixture files."""
    path = PITZ / name
    out = _load(path).toString(_preserve=False)
    expected = {
        "constant/transportProperties": "nu          [0 2 -1 0 0 0 0] 1e-05;",
        "0/U": "[0 1 -1 0 0 0 0];",
    }
    assert expected[name] in out
    assert "[0 0 0 0 0 0 0]" not in out


def test_scalar_keeps_the_dimension_cache_key():
    """The set is stored as `dimension`, so `.params` caches and layout
    fingerprints saved before T-088 stay valid (no `_dimension` key)."""
    d = fkt.ofDimensionedScalar(
        name="nu", value=1e-05, dimensions=[0, 2, -1, 0, 0, 0, 0]
    )
    assert "dimension" in vars(d)
    assert "_dimension" not in vars(d)
    d.dimensions = [0, 1, -1, 0, 0, 0, 0]
    assert list(vars(d)).count("dimension") == 1
    assert d.dimension.dimensions == [0, 1, -1, 0, 0, 0, 0]
