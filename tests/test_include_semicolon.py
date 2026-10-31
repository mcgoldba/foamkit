"""Include directives followed by `;` (T-046, issue #62).

Specification tests for docs/tickets/T-046-include-with-semicolon.md.  OpenFOAM accepts
`#include "f";` (entry::getKeyword skips END_STATEMENT tokens: Foundation 11 entryIO.C:50,
ESI v2412 entryIO.C:54), so these files are valid and must load and round-trip: the `;` is
not part of the value, it is written back exactly once, and the written file re-reads.

Outcome of the reproduction table on this branch (c4a810d):

    #include "f";  (top level, sub-dict), #sinclude,    value is `f";`; written as
    #includeIfPresent, #includeEtc "caseDicts/x";       `#include    "f";"` (unreadable:
                                                        "Unterminated string")
    #includeFunc streamlines;  /  enstrophy(...=no);    value keeps the `;`; written with it
                                                        (already round-trips)
    #include "f" (no `;`)                               round-trips (guard)
    d { value #include "f"; }                           TypeError on load (same without `;`)
    #include "f" ;  (space before `;`)                  TypeError on load, same cause
    x ( #include "f"; );                                FoamKitError "list closes in the
                                                        middle of a line" (loud, guard)
    x (newline #include "f"; 1 newline );              FoamKitError "Unhandled pattern
                                                        found!" (loud, guard)

`iterDirectives` differs from the ticket's line "`iterDirectives` lists it": it walks
`ofVerbatimDirective` items only, `ofInclude` is not one, so it yields nothing for any
include directive today, with or without a `;`, for every `status` filter.  The test
`test_iterdirectives_does_not_list_includes_today` pins that (the T-042 finding).

Real files (byte-exact copies in tests/releases/, outside the golden glob): ESI OpenFOAM-v2606,
commit 481094fdf34f11ed6d0d603ee59a858a0124236d of https://gitlab.com/openfoam/core/openfoam,
extracted with `git show HEAD:<path>` (the working copy is CRLF); `git hash-object` of each
copy equals the blob id, and `cmp` against
https://gitlab.com/openfoam/core/openfoam/-/raw/481094fdf34f11ed6d0d603ee59a858a0124236d/<path>
shows no difference.  Neither file contains a CR.

esi-v2606.blob.collapseDict    (`#include "meshQualityDict";`, line 62)
  tutorials/mesh/foamyHexMesh/blob/system/collapseDict
  blob 02dff10e12ddca9164cf97da7db32dffacb52d1d
esi-v2606.flange.faceSetDict   (`value #include "../facesToBeRemoved";`, line 30)
  tutorials/mesh/foamyHexMesh/flange/system/faceSetDict
  blob cb41adf922537207e187d37017bbfd1284fa3095
"""

import re

import pytest

import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import TESTS
from test_directives import HEADER

NL = "\n"
RELEASES = TESTS / "releases"
COLLAPSE = RELEASES / "esi-v2606.blob.collapseDict"
FACESET = RELEASES / "esi-v2606.flange.faceSetDict"
AFTER_BANNER = "//\n\n"
INCLUDES = (fkt.ofInclude, fkt.ofIncludeEtc, fkt.ofIncludeFunc)


def _load(path):
    return fkt.DictFileParser(path).readDictFile()


def _children(node):
    if isinstance(node, fkt.ofDict):
        return [v for k, v in vars(node).items() if not k.startswith("_")]
    return []


def _walk(node):
    for child in _children(node):
        yield child
        yield from _walk(child)


def _includes(node):
    return [n for n in _walk(node) if isinstance(n, INCLUDES)]


def _shape(node):
    """Structure of the entries: keys and leaf types and values (comments left out)."""
    if isinstance(node, fkt.ofDict):
        return (
            "dict",
            [
                (k, _shape(v))
                for k, v in vars(node).items()
                if not k.startswith("_") and type(v).__name__ != "ofComment"
            ],
        )
    if isinstance(node, fkt.ofList):
        return (type(node).__name__, [_shape(i) for i in node.value])
    return (type(node).__name__, repr(getattr(node, "_value", None)))


def _unpad(line):
    """A directive line without indent and with one space after the keyword (T-020)."""
    return re.sub(r"^(#\w+)\s+", r"\1 ", line.strip())


def _directive_lines(text):
    return [_unpad(ln) for ln in text.splitlines() if ln.strip().startswith("#")]


def _cycle(tmp_path, text):
    """Write `text`, read, write, re-read, write: (first, second, text1, text2)."""
    path = tmp_path / "semi"
    path.write_text(text)
    first = _load(path)
    text1 = first.toString()
    out = tmp_path / "wa"
    out.write_text(text1)
    second = _load(out)
    return first, second, text1, second.toString()


def _sub(body):
    return "d\n{\n" + "".join("    " + ln + NL for ln in body.splitlines()) + "}\n"


# --- the family, with a `;` ---------------------------------------------------------------
# - (directive text as written, value expected after the fix)
FAMILY = [
    ('#include "f";', "f"),
    ('#sinclude "f";', "f"),
    ('#includeIfPresent "f";', "f"),
    ('#includeEtc "caseDicts/x";', "caseDicts/x"),
    ("#includeFunc streamlines;", "streamlines"),
    ("#includeFunc enstrophy(executeAtStart=no);", "enstrophy(executeAtStart=no)"),
    ("#includeFunc foo(a, b);", "foo(a, b)"),
    ('#includeFunc "x";', "x"),
]
CASES = []
for _directive, _value in FAMILY:
    _kw = _directive.split()[0][1:]
    for _cont in ("top", "sub"):
        _text = f"{_directive}\nx 1;\n"
        _id = f"{_kw}-{_cont}" + ("-args" if "(" in _directive else "")
        CASES.append(
            pytest.param(
                _text if _cont == "top" else _sub(_text), _directive, _value, id=_id
            )
        )


def test_the_reproduction_table_is_covered():
    assert {p.id.split("-")[0] for p in CASES} == {
        "include",
        "sinclude",
        "includeIfPresent",
        "includeEtc",
        "includeFunc",
    }
    assert len(CASES) == 2 * len(FAMILY)


@pytest.mark.parametrize(
    ("text", "directive", "value"),
    CASES,
)
def test_the_value_does_not_contain_the_semicolon(tmp_path, text, directive, value):
    path = tmp_path / "semi"
    path.write_text(HEADER + text)
    found = _includes(_load(path))
    assert len(found) == 1
    assert found[0].value == value


@pytest.mark.parametrize(
    ("text", "directive", "value"),
    CASES,
)
def test_written_directive_line_keeps_exactly_one_semicolon(
    tmp_path, text, directive, value
):
    text1 = _cycle_write_only(tmp_path, HEADER + text)
    assert _directive_lines(text1).count(directive) == 1


def _cycle_write_only(tmp_path, text):
    path = tmp_path / "semi"
    path.write_text(text)
    return _load(path).toString()


@pytest.mark.parametrize(
    ("text", "directive", "value"),
    CASES,
)
def test_written_text_reads_back_to_the_same_entries(tmp_path, text, directive, value):
    first, second, _, _ = _cycle(tmp_path, HEADER + text)
    assert _shape(first) == _shape(second)
    assert len(_includes(second)) == 1


@pytest.mark.parametrize(
    ("text", "directive", "value"),
    CASES,
)
def test_second_write_equals_the_first(tmp_path, text, directive, value):
    _, _, text1, text2 = _cycle(tmp_path, HEADER + text)
    assert text1 == text2


@pytest.mark.parametrize(("text", "directive", "value"), CASES)
def test_the_entry_after_the_directive_is_kept(tmp_path, text, directive, value):
    path = tmp_path / "semi"
    path.write_text(HEADER + text)
    d = _load(path)
    holder = d if text.startswith("#") else d.d
    assert holder.x.value == 1


# --- iterDirectives: pins what is true today ----------------------------------------------
@pytest.mark.parametrize("directive", [d for d, _ in FAMILY] + ['#include "f"'])
@pytest.mark.parametrize(
    "status", [None, "verbatim", "unknown", "interpreted", "unsupported"]
)
def test_iterdirectives_does_not_list_includes_today(tmp_path, directive, status):
    """The ticket says `iterDirectives` lists it; it does not (ofInclude is not verbatim)."""
    path = tmp_path / "semi"
    path.write_text(HEADER + directive + "\nx 1;\n")
    assert list(fkt.iterDirectives(_load(path), status)) == []


# --- value position: `d { value #include "f"; }` ------------------------------------------
VALUE_POS = [
    pytest.param('d\n{\n    value #include "../f";\n    a 1;\n}\n', id="semicolon"),
    pytest.param('d\n{\n    value #include "../f"\n    a 1;\n}\n', id="no-semicolon"),
    pytest.param('d\n{\n    value #include "../f";\n}\n', id="semicolon-only-entry"),
]


@pytest.mark.parametrize("text", VALUE_POS)
def test_value_position_include_round_trips_or_raises_foamkiterror(tmp_path, text):
    path = tmp_path / "valpos"
    path.write_text(HEADER + text)
    try:
        text1 = _load(path).toString()
    except FoamKitError as err:
        msg = str(err)
        assert "valpos" in msg
        assert re.search(r"\bline (\d+)\b", msg, re.IGNORECASE), msg
        return
    assert '"../f"' in text1
    out = tmp_path / "wa"
    out.write_text(text1)
    assert _load(out).toString() == text1


@pytest.mark.parametrize(
    ("text", "value", "written"),
    [
        pytest.param('#include "f" ;', "f", '#include "f";', id="include"),
        pytest.param("#includeFunc x ;", "x", "#includeFunc x;", id="includeFunc"),
    ],
)
def test_a_space_before_the_semicolon_loads_and_writes_one_semicolon(
    tmp_path, text, value, written
):
    # - the space before the `;` is layout only (T-020)
    first, second, text1, text2 = _cycle(tmp_path, HEADER + text + "\nx 1;\n")
    assert [i.value for i in _includes(first)] == [value]
    assert _directive_lines(text1) == [written]
    assert text1 == text2
    assert _shape(first) == _shape(second)


@pytest.mark.parametrize(
    "text",
    ['#include "f";;', '#include "f"; ;', '#includeFunc "x";;', 'a 1; #include "f";;'],
)
def test_more_than_one_semicolon_raises_foamkiterror_with_file_and_line(tmp_path, text):
    path = tmp_path / "semis"
    path.write_text(HEADER + text + "\nx 1;\n")
    with pytest.raises(FoamKitError) as err:
        _load(path)
    msg = str(err.value)
    assert "More than one ';'" in msg
    assert "semis" in msg
    assert re.search(r"\bline (\d+)\b", msg, re.IGNORECASE), msg


# --- includes in a list with a `;` (T-042 shape): loud errors today -----------------------
LIST_SEMI = [
    pytest.param('x ( #include "f"; );\n', id="one-line"),
    pytest.param('x\n(\n    #include "f";\n    1\n);\n', id="multi-line"),
]


@pytest.mark.parametrize("text", LIST_SEMI)
def test_a_semicolon_inside_a_list_after_an_include_is_a_foamkiterror_today(
    tmp_path, text
):
    """A `;` inside `( )` is not an empty statement there; characterize the loud error."""
    path = tmp_path / "inlist"
    path.write_text(HEADER + text)
    with pytest.raises(FoamKitError):
        _load(path)


# --- guards that must keep passing --------------------------------------------------------
GUARDS = [
    ('#include "f"', '#include    "f"\n\n'),
    ('#sinclude "f"', '#sinclude   "f"\n\n'),
    ('#includeIfPresent "f"', '#includeIfPresent\t"f"\n\n'),
    ('#includeEtc "caseDicts/f"', '#includeEtc "caseDicts/f"\n\n'),
    ("#includeFunc foo(a, b)", "#includeFunc\tfoo(a, b)\n\n"),
]


@pytest.mark.parametrize(("directive", "written"), GUARDS)
def test_include_without_a_semicolon_is_unchanged_at_top_level(
    tmp_path, directive, written
):
    path = tmp_path / "g"
    path.write_text(HEADER + directive + "\nx 1;\n")
    text = _load(path).toString().split(AFTER_BANNER, 1)[1]
    assert text == written + "\nx           1; \n\n"


@pytest.mark.parametrize(("directive", "written"), GUARDS)
def test_include_without_a_semicolon_is_unchanged_in_a_sub_dict(
    tmp_path, directive, written
):
    path = tmp_path / "g"
    path.write_text(HEADER + "sub\n{\n" + directive + "\n    x 1;\n}\n")
    text = _load(path).toString().split(AFTER_BANNER, 1)[1]
    assert text == "sub\n{\n    " + written + "    x           1; \n}\n\n\n"


@pytest.mark.parametrize(("directive", "written"), GUARDS)
def test_include_without_a_semicolon_has_a_value_without_one(
    tmp_path, directive, written
):
    path = tmp_path / "g"
    path.write_text(HEADER + directive + "\nx 1;\n")
    (inc,) = _includes(_load(path))
    assert ";" not in str(inc.value)


def test_include_inside_a_list_is_unchanged(tmp_path):
    path = tmp_path / "g"
    path.write_text(HEADER + 'x ( #include "f" 1 2 );\n')
    first = _load(path)
    assert '#include "f"' in " ".join(first.toString().split())
    assert any(isinstance(i, fkt.ofInclude) for i in first.x.value)


# --- the real files -----------------------------------------------------------------------
def test_fixtures_are_the_lf_copies_with_the_documented_lines():
    for path, line_no, needle in (
        (COLLAPSE, 62, b'#include                    "meshQualityDict";'),
        (FACESET, 30, b'value #include "../facesToBeRemoved";'),
    ):
        data = path.read_bytes()
        assert b"\r" not in data
        assert needle in data.split(b"\n")[line_no - 1]


def test_collapsedict_loads_and_has_the_include():
    (inc,) = _includes(_load(COLLAPSE))
    assert isinstance(inc, fkt.ofInclude)


def test_collapsedict_include_value_is_the_file_name():
    (inc,) = _includes(_load(COLLAPSE))
    assert inc.value == "meshQualityDict"


def test_collapsedict_keeps_the_directive_line_with_one_semicolon():
    lines = _directive_lines(_load(COLLAPSE).toString())
    assert lines == ['#include "meshQualityDict";']


def test_collapsedict_writes_and_rereads(tmp_path):
    first = _load(COLLAPSE)
    out = tmp_path / "wa"
    out.write_text(first.toString())
    assert _shape(_load(out)) == _shape(first)


def test_collapsedict_second_write_equals_the_first(tmp_path):
    text1 = _load(COLLAPSE).toString()
    out = tmp_path / "wa"
    out.write_text(text1)
    assert _load(out).toString() == text1


def test_facesetdict_loads_or_raises_foamkiterror_with_file_and_line():
    try:
        text1 = _load(FACESET).toString()
    except FoamKitError as err:
        msg = str(err)
        assert "esi-v2606.flange.faceSetDict" in msg
        assert re.search(r"\bline 30\b", msg, re.IGNORECASE), msg
        return
    assert '"../facesToBeRemoved"' in text1
