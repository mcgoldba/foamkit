"""`#includeFunc` with arguments, and original quoting, on read and write (T-015, option A).

Form sources:
- Foundation 11 `tutorials/incompressibleFluid/pitzDaily/system/controlDict`
  (byte-exact in tests/releases/): `patchAverage(patch=inlet, fields=(p U))`.
- Foundation 12, 13 and 14 pitzDaily controlDicts (fetched 2026-10-19) contain no
  `#includeFunc` line, so they add no forms.
- ESI v2606 controlDict (tests/fixtures/headers/): only the bare `#includeFunc streamlines`.
  ESI argument forms are NOT confirmed against a real ESI file.
- positional `mag(U)`, `streamlines(U, name=s)`, the nested `graphUniform(...)` and the
  `name=` override come from the T-015 ticket text and are not confirmed against a real file.
- pitzDaily fixture: `streamlines` and `writeObjects(kEpsilon:G)`.

tests/releases/ is deliberately outside tests/fixtures/ (which test_golden.py globs and
requires a golden for): foundation-11.controlDict cannot load before T-015, so no golden
can exist yet. After the fix, the implementer may move it to tests/fixtures/releases/ and
generate its golden.
"""

import pytest

import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import FIXTURES, TESTS
from test_directives import HEADER, _directive_lines, _roundtrip

RELEASES = TESTS / "releases"
FORMS = [
    "streamlines",
    "mag(U)",
    "streamlines(U)",
    "streamlines(U, name=s)",
    "writeObjects(kEpsilon:G)",
    "patchAverage(patch=inlet, fields=(p U))",
    "graphUniform(funcName=l, start=(0 0 0), end=(1 0 0), nPoints=100, fields=(U))",
    "patchAverage(name=inletP, patch=inlet, fields=(p))",
]
FORM_IDS = [f.split("(")[0] + str(i) for i, f in enumerate(FORMS)]

# - A sibling dictionary after the include checks that following entries survive.
FUNCTIONS = (
    "functions\n{{\n    {line}\n\n    probes\n    {{\n        type            probes;\n"
    "        writeInterval   1;\n    }}\n}}\n"
)


def _wrap_top(line):
    return f"{line}\n\nx 1;\n"


def _wrap_functions(line):
    return FUNCTIONS.format(line=line)


WRAPPERS = pytest.mark.parametrize(
    "wrap", [_wrap_top, _wrap_functions], ids=["top-level", "in-functions"]
)


# --- unquoted input stays unquoted -------------------------------------------


@WRAPPERS
@pytest.mark.parametrize("form", FORMS, ids=FORM_IDS)
def test_unquoted_includeFunc_is_written_unquoted(tmp_path, wrap, form):
    _, _, text = _roundtrip(tmp_path, wrap(f"#includeFunc {form}"))
    assert _directive_lines(text) == [f"#includeFunc {form}"]


@WRAPPERS
@pytest.mark.parametrize("form", FORMS, ids=FORM_IDS)
def test_unquoted_includeFunc_second_write_is_stable(tmp_path, wrap, form):
    _, second, text = _roundtrip(tmp_path, wrap(f"#includeFunc {form}"))
    assert second.toString() == text


@pytest.mark.parametrize("form", FORMS, ids=FORM_IDS)
def test_includeFunc_with_arguments_keeps_following_entries(tmp_path, form):
    first, _, _ = _roundtrip(tmp_path, _wrap_top(f"#includeFunc {form}"))
    assert first.x.value == 1


def test_includeFunc_in_functions_keeps_sibling_dictionary(tmp_path):
    line = "#includeFunc patchAverage(patch=inlet, fields=(p U))"
    first, _, text = _roundtrip(tmp_path, _wrap_functions(line))
    assert first.functions.probes.writeInterval.value == 1
    assert "probes" in text


# --- quoted input stays quoted -----------------------------------------------


@WRAPPERS
@pytest.mark.parametrize(
    "form", ["streamlines", "streamlines(U)", "writeObjects(kEpsilon:G)"]
)
def test_quoted_includeFunc_is_written_quoted(tmp_path, wrap, form):
    line = f'#includeFunc "{form}"'
    _, second, text = _roundtrip(tmp_path, wrap(line))
    assert _directive_lines(text) == [line]
    assert second.toString() == text


def test_quoted_and_unquoted_includeFunc_in_one_file_keep_their_own_quoting(tmp_path):
    body = _wrap_functions(
        '#includeFunc a\n    #includeFunc "b"\n    #includeFunc c(U)'
    )
    _, _, text = _roundtrip(tmp_path, body)
    assert _directive_lines(text) == [
        "#includeFunc a",
        '#includeFunc "b"',
        "#includeFunc c(U)",
    ]


def test_includeFunc_is_still_an_ofIncludeFunc_with_arguments(tmp_path):
    first, _, _ = _roundtrip(tmp_path, _wrap_top("#includeFunc streamlines(U, name=s)"))
    incl = next(v for v in vars(first).values() if isinstance(v, fkt.ofInclude))
    assert type(incl) is fkt.ofIncludeFunc


# --- trailing comments ---------------------------------------------------------


@pytest.mark.parametrize("comment", ["// note", "/* note */"])
def test_includeFunc_trailing_comment_is_not_part_of_the_arguments(tmp_path, comment):
    """Comments are dropped on read today (also for `#include`); the arguments stay intact."""
    first, second, text = _roundtrip(
        tmp_path, _wrap_top(f"#includeFunc streamlines(U, name=s) {comment}")
    )
    assert _directive_lines(text) == ["#includeFunc streamlines(U, name=s)"]
    assert first.x.value == 1
    assert second.toString() == text


# --- unbalanced parentheses ------------------------------------------------------


@pytest.mark.parametrize("line", ["#includeFunc mag(U", "#includeFunc mag((U)"])
@WRAPPERS
def test_unbalanced_parentheses_raise_foamkit_error_naming_file_and_line(
    tmp_path, wrap, line
):
    path = tmp_path / "badControlDict"
    body = wrap(line)
    path.write_text(HEADER + body)
    lineno = HEADER.count("\n") + 1 + body.split(line)[0].count("\n")
    with pytest.raises(FoamKitError) as exc:
        fkt.DictFileParser(path).readDictFile()
    assert "badControlDict" in str(exc.value)
    assert str(lineno) in str(exc.value)


# --- real files ----------------------------------------------------------------------


def test_foundation_11_pitzDaily_controlDict_loads_and_keeps_the_include_verbatim():
    src = RELEASES / "foundation-11.controlDict"
    text = fkt.DictFileParser(src).readDictFile().toString()
    assert _directive_lines(text) == [
        "#includeFunc patchAverage(patch=inlet, fields=(p U))"
    ]


def test_foundation_11_pitzDaily_controlDict_keeps_entries_around_the_include():
    d = fkt.DictFileParser(RELEASES / "foundation-11.controlDict").readDictFile()
    assert d.maxCo.value == 5
    assert d.endTime.value == 0.3
    assert "functions" in vars(d)


def test_foundation_11_pitzDaily_controlDict_rewrite_is_stable(tmp_path):
    first = fkt.DictFileParser(RELEASES / "foundation-11.controlDict").readDictFile()
    text = first.toString()
    out = tmp_path / "controlDict"
    out.write_text(text)
    assert fkt.DictFileParser(out).readDictFile().toString() == text


def test_esi_v2606_bare_includeFunc_is_written_unquoted():
    d = fkt.DictFileParser(
        FIXTURES / "headers" / "esi-v2606.controlDict"
    ).readDictFile()
    assert "#includeFunc streamlines" in _directive_lines(d.toString())


def test_pitzDaily_fixture_includeFuncs_are_written_unquoted():
    d = fkt.DictFileParser(
        FIXTURES / "pitzDaily" / "system" / "controlDict"
    ).readDictFile()
    assert _directive_lines(d.toString()) == [
        "#includeFunc streamlines",
        "#includeFunc writeObjects(kEpsilon:G)",
    ]


# --- quoted argument values (T-015 follow-up) ----------------------------------

QUOTED_ARGS = [
    '#includeFunc foo(name="(")',
    '#includeFunc foo(name=")")',
    '#includeFunc foo(url="http://x")',
    '#includeFunc foo(a="x\\"y")',
]


@WRAPPERS
@pytest.mark.parametrize(
    "line", QUOTED_ARGS, ids=["open", "close", "slashes", "escaped"]
)
def test_quoted_argument_value_round_trips_verbatim(tmp_path, wrap, line):
    """Brackets, `//` and `\\"` inside a quoted value are data, not syntax."""
    first, second, text = _roundtrip(tmp_path, wrap(line))
    assert _directive_lines(text) == [line]
    assert second.toString() == text


@pytest.mark.parametrize(
    "line", QUOTED_ARGS, ids=["open", "close", "slashes", "escaped"]
)
def test_quoted_argument_value_keeps_following_entries(tmp_path, line):
    first, _, _ = _roundtrip(tmp_path, _wrap_top(line))
    assert first.x.value == 1


def test_quoted_argument_value_in_functions_keeps_sibling_dictionary(tmp_path):
    first, _, _ = _roundtrip(
        tmp_path, _wrap_functions('#includeFunc foo(url="http://x")')
    )
    assert first.functions.probes.writeInterval.value == 1


@WRAPPERS
def test_unterminated_quote_raises_foamkit_error_naming_file_and_line(tmp_path, wrap):
    line = '#includeFunc foo(name="abc)'
    path = tmp_path / "badControlDict"
    body = wrap(line)
    path.write_text(HEADER + body)
    lineno = HEADER.count("\n") + 1 + body.split(line)[0].count("\n")
    with pytest.raises(FoamKitError) as exc:
        fkt.DictFileParser(path).readDictFile()
    assert "badControlDict" in str(exc.value)
    assert str(lineno) in str(exc.value)


@WRAPPERS
def test_unquoted_double_slash_in_arguments_is_still_a_comment(tmp_path, wrap):
    """Regression guard: OpenFOAM reads an unquoted `//` as a comment start, so the
    closing parenthesis is lost. Pinned current behaviour: FoamKitError
    ("Unbalanced parentheses in #includeFunc on line N of file ...")."""
    path = tmp_path / "badControlDict"
    path.write_text(HEADER + wrap("#includeFunc foo(url=http://x)"))
    with pytest.raises(FoamKitError, match="Unbalanced parentheses"):
        fkt.DictFileParser(path).readDictFile()
