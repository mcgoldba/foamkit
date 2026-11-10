"""Named dimensioned entries keep their value (T-014, issue #21).

Specification tests for docs/tickets/T-014-legacy-named-dimensioned-value-loss.md.  The legacy
form `nu nu [0 2 -1 0 0 0 0] 1.5e-05;` (name, dimension set, value; also with spaces inside the
brackets) loads as an `ofNamedDimension` that has no value, so the value is lost as soon as
the entry is regenerated.  Since T-020a an UNEDITED entry is written from its source text, so
the loss shows (a) on the object (no value), (b) on the regenerate path
(`toString(_preserve=False)`, what an edited or new entry gets), and (c) after an edit in the
same top-level sub-dict, which regenerates the whole block.  All three are tested, at the top
level and inside a sub-dict.

Integer-valued named entries (`E E [1 -1 -3 0 0 0 0] 0;`) load as `ofStr` text today and keep
their text only by luck; after the fix they are typed and have a numeric value (type change,
noted in the commit body).  Vector values and named units are out of scope (controls that
record today's behaviour).

Real files (byte-exact copies in tests/releases/, outside the golden glob; `git hash-object`
of each copy equals the blob in the upstream tree):

foundation-11.flange.physicalProperties   (`DT DT [0 2 -1 0 0 0 0] 4e-05;`, line 17)
  Shallow clone of https://github.com/OpenFOAM/OpenFOAM-11, commit
  9cbf94f3339dd49286633b303c4155fd10ea8200, extracted with `git show HEAD:<path>`:
  tutorials/legacy/basic/laplacianFoam/flange/constant/physicalProperties
  blob 7619059ce0d1b3487e8e74aa70a59831f849c0fa
esi-v2606.annularCombustorTurbine.combustionProperties   (8 named entries with spaces inside
  the brackets, lines 21-82, 3 of them integer-valued)
  ESI OpenFOAM-v2606 (tag OpenFOAM-v2606; the `openfoam-OpenFOAM-v2606-tutorials` archive
  extraction; the same bytes are served by
  https://gitlab.com/openfoam/core/openfoam/-/raw/OpenFOAM-v2606/<path>):
  tutorials/combustion/XiDyMFoam/annularCombustorTurbine/constant/combustionProperties
  blob 0a7746a5af6dcbc7444ee6bfc82174b98641f2fe
"""

import re

import pytest

import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import TESTS
from test_directives import HEADER
from test_several_lists_value import CONTAINERS, _body, _load, _scope, _wrap

NL = "\n"
RELEASES = TESTS / "releases"
FLANGE = RELEASES / "foundation-11.flange.physicalProperties"
ANNULAR = RELEASES / "esi-v2606.annularCombustorTurbine.combustionProperties"

DIMS = [0, 2, -1, 0, 0, 0, 0]


# - (id, source line, key, named, dimensions, value, integer-valued)
ROWS = [
    ("named", "nu nu [0 2 -1 0 0 0 0] 1.5e-05;", "nu", True, DIMS, 1.5e-05, False),
    (
        "named-spaced",
        "nu nu [ 0 2 -1 0 0 0 0 ] 1.5e-05;",
        "nu",
        True,
        DIMS,
        1.5e-05,
        False,
    ),
    ("unnamed-spaced", "nu [ 0 2 -1 0 0 0 0 ] 1e-05;", "nu", False, DIMS, 1e-05, False),
    (
        "integer-spaced",
        "XiShapeCoef XiShapeCoef [ 0 0 0 0 0 0 0 ] 1;",
        "XiShapeCoef",
        True,
        [0] * 7,
        1,
        True,
    ),
    (
        "integer-zero",
        "E E [1 -1 -3 0 0 0 0] 0;",
        "E",
        True,
        [1, -1, -3, 0, 0, 0, 0],
        0,
        True,
    ),
    (
        "exponent-value",
        "lambda lambda [0 -2 1 0 0 0 0] 1e5;",
        "lambda",
        True,
        [0, -2, 1, 0, 0, 0, 0],
        1e5,
        False,
    ),
]
ROW_IDS = [r[0] for r in ROWS]


def _rows(kind=None, rows=ROWS):
    """`pytest.param` for each row and container (`kind` names the test group; the T-014
    xfails were removed when the fix landed)."""
    return [
        pytest.param(*row, cont, id=f"{row[0]}-{cont}")
        for row in rows
        for cont in CONTAINERS
    ]


# --- helpers ---------------------------------------------------------------------------------
def _toks(text):
    """Tokens of `text` for entry comparison: brackets, parentheses, braces, `;` and words;
    numbers are normalised (`1.5e-05` == `1.5e-5`)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    out = []
    for t in re.findall(r"[\[\](){};]|[^\s\[\](){};]+", text):
        try:
            out.append(float(t))
        except ValueError:
            out.append(t)
    return out


def _expected(key, named, dims, value):
    """Tokens of the entry: `key [name] [ d0 .. d6 ] value ;`."""
    return (
        [key]
        + ([key] if named else [])
        + ["[", *map(float, dims), "]", float(value), ";"]
    )


def _has(text, seq):
    toks = _toks(_body(text))
    return any(toks[i : i + len(seq)] == seq for i in range(len(toks) - len(seq) + 1))


def _read(tmp_path, text, cont, name="named"):
    path = tmp_path / name
    path.write_text(HEADER + _wrap(text + NL, cont))
    return _load(path)


def _regen(d):
    return d.toString(_preserve=False)


def _dims(entry):
    dims = getattr(entry, "dimensions", None)
    if dims is None:
        dims = entry.dimension.dimensions
    return list(dims)


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# --- the object ----------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("rid", "line", "key", "named", "dims", "value", "integer", "cont"), _rows("object")
)
def test_loaded_entry_exposes_name_dimensions_and_a_numeric_value(
    tmp_path, rid, line, key, named, dims, value, integer, cont
):
    entry = getattr(_scope(_read(tmp_path, line, cont), cont), key)
    assert entry.name == key
    assert _dims(entry) == dims
    assert _is_number(entry.value)
    assert entry.value == pytest.approx(value)


@pytest.mark.parametrize(
    ("rid", "line", "key", "named", "dims", "value", "integer", "cont"),
    [
        pytest.param(
            *r,
            c,
            id=f"{r[0]}-{c}",
            marks=[],
        )
        for r in ROWS
        if r[6]
        for c in CONTAINERS
    ],
)
def test_integer_valued_entry_is_typed_not_text(
    tmp_path, rid, line, key, named, dims, value, integer, cont
):
    entry = getattr(_scope(_read(tmp_path, line, cont), cont), key)
    assert not isinstance(entry, fkt.ofStr)


# --- unedited write (T-020a guard) ------------------------------------------------------------
@pytest.mark.parametrize(
    ("rid", "line", "key", "named", "dims", "value", "integer", "cont"), _rows(None)
)
def test_unedited_entry_is_written_as_read(
    tmp_path, rid, line, key, named, dims, value, integer, cont
):
    d = _read(tmp_path, line, cont)
    assert d.toString() == HEADER + _wrap(line + NL, cont)


# --- the regenerate path ------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("rid", "line", "key", "named", "dims", "value", "integer", "cont"), _rows("regen")
)
def test_regenerated_entry_has_name_dimensions_and_value(
    tmp_path, rid, line, key, named, dims, value, integer, cont
):
    text = _regen(_read(tmp_path, line, cont))
    assert _has(text, _expected(key, named, dims, value)), text


@pytest.mark.parametrize(
    ("rid", "line", "key", "named", "dims", "value", "integer", "cont"), _rows(None)
)
def test_second_regenerated_write_equals_the_first(
    tmp_path, rid, line, key, named, dims, value, integer, cont
):
    text1 = _regen(_read(tmp_path, line, cont))
    out = tmp_path / "again"
    out.write_text(text1)
    assert _regen(_load(out)) == text1


@pytest.mark.parametrize(
    ("rid", "line", "key", "named", "dims", "value", "integer", "cont"), _rows("regen")
)
def test_regenerated_text_read_back_still_has_name_dimensions_and_value(
    tmp_path, rid, line, key, named, dims, value, integer, cont
):
    out = tmp_path / "again"
    out.write_text(_regen(_read(tmp_path, line, cont)))
    assert _has(_regen(_load(out)), _expected(key, named, dims, value))


# --- edits ----------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("rid", "line", "key", "named", "dims", "value", "integer", "cont"),
    _rows("edit"),
)
def test_assigned_value_is_written_with_name_and_dimensions(
    tmp_path, rid, line, key, named, dims, value, integer, cont
):
    d = _read(tmp_path, line, cont)
    getattr(_scope(d, cont), key).value = 7.25
    text = d.toString()
    assert _has(text, _expected(key, named, dims, 7.25)), text
    # - the old entry (with its old value) is gone: compare whole token sequences, since a
    # - bare `str(value) in text` check matches the 0s of the dimension set
    assert not _has(text, _expected(key, named, dims, value)), text


@pytest.mark.parametrize(
    ("rid", "line", "key", "named", "dims", "value", "integer", "cont"), _rows("edit")
)
def test_assigned_value_survives_a_regeneration(
    tmp_path, rid, line, key, named, dims, value, integer, cont
):
    d = _read(tmp_path, line, cont)
    getattr(_scope(d, cont), key).value = 7.25
    assert _has(_regen(d), _expected(key, named, dims, 7.25))


@pytest.mark.parametrize(
    ("rid", "line", "key", "named", "dims", "value", "integer", "cont"),
    _rows("sibling"),
)
def test_editing_a_sibling_in_the_same_block_keeps_the_entry(
    tmp_path, rid, line, key, named, dims, value, integer, cont
):
    other = "other other [ 0 1 0 0 0 0 0 ] 0.25;"
    d = _read(tmp_path, "before 1;" + NL + line + NL + other + NL + "after 2;", cont)
    _scope(d, cont).after.value = 3
    text = d.toString()
    assert _has(text, _expected(key, named, dims, value)), text
    assert _has(text, _expected("other", True, [0, 1, 0, 0, 0, 0, 0], 0.25)), text
    assert _scope(d, cont).before.value == 1


# --- controls: must not change -------------------------------------------------------------------
@pytest.mark.parametrize("cont", CONTAINERS)
def test_control_unnamed_dimensioned_scalar_keeps_type_and_output(tmp_path, cont):
    d = _read(tmp_path, "nu [0 2 -1 0 0 0 0] 1.5e-05;", cont)
    entry = _scope(d, cont).nu
    assert type(entry) is fkt.ofDimensionedScalar
    assert entry.value == pytest.approx(1.5e-05)
    assert _dims(entry) == DIMS
    assert _has(d.toString(), _expected("nu", False, DIMS, 1.5e-05))
    assert _has(_regen(d), _expected("nu", False, DIMS, 1.5e-05))


@pytest.mark.parametrize("cont", CONTAINERS)
def test_control_unnamed_dimensioned_scalar_edit_is_written(tmp_path, cont):
    d = _read(tmp_path, "nu [0 2 -1 0 0 0 0] 1.5e-05;", cont)
    _scope(d, cont).nu.value = 7.25
    assert _has(d.toString(), _expected("nu", False, DIMS, 7.25))


# - Out of scope: a vector value is kept as text (ofStr) today; whatever it becomes, it must
# - not lose a token.  Recorded here, not fixed by T-014.
@pytest.mark.parametrize("cont", CONTAINERS)
def test_control_vector_value_is_kept_as_text_and_is_stable(tmp_path, cont):
    line = "g g [0 1 -2 0 0 0 0] (0 0 -9.81);"
    d = _read(tmp_path, line, cont)
    assert type(_scope(d, cont).g) is fkt.ofStr
    for text in (d.toString(), _regen(d)):
        assert _has(text, _toks(line))
    out = tmp_path / "again"
    out.write_text(_regen(d))
    assert _regen(_load(out)) == _regen(d)


# - Out of scope (T-013): named units are kept as text (ofStr) today.
@pytest.mark.parametrize("cont", CONTAINERS)
def test_control_named_units_are_kept_as_text_and_are_stable(tmp_path, cont):
    line = "nu nu [m^2/s] 1.5e-05;"
    d = _read(tmp_path, line, cont)
    assert type(_scope(d, cont).nu) is fkt.ofStr
    for text in (d.toString(), _regen(d)):
        assert _has(text, _toks(line))
    out = tmp_path / "again"
    out.write_text(_regen(d))
    assert _regen(_load(out)) == _regen(d)


# --- real files -------------------------------------------------------------------------------------
_NAMED_RE = re.compile(
    r"^(\w+)\s+\1\s+\[\s*((?:-?\d+\s+){6}-?\d+)\s*\]\s+(\S+);\s*$", re.MULTILINE
)


def _named_entries(path):
    return [
        (m.group(1), [int(x) for x in m.group(2).split()], float(m.group(3)))
        for m in _NAMED_RE.finditer(path.read_text())
    ]


def _real_params(kind, edit=False):
    out = []
    for path in (FLANGE, ANNULAR):
        for key, dims, value in _named_entries(path):
            marks = []
            out.append(
                pytest.param(
                    path,
                    key,
                    dims,
                    value,
                    id=f"{path.name.split('.')[1]}-{key}",
                    marks=marks,
                )
            )
    return out


def test_real_files_have_the_expected_named_entries():
    assert [k for k, _, _ in _named_entries(FLANGE)] == ["DT"]
    assert [k for k, _, _ in _named_entries(ANNULAR)] == [
        "Su",
        "equivalenceRatio",
        "sigmaExt",
        "XiCoef",
        "XiShapeCoef",
        "uPrimeCoef",
        "ignitionThickness",
        "ignitionKernelArea",
    ]


@pytest.mark.parametrize(("path", "key", "dims", "value"), _real_params("object"))
def test_real_file_named_entry_exposes_name_dimensions_and_value(
    path, key, dims, value
):
    entry = getattr(_load(path), key)
    assert entry.name == key
    assert _dims(entry) == dims
    assert _is_number(entry.value)
    assert entry.value == pytest.approx(value)


@pytest.mark.parametrize(("path", "key", "dims", "value"), _real_params("regen"))
def test_real_file_regenerated_entry_has_name_dimensions_and_value(
    path, key, dims, value
):
    _ = value
    assert _has(_regen(_load(path)), _expected(key, True, dims, value))


@pytest.mark.parametrize("path", [FLANGE, ANNULAR], ids=lambda p: p.name.split(".")[1])
def test_real_file_unedited_write_is_the_source(path):
    assert _load(path).toString() == path.read_text()


@pytest.mark.parametrize("path", [FLANGE, ANNULAR], ids=lambda p: p.name.split(".")[1])
def test_real_file_second_regenerated_write_equals_the_first(tmp_path, path):
    text1 = _regen(_load(path))
    out = tmp_path / path.name
    out.write_text(text1)
    assert _regen(_load(out)) == text1


@pytest.mark.parametrize(("path", "key", "dims", "value"), _real_params("regen"))
def test_real_file_regenerated_text_read_back_keeps_name_dimensions_and_value(
    tmp_path, path, key, dims, value
):
    out = tmp_path / path.name
    out.write_text(_regen(_load(path)))
    assert _has(_regen(_load(out)), _expected(key, True, dims, value))


@pytest.mark.parametrize(("path", "key", "dims", "value"), _real_params("edit"))
def test_real_file_assigned_value_is_written(path, key, dims, value):
    _ = value
    d = _load(path)
    getattr(d, key).value = 7.25
    assert _has(d.toString(), _expected(key, True, dims, 7.25))


# --- shapes the bracket reader does not read exactly (T-081's): not newly typed ----------------------
@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize(
    "line",
    [
        "nu nu [0 2 -1 0 0 0] 1e-5 a;",  # six exponents
        "nu nu [0 2 -1 0 0 0 x] 1e-5;",  # a non-integer token
        "nu nu [0 2 -1 0 0 0 0 0] 1;",  # eight exponents
        "nu nu [0 2 -1 0 0 0 0]1.5 a b;",  # text glued to the bracket
    ],
)
def test_unread_bracket_shapes_stay_text_and_lose_no_token(tmp_path, cont, line):
    d = _read(tmp_path, line, cont)
    assert type(_scope(d, cont).nu) is fkt.ofStr
    for text in (d.toString(), _regen(d)):
        assert _has(text, _toks(line))


# - A named entry split over lines: the key and name alone on a line is a loud error (not
# - touched); the bracket and value on the next line are read.
def test_named_entry_with_the_value_on_the_next_line_is_read(tmp_path):
    d = _read(tmp_path, "nu nu [0 2 -1 0 0 0 0]\n1e-5;", "top")
    assert type(d.nu) is fkt.ofDimensionedScalar
    assert _has(_regen(d), _expected("nu", True, DIMS, 1e-5))


def test_named_entry_with_the_brackets_on_another_line_is_an_error(tmp_path):
    with pytest.raises(FoamKitError, match="line"):
        _read(tmp_path, "nu nu\n[0 2 -1 0 0 0 0]\n1e-5;", "top")


# --- named entries with a non-scalar value (T-014 review round 1) --------------------------------
@pytest.mark.parametrize(
    "line",
    [
        pytest.param(
            "s s [0 0 0 0 0 0 0] (1);",
            id="spherical",
            marks=pytest.mark.xfail(
                strict=True,
                reason="T-081: the value of a named entry with a tensor value is dropped on "
                "regeneration (as on main; it no longer raises a bare TypeError)",
            ),
        ),
        pytest.param("s s [0 0 0 0 0 0 0] (1 0 0 1 0);", id="symm"),
    ],
)
@pytest.mark.parametrize("cont", CONTAINERS)
def test_named_entry_with_a_tensor_value_loads_and_keeps_its_text(tmp_path, line, cont):
    """Only the scalar form keeps an inner name; a named entry with a tensor value stays on
    the old path (never a bare TypeError), and its text is kept on every write path."""
    d = _read(tmp_path, line, cont)
    assert d.toString() == HEADER + _wrap(line + NL, cont)
    regen = _regen(d)
    assert _has(regen, _toks(line)), regen
