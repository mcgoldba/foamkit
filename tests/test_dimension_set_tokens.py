"""Dimension sets and dimensioned values keep every token (T-081, issue #108).

Specification tests for docs/tickets/T-081-dimension-sets-keep-every-token.md, option A:
a shape FoamKit does not type is kept verbatim as `ofStr`.

An unedited file is written back byte for byte (the original text is kept), so the loss
only shows when an entry is regenerated: `toString(_preserve=False)`, or any edit inside a
sub-dictionary (the whole sub-dictionary is regenerated).  Both are tested.

Each "bold" row of the ticket's "Today" table is tested at the top level and in a
sub-dictionary: the written text has the same tokens in the same order (numbers compared
by value), write 1 == write 2, or the load raises `FoamKitError` naming the file and line.
A bare exception (`ValueError`, `AttributeError`, `TypeError`, `Exception`) is reported as
an `AssertionError` by the helpers, so every failing test here fails with `AssertionError`.

Rows that are lossless today are pinned (they pass now and must keep passing).

The real Foundation 11 file below is embedded byte for byte (commit
9cbf94f3339dd49286633b303c4155fd10ea8200 of OpenFOAM/OpenFOAM-11, path
tutorials/compressibleVoF/throttle/constant/thermodynamicProperties, git blob
c33def899ba2f81f2d6d255db90953d81cd02280, fetched with curl from raw.githubusercontent.com).
"""

import re

import pytest

from foamkit import FoamKitError
from test_directives import HEADER
from test_several_lists_value import _load

WHERE = ["top", "sub"]
FAIL = "fails today"

# id -> (body, type after the change, loses data today)
ROWS = {
    # --- bold rows of the "Today" table ---
    "letter-in-3rd-exponent": ("nu [0 2 a 0 0 0 0] 1;", "ofStr", True),
    "letter-in-1st-exponent": ("nu [a 2 -1 0 0 0 0] 1;", "ofStr", True),
    "letter-in-7th-exponent": ("nu [0 2 -1 0 0 0 a] 1;", "ofStr", True),
    "fractional-exponent": ("nu [0 2 -1.5 0 0 0 0] 1;", "ofStr", True),
    "six-exponents": ("nu [0 2 -1 0 0 0] 1;", "ofStr", True),
    "six-exponents-vector": ("U [0 1 -1 0 0 0] (1 0 0);", "ofStr", True),
    "six-exponents-uniform": ("v [0 1 -1 0 0 0] uniform 1;", "ofStr", True),
    "gravity-vector-non-integer": ("g [0 1 -2 0 0 0 0] (0 -9.81 0);", "ofStr", True),
    "value-is-a-word": ("nu [0 2 -1 0 0 0 0] abc;", "ofStr", True),
    "value-is-a-variable": ("nu [0 2 -1 0 0 0 0] $x;", "ofStr", True),
    "value-is-a-switch": ("nu [0 2 -1 0 0 0 0] on;", "ofStr", True),
    "value-before-the-brackets": ("nu 1e-05 [0 2 -1 0 0 0 0];", "ofStr", True),
    "numbers-around-brackets": ("x 1 2 [3] 4 5 6 7;", "ofStr", True),
    "symm-tensor-five-numbers": ("s [0 2 -2 0 0 0 0] (1 0 0 0 0);", "ofStr", True),
    "spherical-tensor-one-number": ("s [0 2 -2 0 0 0 0] (1);", "ofStr", True),
    # --- bold rows that already pass (fixed by T-014 or earlier): pinned ---
    "spaced-brackets": (
        "nu [ 0 2 -1 0 0 0 0 ] 1e-05;",
        "ofDimensionedScalar",
        False,
    ),
    "eight-exponents": ("nu [0 2 -1 0 0 0 0 0] 1;", "ofStr", False),
    "nine-exponents": ("nu [0 2 -1 0 0 0 0 0 0] 1;", "ofStr", False),
}

# rows that raise a bare exception today (at load or at write)
RAISES_AT_LOAD = {"symm-tensor-five-numbers", "spherical-tensor-one-number"}

# id -> (body, type): already lossless today (pinned)
LOSSLESS = {
    "scalar": ("nu [0 2 -1 0 0 0 0] 1e-05;", "ofDimensionedScalar"),
    "scalar-tabs": ("nu\t[0 2 -1 0 0 0 0]\t1e-05;", "ofDimensionedScalar"),
    "scalar-two-spaces": ("nu  [0 2 -1 0 0 0 0]  1e-05;", "ofDimensionedScalar"),
    "scalar-space-before-semicolon": (
        "nu [0 2 -1 0 0 0 0] 1e-05 ;",
        "ofDimensionedScalar",
    ),
    "scalar-value-on-next-line": (
        "nu [0 2 -1 0 0 0 0]\n1e-05;",
        "ofDimensionedScalar",
    ),
    "scalar-negative": ("nu [0 2 -1 0 0 0 0] -1;", "ofDimensionedScalar"),
    "dimensions-entry": ("dimensions [0 1 -1 0 0 0 0];", "ofNamedDimension"),
    "dimension-set-only": ("nu [0 2 -1 0 0 0 0];", "ofNamedDimension"),
    "five-exponents": ("nu [0 2 -1 0 0] 1e-05;", "ofStr"),
    "five-exponents-dimensions": ("dimensions [0 1 -1 0 0];", "ofStr"),
    "value-glued-to-bracket": ("nu [0 2 -1 0 0 0 0]1e-05;", "ofStr"),
    "two-values": ("nu [0 2 -1 0 0 0 0] 1 2;", "ofStr"),
    "empty-brackets": ("nu [] 1;", "ofStr"),
    "letter-dimensions": ("dimensions [0 1 a 0 0 0 0];", "ofStr"),
    "vector-value": ("U [0 1 -1 0 0 0 0] (1 0 0);", "ofStr"),
    "tensor-nine-numbers": ("T [0 2 -2 0 0 0 0] (1 2 3 4 5 6 7 8 9);", "ofStr"),
    "symm-tensor-named-dims": ("s [dims] (1 2 3 4 5 6);", "ofStr"),
    "uniform-vector": ("v [0 1 -1 0 0 0 0] uniform (1 0 0);", "ofStr"),
    # T-013 forms: stay text
    "unit-name-slash": ("nu [m^2/s] 1e-05;", "ofStr"),
    "unit-name-powers": ("nu [m^2 s^-1] 1e-05;", "ofStr"),
    "unit-name-velocity": ("nu [velocity] 1;", "ofStr"),
    "dimensions-velocity": ("dimensions [velocity];", "ofStr"),
    "dimensions-m-per-s": ("dimensions [m/s];", "ofStr"),
}


# --- helpers ----------------------------------------------------------------------------


def _sub(body):
    """The body as the content of a sub-dictionary `s` (4-space indent)."""
    lines = "".join("    " + ln + "\n" for ln in body.split("\n"))
    return "s\n{\n" + lines + "}\n"


def _text(where, body):
    return HEADER + (body + "\n" if where == "top" else _sub(body))


def _src(tmp_path, text, name="dimFile"):
    path = tmp_path / name
    path.write_bytes(text.encode())
    return path


def _num(tok):
    try:
        return float(tok)
    except ValueError:
        return tok


def _tokens(text):
    """Tokens of the entries after the header: brackets and parentheses are tokens, `;` is not;
    numbers are compared by value; comment lines and the header block are skipped."""
    lines = text.split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.startswith("// * * *"))
    body = "\n".join(ln for ln in lines[start + 1 :] if not ln.startswith("//"))
    return [_num(t) for t in re.findall(r"[\[\]()]|[^\s\[\]();]+", body)]


def _expected(where, body):
    return _tokens(_text(where, body))


def _is_located(exc, path):
    msg = str(exc)
    return path.name in msg and re.search(r"line \d+", msg) is not None


def _call(path, fn):
    """Run `fn`; a bare (non-FoamKit) exception becomes an AssertionError."""
    try:
        return fn()
    except FoamKitError:
        raise
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"bare {type(e).__name__}: {str(e)[:80]!r}") from e


def _regen(path):
    """Load and write with every entry regenerated; None if FoamKitError (checked)."""
    try:
        d = _call(path, lambda: _load(path))
        return _call(path, lambda: d.toString(_preserve=False))
    except FoamKitError as e:
        assert _is_located(e, path), f"error lacks file and line: {e}"
        return None


def _params(guard=False):
    out = []
    for w in WHERE:
        for k, (body, typ, fails) in ROWS.items():
            if guard and k in RAISES_AT_LOAD:
                continue  # bare exception today; covered by the xfail tests
            marks = ()
            if fails and not guard:
                marks = pytest.mark.xfail(
                    strict=True,
                    raises=AssertionError,
                    reason="T-081: dimension-set entry loses or shifts tokens on write",
                )
            out.append(pytest.param(w, k, id=f"{w}-{k}", marks=marks))
    return out


# --- the bold rows: same tokens, in order, write 1 == write 2, or a located error ---------


@pytest.mark.parametrize("where, row", _params())
def test_regenerated_write_keeps_every_token_in_order(tmp_path, where, row):
    body = ROWS[row][0]
    path = _src(tmp_path, _text(where, body))
    out = _regen(path)
    if out is None:
        return  # a located FoamKitError is acceptable
    assert _tokens(out) == _expected(where, body)


# - write 1 == write 2 already holds today for every row that loads (guard, not xfail)
@pytest.mark.parametrize("where, row", _params(guard=True))
def test_regenerated_write_one_equals_write_two(tmp_path, where, row):
    path = _src(tmp_path, _text(where, ROWS[row][0]))
    first = _regen(path)
    if first is None:
        return
    second = _regen(_src(tmp_path, first, "dimFile2"))
    assert second is not None
    assert second == first


@pytest.mark.parametrize("where, row", _params())
def test_unsupported_shape_is_kept_as_text_not_typed(tmp_path, where, row):
    """Option A: not exactly `[7 integers] number` -> `ofStr`; a located error is allowed."""
    body, typ, _ = ROWS[row]
    path = _src(tmp_path, _text(where, body))
    try:
        d = _call(path, lambda: _load(path))
    except FoamKitError as e:
        assert _is_located(e, path), f"error lacks file and line: {e}"
        return
    holder = d if where == "top" else d.s
    assert type(holder.__dict__[body.split()[0]]).__name__ == typ


@pytest.mark.parametrize("where, row", _params(guard=True))
def test_unedited_write_is_byte_identical(tmp_path, where, row):
    """Guard: the original text is kept for an unedited file (passes today when it loads)."""
    path = _src(tmp_path, _text(where, ROWS[row][0]))
    try:
        d = _call(path, lambda: _load(path))
        out = _call(path, d.toString)
    except FoamKitError as e:
        assert _is_located(e, path), f"error lacks file and line: {e}"
        return
    assert out.encode() == path.read_bytes()


@pytest.mark.parametrize(
    "row",
    [
        pytest.param(
            k,
            marks=pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="T-081: dimension-set entry loses or shifts tokens on write",
            ),
        )
        for k, v in ROWS.items()
        if v[2]
    ],
)
def test_editing_a_sibling_in_a_sub_dict_keeps_every_token(tmp_path, row):
    """A sub-dictionary is regenerated on any edit; the dimension entry must not change."""
    body = ROWS[row][0]
    path = _src(tmp_path, HEADER + _sub(body + "\nzz 1;"))
    try:
        d = _call(path, lambda: _load(path))
        d.s.zz.value = 2
        out = _call(path, d.toString)
    except FoamKitError as e:
        assert _is_located(e, path), f"error lacks file and line: {e}"
        return
    expected = _tokens(HEADER + _sub(body + "\nzz 2;"))
    assert _tokens(out) == expected


# --- pinned: spaced brackets are read as a dimensioned scalar (T-014) ---------------------


@pytest.mark.parametrize("where", WHERE)
def test_spaced_brackets_load_as_dimensioned_scalar_with_value(tmp_path, where):
    path = _src(tmp_path, _text(where, "nu [ 0 2 -1 0 0 0 0 ] 1e-05;"))
    d = _load(path)
    nu = (d if where == "top" else d.s).nu
    assert type(nu).__name__ == "ofDimensionedScalar"
    assert nu.value == 1e-05


# --- pinned: already lossless -----------------------------------------------------------

LOSSLESS_PARAMS = [
    pytest.param(w, k, id=f"{w}-{k}") for w in WHERE for k in LOSSLESS
]


@pytest.mark.parametrize("where, row", LOSSLESS_PARAMS)
def test_lossless_row_keeps_its_type(tmp_path, where, row):
    body, typ = LOSSLESS[row]
    path = _src(tmp_path, _text(where, body))
    holder = (lambda d: d if where == "top" else d.s)(_load(path))
    key = body.split()[0]
    assert type(holder.__dict__[key]).__name__ == typ


@pytest.mark.parametrize("where, row", LOSSLESS_PARAMS)
def test_lossless_row_unedited_write_is_byte_identical(tmp_path, where, row):
    path = _src(tmp_path, _text(where, LOSSLESS[row][0]))
    assert _load(path).toString().encode() == path.read_bytes()


@pytest.mark.parametrize("where, row", LOSSLESS_PARAMS)
def test_lossless_row_regenerated_write_keeps_tokens(tmp_path, where, row):
    body = LOSSLESS[row][0]
    out = _load(_src(tmp_path, _text(where, body))).toString(_preserve=False)
    assert _tokens(out) == _expected(where, body)
    again = _load(_src(tmp_path, out, "dimFile2")).toString(_preserve=False)
    assert again == out


@pytest.mark.parametrize("where", WHERE)
def test_dimensioned_scalar_value_is_read_by_value(tmp_path, where):
    d = _load(_src(tmp_path, _text(where, "nu [0 2 -1 0 0 0 0] 1e-05;")))
    assert (d if where == "top" else d.s).nu.value == 1e-05


@pytest.mark.parametrize("where", WHERE)
def test_named_dimension_exponents_are_read(tmp_path, where):
    d = _load(_src(tmp_path, _text(where, "dimensions [0 1 -1 0 0 0 0];")))
    dims = (d if where == "top" else d.s).dimensions
    assert type(dims).__name__ == "ofNamedDimension"
    assert [float(x) for x in dims.dimensions] == [0, 1, -1, 0, 0, 0, 0]


# --- real file: Foundation 11 compressibleVoF/throttle thermodynamicProperties -----------

THROTTLE_THERMO = """\
/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "constant";
    object      thermodynamicProperties;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

barotropicCompressibilityModel linear;

psiv            [0 -2 2 0 0] 2.5e-06;

rholSat         [1 -3 0 0 0] 830;

psil            [0 -2 2 0 0] 5e-07;

pSat            [1 -1 -2 0 0] 4500;

rhoMin          [1 -3 0 0 0] 0.001;

// ************************************************************************* //
"""
FIVE_EXP_KEYS = ["psiv", "rholSat", "psil", "pSat", "rhoMin"]


def _thermo(tmp_path):
    return _src(tmp_path, THROTTLE_THERMO, "thermodynamicProperties")


def test_throttle_thermodynamic_properties_unedited_write_is_byte_identical(tmp_path):
    path = _thermo(tmp_path)
    assert _load(path).toString().encode() == path.read_bytes()


@pytest.mark.parametrize("key", FIVE_EXP_KEYS)
def test_throttle_five_exponent_entries_stay_text(tmp_path, key):
    d = _load(_thermo(tmp_path))
    assert type(d.__dict__[key]).__name__ == "ofStr"


def test_throttle_regenerated_write_keeps_every_token_of_the_five_exponent_entries(
    tmp_path,
):
    path = _thermo(tmp_path)
    out = _load(path).toString(_preserve=False)
    assert _tokens(out) == _tokens(THROTTLE_THERMO)
    again = _load(_src(tmp_path, out, "thermodynamicProperties2"))
    assert again.toString(_preserve=False) == out


def test_throttle_editing_one_entry_keeps_the_five_exponent_entries(tmp_path):
    path = _thermo(tmp_path)
    d = _load(path)
    d.barotropicCompressibilityModel.value = "perfectFluid"
    out = d.toString()
    assert _tokens(out) == _tokens(
        THROTTLE_THERMO.replace("linear", "perfectFluid")
    )
