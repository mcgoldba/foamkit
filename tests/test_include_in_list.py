"""`#include`-family directives inside a list (T-042, issue #57).

Specification tests for docs/tickets/T-042-include-inside-a-list.md.  A list that holds
`#include`, `#sinclude`, `#includeIfPresent`, `#includeEtc` or `#includeFunc` must load,
keep the directive as ONE include item and write it back on one line, unchanged.  Anything
that cannot be kept raises `FoamKitError` with file and line, never `TypeError` and never a
silent change ("errors never pass silently").

Outcome of the ticket's reproduction table on this branch (after T-040, a9a9447):

    helmholtzResonance blockMeshDict (F14, ESI v2606)   loads; toString() TypeError
                                                        (ofInclude.toString() takes no indent)
    x ( #include "f" a { b 1; } );   (multi-line)       loads; toString() TypeError, same
    blocks ( #include "f" hex ... ); (plain list)       loads; written as ofStr tokens
                                                        `#include` / `"f"` on two lines
    x ( #include "f" );              (one-line list)    same token split
    functions ( #includeFunc patchAverage(name=inlet, p) );
                                                        loads; written as `#includeFunc` /
                                                        `patchAverage` / `name=inlet,` / `p`:
                                                        the parentheses are lost (silent
                                                        corruption)
    #calc "1+2", #neg $a, #print "hi", $a in a plain list
                                                        separate tokens, stable (out of scope)

Not checked through `iterDirectives`: it walks attributes only (it does not descend into
lists) and yields only `ofVerbatimDirective` items, while `ofInclude` is "interpreted" and
is not listed even at dict level today.  The tests below check that the include item exists
in the list (`isinstance(item, ofInclude)`) instead.

Real files (byte-exact copies in tests/releases/, outside the golden glob):
- foundation-14.helmholtzResonance.blockMeshDict: see tests/test_entries_per_line.py.
- esi-v2606.helmholtzResonance.blockMeshDict: ESI OpenFOAM-v2606, commit
  481094fdf34f11ed6d0d603ee59a858a0124236d of https://gitlab.com/openfoam/core/openfoam,
  tutorials/compressible/rhoPimpleFoam/laminar/helmholtzResonance/system/blockMeshDict
  (blob 975b9acfd5c87ff048b5875433d7652bef074cc1).  Extracted with `git show HEAD:<path>`
  (the working copy is CRLF), `git hash-object` of the copy equals that blob id, and `cmp`
  against
  https://gitlab.com/openfoam/core/openfoam/-/raw/481094fdf34f11ed6d0d603ee59a858a0124236d/tutorials/compressible/rhoPimpleFoam/laminar/helmholtzResonance/system/blockMeshDict
  shows no difference.  Lines 150 and 193 are the `#include` lines in `blocks` and `boundary`.
"""

import re

import pytest

import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import TESTS
from test_directives import HEADER

NL = "\n"
RELEASES = TESTS / "releases"
HELM_F14 = RELEASES / "foundation-14.helmholtzResonance.blockMeshDict"
HELM_ESI = RELEASES / "esi-v2606.helmholtzResonance.blockMeshDict"
HL = HEADER.count(NL)


def _load(path):
    return fkt.DictFileParser(path).readDictFile()


def _norm(line):
    return " ".join(line.split())


def _lines(text):
    return [_norm(ln) for ln in text.splitlines()]


def _children(node):
    if isinstance(node, fkt.ofDict):
        return [v for k, v in vars(node).items() if not k.startswith("_")]
    if isinstance(node, fkt.ofList):
        return list(node.value)
    return []


def _walk(node):
    for child in _children(node):
        yield child
        yield from _walk(child)


def _in_lists(node):
    """Include items that sit inside a list (not at dict level)."""
    found = []
    for n in _walk(node):
        if isinstance(n, fkt.ofList):
            found += [i for i in n.value if isinstance(i, fkt.ofInclude)]
    return found


def _shape(node):
    """Structure of the entries: keys, list items and leaf types and values."""
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


def _cycle(tmp_path, text):
    """Write `text`, read, write, re-read, write: (first, second, text1, text2)."""
    path = tmp_path / "inList"
    path.write_text(text)
    first = _load(path)
    text1 = first.toString()
    out = tmp_path / "wa"
    out.write_text(text1)
    second = _load(out)
    return first, second, text1, second.toString()


def _sub(body):
    """Wrap `body` (lines) in a sub-dict, indented."""
    return "sub\n{\n" + "".join("    " + ln + NL for ln in body.splitlines()) + "}\n"


# --- the rows of the reproduction table ------------------------------------------------
# - (id, text, directive line, kind).  kind "dicts": the write raises TypeError today.
# - kind "tokens": it writes today, but as separate tokens.
FUNC = "#includeFunc patchAverage(name=inlet, p)"
ROWS = [
    (
        "list-of-dicts",
        'x\n(\n    #include "f"\n    a { b 1; }\n);\n',
        '#include "f"',
        "dicts",
    ),
    (
        "plain-list",
        'blocks\n(\n    #include "f"\n    hex (0 1 2 3) (1 1 1) simpleGrading (1 1 1)\n);\n',
        '#include "f"',
        "tokens",
    ),
    ("one-line-list", 'x ( #include "f" );\n', '#include "f"', "tokens"),
    ("one-line-list-items", 'x ( #include "f" 1 2 );\n', '#include "f"', "tokens"),
    ("includeFunc-args-one-line", f"functions ( {FUNC} );\n", FUNC, "tokens"),
    ("includeFunc-args-multi-line", f"functions\n(\n    {FUNC}\n);\n", FUNC, "tokens"),
    (
        "quoted-variable-path",
        'times ( #include "$FOAM_CASE/constant/meshTimes" );\n',
        '#include "$FOAM_CASE/constant/meshTimes"',
        "tokens",
    ),
]
# - Each family member, in a plain list and in a list of dicts.
FAMILY = [
    '#include "f"',
    '#sinclude "f"',
    '#includeIfPresent "f"',
    '#includeEtc "caseDicts/f"',
    "#includeFunc foo(a, b)",
]
for _dir in FAMILY:
    _kw = _dir.split()[0][1:]
    ROWS.append(
        (f"{_kw}-plain", f"x\n(\n    {_dir}\n    1\n    2\n);\n", _dir, "tokens")
    )
    ROWS.append(
        (f"{_kw}-dicts", f"x\n(\n    {_dir}\n    a {{ b 1; }}\n);\n", _dir, "dicts")
    )

CONTAINERS = ["top", "sub"]
PARAMS = []
TYPEERROR_IDS = set()  # - rows that raised TypeError on write before T-042
for _name, _text, _directive, _kind in ROWS:
    for _cont in CONTAINERS:
        _id = f"{_name}-{_cont}"
        PARAMS.append(
            pytest.param(_text if _cont == "top" else _sub(_text), _directive, id=_id)
        )
        if _kind == "dicts":
            TYPEERROR_IDS.add(_id)
ALL_IDS = {p.id for p in PARAMS}


def test_the_reproduction_table_is_covered():
    assert len(ALL_IDS) == 2 * len(ROWS)
    assert any(i.startswith("list-of-dicts") for i in TYPEERROR_IDS)
    assert len(TYPEERROR_IDS) == 2 * (1 + len(FAMILY))


@pytest.mark.parametrize(("text", "directive"), PARAMS)
def test_loads_and_models_the_directive_as_one_include_item(tmp_path, text, directive):
    path = tmp_path / "inList"
    path.write_text(HEADER + text)
    assert len(_in_lists(_load(path))) == 1


@pytest.mark.parametrize(("text", "directive"), PARAMS)
def test_written_text_has_the_directive_on_one_line_unchanged(
    tmp_path, text, directive
):
    text1 = _cycle(tmp_path, HEADER + text)[2]
    assert _lines(text1).count(_norm(directive)) == 1


@pytest.mark.parametrize(("text", "directive"), PARAMS)
def test_written_text_reads_back_to_the_same_entries(tmp_path, text, directive):
    first, second, _, _ = _cycle(tmp_path, HEADER + text)
    assert _shape(first) == _shape(second)
    assert len(_in_lists(second)) == len(_in_lists(first))


@pytest.mark.parametrize(("text", "directive"), PARAMS)
def test_second_write_equals_the_first(tmp_path, text, directive):
    _, _, text1, text2 = _cycle(tmp_path, HEADER + text)
    assert text1 == text2


# --- #includeFunc patchAverage(name=inlet, p): never lose the parentheses ---------------
ARGS_CASES = [
    pytest.param(f"functions ( {FUNC} );\n", id="one-line-top"),
    pytest.param(f"functions\n(\n    {FUNC}\n);\n", id="multi-line-top"),
    pytest.param(_sub(f"functions ( {FUNC} );\n"), id="one-line-sub"),
    pytest.param(_sub(f"functions\n(\n    {FUNC}\n);\n"), id="multi-line-sub"),
]


@pytest.mark.parametrize("text", ARGS_CASES)
def test_includefunc_arguments_in_a_list_round_trip_or_raise_with_file_and_line(
    tmp_path, text
):
    """Today the call is split into tokens and the parentheses are lost (silent)."""
    path = tmp_path / "args"
    path.write_text(HEADER + text)
    span = "|".join(str(HL + 1 + i) for i in range(text.count(NL)))
    try:
        written = _load(path).toString()
    except FoamKitError as err:
        msg = str(err)
        assert "args" in msg
        assert re.search(rf"\bline ({span})\b", msg, re.IGNORECASE), msg
        return
    assert FUNC in _lines(written)


# --- the real helmholtzResonance files -----------------------------------------------
HELM = [
    pytest.param(HELM_F14, id="foundation-14"),
    pytest.param(HELM_ESI, id="esi-v2606"),
]
HELM_INCLUDES = [
    '#include "blockMeshDict.caseBlocks"',
    '#include "blockMeshDict.caseBoundary"',
]


def test_esi_helmholtz_fixture_has_the_two_include_lines():
    data = HELM_ESI.read_bytes()
    lines = data.decode().split(NL)
    assert lines[149].strip() == HELM_INCLUDES[0]
    assert lines[192].strip() == HELM_INCLUDES[1]
    assert b"\r" not in data


@pytest.mark.parametrize("path", HELM)
def test_helmholtz_loads(path):
    d = _load(path)
    assert d.blocks is not None
    assert d.boundary is not None


@pytest.mark.parametrize("path", HELM)
def test_helmholtz_blocks_and_boundary_each_hold_one_include_item(path):
    assert len(_in_lists(_load(path))) == 2


@pytest.mark.parametrize("path", HELM)
def test_helmholtz_writes_the_two_include_lines_on_one_line_each(path):
    lines = _lines(_load(path).toString())
    for wanted in HELM_INCLUDES:
        assert lines.count(wanted) == 1


@pytest.mark.parametrize("path", HELM)
def test_helmholtz_written_text_reads_back_to_the_same_entries(tmp_path, path):
    first = _load(path)
    out = tmp_path / "wa"
    out.write_text(first.toString())
    assert _shape(_load(out)) == _shape(first)


@pytest.mark.parametrize("path", HELM)
def test_helmholtz_second_write_equals_the_first(tmp_path, path):
    first = _load(path)
    text1 = first.toString()
    out = tmp_path / "wa"
    out.write_text(text1)
    assert _load(out).toString() == text1


# --- guards that must keep passing -------------------------------------------------------
# - Dict-level output of the include family, today (including the blank line after it).
DICT_LEVEL = [
    ('#include "f"', '#include    "f"\n\n'),
    ('#sinclude "f"', '#sinclude   "f"\n\n'),
    ('#includeIfPresent "f"', '#includeIfPresent\t"f"\n\n'),
    ('#includeEtc "caseDicts/f"', '#includeEtc "caseDicts/f"\n\n'),
    ("#includeFunc foo(a, b)", "#includeFunc\tfoo(a, b)\n\n"),
]
AFTER_BANNER = "//\n\n"


@pytest.mark.parametrize(("directive", "written"), DICT_LEVEL)
def test_dict_level_include_output_is_unchanged_at_top_level(
    tmp_path, directive, written
):
    path = tmp_path / "dl"
    path.write_text(HEADER + directive + "\nx 1;\n")
    text = _load(path).toString().split(AFTER_BANNER, 1)[1]
    assert text == written + "\nx           1; \n\n"


@pytest.mark.parametrize(("directive", "written"), DICT_LEVEL)
def test_dict_level_include_output_is_unchanged_in_a_sub_dict(
    tmp_path, directive, written
):
    path = tmp_path / "dl"
    path.write_text(HEADER + "sub\n{\n" + directive + "\n    x 1;\n}\n")
    text = _load(path).toString().split(AFTER_BANNER, 1)[1]
    assert text == "sub\n{\n    " + written + "    x           1; \n}\n\n\n"


# - Other directives in a plain list keep today's token behaviour (out of scope).
TOKENS = [
    ('#calc "1+2"', ["#calc", '"1+2"']),
    ("0 #neg $a 1", ["0", "#neg", "$a", "1"]),
    ('#print "hi"', ["#print", '"hi"']),
    ("$a", ["$a"]),
]


@pytest.mark.parametrize(("item", "tokens"), TOKENS, ids=[t[0] for t in TOKENS])
@pytest.mark.parametrize("container", CONTAINERS)
def test_other_directives_in_a_plain_list_stay_separate_tokens(
    tmp_path, item, tokens, container
):
    text = f"x ( {item} );\n"
    if container == "sub":
        text = _sub(text)
    first, second, text1, text2 = _cycle(tmp_path, HEADER + text)
    body = _lines(text1.split(AFTER_BANNER, 1)[1])
    start = body.index("(") + 1
    assert body[start : start + len(tokens)] == tokens
    assert _shape(first) == _shape(second)
    assert text1 == text2
    assert not _in_lists(first)


def test_engine2valve_style_times_list_loads_and_keeps_the_path(tmp_path):
    path = tmp_path / "dynamicMeshDict"
    path.write_text(HEADER + 'times ( #include "$FOAM_CASE/constant/meshTimes" );\n')
    text = _load(path).toString()
    assert '"$FOAM_CASE/constant/meshTimes"' in text
