"""`#print`, `#remove`, `#if/#ifeq/#else/#endif`, `#inputMode`, `#calc`, unknown directives (T-016).

Specification tests for ticket docs/tickets/T-016-other-directives-round-trip.md.
Public names (approved 2026-10-19): `ofVerbatimDirective`, `OF_DIRECTIVES`,
`DirectiveInfo`, `iterDirectives`, all in `foamkit.types`.

Real files (byte-exact copies in tests/releases/, which is outside the
tests/fixtures/ tree that test_golden.py globs).  Shallow clones made 2026-10-21:
- Foundation 11-14: https://github.com/OpenFOAM/OpenFOAM-{11,12,13,14} (default
  branch, `tutorials/` only).
- ESI v2412, v2506, v2512, v2606: tags OpenFOAM-v2412 ... OpenFOAM-v2606 of
  https://gitlab.com/openfoam/core/openfoam (inventory by `git grep` on the tag).

foundation-14.pitzDaily.momentumTransport      (`#print` in RAS {})
  OpenFOAM-14: tutorials/incompressibleFluid/pitzDaily/constant/momentumTransport
foundation-14.cylinder.momentumTransport       (`#print` in RAS {} and LES {})
  OpenFOAM-14: tutorials/incompressibleFluid/cylinder/constant/momentumTransport
foundation-14.cylinder.fvSchemes               (`#ifeq`/`#else`/`#endif` in divSchemes {})
  OpenFOAM-14: tutorials/incompressibleFluid/cylinder/system/fvSchemes
foundation-14.cylinder.blockMeshDict           (`key #calc "..."`, `key #neg $x`)
  OpenFOAM-14: tutorials/incompressibleFluid/cylinder/system/blockMeshDict
foundation-14.aerofoilNACA0012Steady.U         (`#codeBlock`, `#codeInclude`, `#endCodeBlock`)
  OpenFOAM-14: tutorials/fluid/aerofoilNACA0012Steady/0/U
foundation-13.aerofoilNACA0012Steady.U         (`#calcInclude`, Foundation 11-13)
  OpenFOAM-13: tutorials/fluid/aerofoilNACA0012Steady/0/U
foundation-14.floatingBeam.blockMeshDict       (`vertices #codeStream {...};`)
  OpenFOAM-14: tutorials/incompressibleVoF/floatingBeam/system/blockMeshDict
foundation-14.trayedPipe.createZonesDict       (`#codeDict` followed by `{ ... }` on the next line)
  OpenFOAM-14: tutorials/incompressibleVoF/trayedPipe/system/createZonesDict
foundation-14.roomHeating.fvModels             (`#includeModel heatSource`, unquoted)
  OpenFOAM-14: tutorials/fluid/roomHeating/constant/fvModels
foundation-14.engine2Valve2D.fvConstraints     (`#includeConstraint limit...(min=1e4)`)
  OpenFOAM-14: tutorials/XiFluid/engine2Valve2D/system/fvConstraints
esi-v2606.bendJunction.blockMeshDict           (`#inputMode merge`)
  tutorials/mesh/moveDynamicMesh/bendJunction/system/blockMeshDict
esi-v2606.squareBend.blockMeshDict             (`#if 0 ... #endif` around `#eval` lines)
  tutorials/incompressible/simpleFoam/squareBend/system/blockMeshDict
esi-v2606.good-if1.dict                        (nested `#ifeq`/`#if`/`#else`/`#endif`)
esi-v2606.good-if3.dict                        (unbalanced `}` in a dead `#else` branch)
esi-v2606.good-word-expand.dict                (`#message`, `#word`)
  tutorials/IO/dictionary/good-{if1,if3,word-expand}.dict  (ESI parser tests, not solver tutorials)
esi-v2606.freePiston.U                         (`#remove (wall piston)`)
  tutorials/combustion/coldEngineFoam/freePiston/0/U
esi-v2606.potentialFoam-cylinder.blockMeshDict (`#remove ( "r(Inner|Outer).*" ... )`)
  tutorials/basic/potentialFoam/cylinder/system/blockMeshDict
esi-v2606.externalCoupled                      (`#sinclude` in a sub-dictionary; loads today)
  tutorials/compressible/rhoPimpleFoam/RAS/externalCoupledSquareBendLiq/system/externalCoupled

Several of these still fail for reasons outside T-016 (the `$!` scoped-key syntax,
a lost `/* */` block, one-line `vertices` entries ...).  Tests below therefore compare
the directive lines (and blocks) of a file, not the whole file, except for the four
files whose only blocker today is the directive (see WHOLE_FILE_CLEAN).

Unknown (unregistered) directives are synthetic: every `#word` found in the real
dictionaries is in the inventory (see INVENTORY).
"""

import re
import shutil

import pytest

import foamkit.functions as pf
import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import TESTS
from test_directives import HEADER, _directive_lines, _roundtrip

RELEASES = TESTS / "releases"

# --- inventory ----------------------------------------------------------------
# Keywords of every directive found in dictionary files (system/, constant/, 0/,
# IO/dictionary) of Foundation 11-14 and ESI v2412-v2606, including value
# position forms (`key #calc ...;`), which a line-start grep misses.
# `#CAD` (a data-table comment in expData/pInlet, not a dictionary) is excluded.
# The registry must have a row for EVERY one of these (ticket T-016, narrowed).
INVENTORY = [
    "include",
    "includeEtc",
    "includeFunc",
    "includeIfPresent",
    "sinclude",
    "includeModel",
    "includeConstraint",
    "calc",
    "neg",
    "eval",
    "codeStream",
    "print",
    "remove",
    "if",
    "ifeq",
    "else",
    "endif",
    "inputMode",
    "calcInclude",
    "codeBlock",
    "endCodeBlock",
    "codeInclude",
    "codeDict",
    "message",
    "word",
]
# - Block terminators: registry rows, but never a directive on their own.
SNIPPET_EXEMPT = {"else", "endif"}

# - Directives owned by later tickets.  T-016 only requires their registry row,
# - with status "unsupported" and the ticket named in `note`.  The behaviour tests
# - for them are strict xfails that flip loudly when the owning ticket lands.
DEFERRED = {
    "calc": "T-027",
    "neg": "T-027",
    "if": "T-026",
    "ifeq": "T-026",
    "else": "T-026",
    "endif": "T-026",
    "codeDict": "T-028",
    "word": "T-028",
    "includeModel": "T-029",
    "includeConstraint": "T-029",
}


def _xf(ticket, why):
    return pytest.mark.xfail(strict=True, reason=f"{ticket}: {why}")


XF_T026 = _xf("T-026", "conditional #if/#ifeq/#else/#endif blocks")
XF_T027 = _xf("T-027", "value-position #calc/#neg, ofCalc TypeError")
XF_T028 = _xf("T-028", "#codeDict/#word with { on the next line")
XF_T029 = _xf("T-029", "#includeModel/#includeConstraint quoting and arguments")
XF_T033 = _xf("T-033", "#codeStream writer instability")
XF_T031 = _xf("T-031", "block comments")
_XF_BY_TICKET = {
    "T-026": XF_T026,
    "T-027": XF_T027,
    "T-028": XF_T028,
    "T-029": XF_T029,
    "T-031": XF_T031,
}


def _text(name):
    return (RELEASES / name).read_bytes().replace(b"\r\n", b"\n").decode()


def _lines(name, first, last, expect):
    """Lines `first..last` (1-based, inclusive) of a release file; guards the first line."""
    lines = _text(name).split("\n")[first - 1 : last]
    assert lines[0].strip().startswith(expect), (name, first, lines[0])
    return "\n".join(lines)


# - Real source text per keyword.  All text is sliced from the byte-exact copies.
# - `codeBlock` and `endCodeBlock` are the marker lines only: the entries between
# - them in the real file use value-position `#calc` (T-027) and are tested apart.
SNIPPETS = {
    "include": '#include        "include/initialConditions"',
    "includeEtc": '#includeEtc "caseDicts/setConstraintTypes"',
    "includeFunc": "#includeFunc patchAverage",
    "includeIfPresent": '#includeIfPresent "regionSolvers"',
    "sinclude": '#sinclude "<constant>/dynamicMeshDict"',
    "includeModel": "#includeModel clouds(name=fvModel)",
    "includeConstraint": "#includeConstraint limitTemperature(phase=water, min=270, max=2000)",
    "calc": _lines("foundation-14.cylinder.blockMeshDict", 27, 27, "cylRadius"),
    "neg": _lines("foundation-14.cylinder.blockMeshDict", 29, 29, "cylMin"),
    "eval": _lines("esi-v2606.squareBend.blockMeshDict", 42, 42, "zmin"),
    "codeStream": _lines(
        "foundation-14.floatingBeam.blockMeshDict", 21, 40, "vertices #codeStream"
    ),
    "print": "#print",
    "remove": _lines("esi-v2606.freePiston.U", 51, 51, "#remove"),
    "if": _lines("esi-v2606.squareBend.blockMeshDict", 32, 40, "#if 0"),
    "ifeq": _lines("foundation-14.cylinder.fvSchemes", 39, 45, "#ifeq"),
    "inputMode": _lines("esi-v2606.bendJunction.blockMeshDict", 46, 46, "#inputMode"),
    "calcInclude": '#calcInclude    "transform.H"',
    "codeBlock": _lines("foundation-14.aerofoilNACA0012Steady.U", 20, 21, "#codeBlock"),
    "endCodeBlock": _lines(
        "foundation-14.aerofoilNACA0012Steady.U", 26, 26, "#endCodeBlock"
    ),
    "codeInclude": '#codeInclude    "transform.H"',
    "codeDict": _lines("foundation-14.trayedPipe.createZonesDict", 24, 46, "#codeDict"),
    "message": _lines("esi-v2606.good-word-expand.dict", 21, 21, "#message"),
    "word": _lines("esi-v2606.good-word-expand.dict", 34, 37, "#word"),
}

# - Single-line verbatim directives owned by T-016 (narrowed ticket table).
VERBATIM_LINE = {
    "print": "#print",
    "remove": "#remove (wall piston)",
    "inputMode": "#inputMode merge",
    "calcInclude": '#calcInclude    "transform.H"',
    "codeBlock": "#codeBlock",
    "endCodeBlock": "#endCodeBlock",
    "codeInclude": '#codeInclude    "transform.H"',
    "message": "#message message-word",
}
INTERPRETED = ["include", "includeEtc", "includeFunc"]

REGISTRY = getattr(fkt, "OF_DIRECTIVES", None)
# - Parametrize over the registry once it exists; until then over the inventory,
# - so the tests fail for the missing registry rather than vanish.
KEYWORDS = sorted((set(INVENTORY) | set(REGISTRY or ())) - SNIPPET_EXEMPT)

# - `#codeStream` is interpreted (ofCodeStream) but its writer is unstable (T-033):
# - it is out of the byte-level round-trip tests here and has strict xfails below.
ROUNDTRIP_KEYWORDS = [k for k in KEYWORDS if k != "codeStream"]


def _kw_params(keywords, passing_today=()):
    """Parametrize over keywords; those owned by later tickets get a strict xfail
    unless the behaviour already holds today (`passing_today`)."""
    out = []
    for kw in keywords:
        ticket = DEFERRED.get(kw)
        if ticket and kw not in passing_today:
            out.append(pytest.param(kw, id=kw, marks=_XF_BY_TICKET[ticket]))
        else:
            out.append(pytest.param(kw, id=kw))
    return out


def _file_params(names, deferred):
    """Parametrize over real-file names; `deferred` maps name -> ticket."""
    return [
        pytest.param(n, id=n, marks=_XF_BY_TICKET[deferred[n]])
        if n in deferred
        else pytest.param(n, id=n)
        for n in names
    ]


# - Real files whose only blocker today is a directive: the whole file must
# - survive modulo whitespace and blank lines.
WHOLE_FILE_CLEAN = _file_params(
    [
        "foundation-14.pitzDaily.momentumTransport",
        "foundation-14.cylinder.momentumTransport",
        "foundation-14.cylinder.fvSchemes",
        "esi-v2606.good-if1.dict",
        "esi-v2606.good-if3.dict",
    ],
    {
        "foundation-14.cylinder.fvSchemes": "T-026",
        "esi-v2606.good-if1.dict": "T-026",
        "esi-v2606.good-if3.dict": "T-026",
    },
)


# --- helpers ------------------------------------------------------------------


def _write(tmp_path, body, name="dict"):
    path = tmp_path / name
    path.write_text(HEADER + body)
    return path


def _read(tmp_path, body, name="dict"):
    return fkt.DictFileParser(_write(tmp_path, body, name)).readDictFile()


def _indent(text, n=4):
    return "\n".join((" " * n + ln) if ln else ln for ln in text.split("\n"))


def _top(snippet):
    return f"{snippet}\n\nx 1;\n"


def _sub(snippet):
    return f"sub\n{{\n    a 1;\n\n{_indent(snippet)}\n\n    b 2;\n}}\n\nx 1;\n"


WRAPPERS = pytest.mark.parametrize(
    "wrap", [_top, _sub], ids=["top-level", "in-subdict"]
)


def _norm(text):
    """Whitespace-normalised, non-blank lines."""
    return [" ".join(ln.split()) for ln in text.splitlines() if ln.strip()]


def _directive_text(text):
    """The lines of `text` that start with `#`."""
    return chr(10).join(ln for ln in text.splitlines() if ln.lstrip().startswith("#"))


def _contains_run(haystack, needle):
    n = len(needle)
    return any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


def _walk(obj, _seen=None):
    """Yield every non-private attribute value below `obj`, depth first."""
    seen = set() if _seen is None else _seen
    if id(obj) in seen:
        return
    seen.add(id(obj))
    for key, val in list(vars(obj).items()):
        if key.startswith("_"):
            continue
        yield val
        if type(val).__module__.startswith("foamkit"):
            yield from _walk(val, seen)


def _verbatims(obj):
    return [v for v in _walk(obj) if isinstance(v, fkt.ofVerbatimDirective)]


def _warnings(capsys, caplog, name):
    """Count WARNING messages that mention `name`, from userMsg output and the logger."""
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if "WARNING" in ln and name in ln]
    lines += [
        r.getMessage()
        for r in caplog.records
        if r.levelname == "WARNING" and name in r.getMessage()
    ]
    return lines


# === registry ==================================================================


def test_registry_is_a_dict_of_directive_info():
    assert isinstance(fkt.OF_DIRECTIVES, dict)
    assert fkt.OF_DIRECTIVES
    assert all(isinstance(v, fkt.DirectiveInfo) for v in fkt.OF_DIRECTIVES.values())


def test_registry_keys_are_keywords_without_hash():
    assert all(
        isinstance(k, str) and re.fullmatch(r"[A-Za-z]\w*", k)
        for k in fkt.OF_DIRECTIVES
    )


def test_directive_info_has_status_distributions_and_note():
    info = next(iter(fkt.OF_DIRECTIVES.values()))
    assert {"status", "distributions", "note"} <= set(dir(info))


def test_registry_status_values_are_from_the_allowed_set():
    assert {i.status for i in fkt.OF_DIRECTIVES.values()} <= {
        "interpreted",
        "verbatim",
        "unsupported",
    }


def test_registry_distributions_are_non_empty_strings():
    for kw, info in fkt.OF_DIRECTIVES.items():
        assert info.distributions, kw
        assert all(isinstance(d, str) and d for d in info.distributions), kw


@pytest.mark.parametrize("keyword", INVENTORY)
def test_registry_lists_inventoried_directive(keyword):
    assert keyword in fkt.OF_DIRECTIVES


def test_registry_contains_exactly_the_inventory():
    """Ticket: a row for every inventoried directive, and no others."""
    extra = set(fkt.OF_DIRECTIVES) - set(INVENTORY)
    assert not extra, f"registry rows without an inventory entry: {sorted(extra)}"


@pytest.mark.parametrize("keyword", INTERPRETED)
def test_include_family_is_registered_as_interpreted(keyword):
    assert fkt.OF_DIRECTIVES[keyword].status == "interpreted"


@pytest.mark.parametrize("keyword", sorted(VERBATIM_LINE))
def test_preserved_directive_is_registered_as_verbatim(keyword):
    assert fkt.OF_DIRECTIVES[keyword].status == "verbatim"


@pytest.mark.parametrize("keyword", sorted(DEFERRED))
def test_deferred_directive_is_unsupported_and_names_its_ticket(keyword):
    """Directives owned by T-026..T-029 are "unsupported" with the ticket in `note`."""
    info = fkt.OF_DIRECTIVES[keyword]
    assert info.status == "unsupported"
    assert DEFERRED[keyword] in info.note


def test_print_is_not_attributed_to_esi():
    """Real files: `#print` appears only in Foundation 14 tutorials (not 11-13, not ESI)."""
    dists = fkt.OF_DIRECTIVES["print"].distributions
    assert not any(d.lower().startswith("esi") for d in dists)
    assert any(d.lower().startswith("foundation") for d in dists)


def test_eval_is_not_attributed_to_foundation():
    """Real files: `#eval` appears in ESI tutorials only."""
    dists = fkt.OF_DIRECTIVES["eval"].distributions
    assert not any(d.lower().startswith("foundation") for d in dists)


def test_existing_registries_are_untouched():
    assert "include" in fkt.OF_FUNCTION_ENTRIES
    assert "codeExecute" in fkt.OF_VERBATIM_CODE_ENTRIES


# === every inventoried directive round-trips ==================================


@pytest.mark.parametrize("keyword", KEYWORDS)
def test_inventoried_directive_has_a_test_snippet(keyword):
    """Every registry row needs real source text here (keeps registry == inventory)."""
    assert keyword in SNIPPETS


@WRAPPERS
@pytest.mark.parametrize("keyword", _kw_params(ROUNDTRIP_KEYWORDS))
def test_directive_round_trips(tmp_path, wrap, keyword):
    if keyword not in SNIPPETS:
        pytest.skip("no snippet; see test_inventoried_directive_has_a_test_snippet")
    snippet = SNIPPETS[keyword]
    first, _, text = _roundtrip(tmp_path, wrap(snippet))
    assert _contains_run(_norm(text), _norm(snippet)), text


@WRAPPERS
@pytest.mark.parametrize(
    "keyword", _kw_params(ROUNDTRIP_KEYWORDS, passing_today={"includeModel"})
)
def test_directive_second_write_is_stable(tmp_path, wrap, keyword):
    if keyword not in SNIPPETS:
        pytest.skip("no snippet; see test_inventoried_directive_has_a_test_snippet")
    _, second, text = _roundtrip(tmp_path, wrap(SNIPPETS[keyword]))
    assert second.toString() == text


@pytest.mark.parametrize(
    "keyword", _kw_params(KEYWORDS, passing_today={"includeModel"})
)
def test_entries_after_directive_still_parse(tmp_path, keyword):
    if keyword not in SNIPPETS:
        pytest.skip("no snippet; see test_inventoried_directive_has_a_test_snippet")
    first, _, _ = _roundtrip(tmp_path, _top(SNIPPETS[keyword]))
    assert first.x.value == 1


@pytest.mark.parametrize(
    "keyword", _kw_params(KEYWORDS, passing_today={"includeModel"})
)
def test_entries_after_directive_in_subdict_still_parse(tmp_path, keyword):
    if keyword not in SNIPPETS:
        pytest.skip("no snippet; see test_inventoried_directive_has_a_test_snippet")
    first, _, _ = _roundtrip(tmp_path, _sub(SNIPPETS[keyword]))
    assert first.sub.a.value == 1
    assert first.sub.b.value == 2
    assert first.x.value == 1


@XF_T033
@WRAPPERS
def test_real_codeStream_round_trips(tmp_path, wrap):
    snippet = SNIPPETS["codeStream"]
    _, _, text = _roundtrip(tmp_path, wrap(snippet))
    assert _contains_run(_norm(text), _norm(snippet))


@XF_T033
@WRAPPERS
def test_real_codeStream_second_write_is_stable(tmp_path, wrap):
    _, second, text = _roundtrip(tmp_path, wrap(SNIPPETS["codeStream"]))
    assert second.toString() == text


CODE_BLOCK = _lines("foundation-14.aerofoilNACA0012Steady.U", 20, 26, "#codeBlock")


@XF_T027
def test_real_codeBlock_with_its_calc_entries_round_trips(tmp_path):
    """The whole real block: the markers are T-016, the `#calc` entries between are T-027."""
    _, second, text = _roundtrip(tmp_path, _top(CODE_BLOCK))
    assert _contains_run(_norm(text), _norm(CODE_BLOCK))
    assert second.toString() == text


# === verbatim type ==============================================================


@pytest.mark.parametrize("keyword", sorted(VERBATIM_LINE))
def test_line_directive_parses_to_verbatim_type(tmp_path, keyword):
    first, _, _ = _roundtrip(tmp_path, _top(VERBATIM_LINE[keyword]))
    found = _verbatims(first)
    assert [type(v) for v in found] == [fkt.ofVerbatimDirective]
    assert found[0].keyword == keyword


@pytest.mark.parametrize("keyword", sorted(VERBATIM_LINE))
def test_line_directive_keeps_raw_text(tmp_path, keyword):
    first, _, _ = _roundtrip(tmp_path, _top(VERBATIM_LINE[keyword]))
    (d,) = _verbatims(first)
    assert d.text.strip() == VERBATIM_LINE[keyword]
    assert d.toString().strip() == VERBATIM_LINE[keyword]


@pytest.mark.parametrize("keyword", sorted(VERBATIM_LINE))
def test_registered_directive_is_known(tmp_path, keyword):
    first, _, _ = _roundtrip(tmp_path, _top(VERBATIM_LINE[keyword]))
    (d,) = _verbatims(first)
    assert d.known is True


def test_verbatim_directive_is_constructible_and_str_round_trips():
    d = fkt.ofVerbatimDirective(keyword="print", text="#print")
    assert d.keyword == "print"
    assert d.text == "#print"
    assert d.toString() == "#print"
    assert d.known is True


def test_verbatim_directive_with_unregistered_keyword_is_not_known():
    assert (
        fkt.ofVerbatimDirective(keyword="frobnicate", text="#frobnicate x").known
        is False
    )


def test_verbatim_directive_toString_keeps_unusual_spacing():
    raw = "#remove    (  a    b )"
    assert fkt.ofVerbatimDirective(keyword="remove", text=raw).toString() == raw


@pytest.mark.parametrize(
    "line",
    [
        "#remove (wall piston)",
        '#remove ( "r(Inner|Outer).*"  "[xy](min|max)" )',
        "#remove x",
    ],
)
def test_remove_forms_round_trip_on_one_line(tmp_path, line):
    _, second, text = _roundtrip(tmp_path, _top(line))
    assert line in [ln.strip() for ln in text.splitlines()]
    assert second.toString() == text


def test_real_potentialFoam_remove_line_is_preserved(tmp_path):
    line = _lines("esi-v2606.potentialFoam-cylinder.blockMeshDict", 87, 87, "#remove")
    _, _, text = _roundtrip(tmp_path, _top(line))
    assert line in text


# === #print in the real Foundation 14 files =====================================


PITZ_MT = "foundation-14.pitzDaily.momentumTransport"


def test_real_pitzDaily_momentumTransport_fixture_is_byte_exact():
    """The fixture is the file fetched from OpenFOAM-14 (777 bytes, LF, `#print` at line 25)."""
    raw = (RELEASES / PITZ_MT).read_bytes().replace(b"\r\n", b"\n")
    assert len(raw) == 777
    assert raw.split(b"\n")[24] == b"    #print"


def test_real_pitzDaily_momentumTransport_loads():
    d = fkt.DictFileParser(RELEASES / PITZ_MT).readDictFile()
    assert d.simulationType.value == "RAS"
    assert d.RAS.model.value == "kEpsilon"
    assert d.RAS.turbulence.value is True or d.RAS.turbulence.value == "on"


def test_real_pitzDaily_momentumTransport_print_is_inside_RAS():
    d = fkt.DictFileParser(RELEASES / PITZ_MT).readDictFile()
    assert [v.keyword for v in _verbatims(d.RAS)] == ["print"]
    assert _verbatims(d) == _verbatims(d.RAS)


def test_real_pitzDaily_momentumTransport_writes_print_back_unchanged():
    d = fkt.DictFileParser(RELEASES / PITZ_MT).readDictFile()
    out = d.toString()
    ras = out.split("RAS", 1)[1]
    assert "    #print\n" in ras
    assert [ln.strip() for ln in out.splitlines() if ln.lstrip().startswith("#")] == [
        "#print"
    ]


def test_real_pitzDaily_momentumTransport_second_write_is_stable(tmp_path):
    d = fkt.DictFileParser(RELEASES / PITZ_MT).readDictFile()
    text = d.toString()
    out = tmp_path / "momentumTransport"
    out.write_text(text)
    assert fkt.DictFileParser(out).readDictFile().toString() == text


def test_real_cylinder_momentumTransport_has_two_prints_in_two_subdicts():
    d = fkt.DictFileParser(
        RELEASES / "foundation-14.cylinder.momentumTransport"
    ).readDictFile()
    assert [v.keyword for v in _verbatims(d.RAS)] == ["print"]
    assert [v.keyword for v in _verbatims(d.LES)] == ["print"]


@pytest.mark.parametrize("name", WHOLE_FILE_CLEAN)
def test_real_file_round_trips_modulo_whitespace(name):
    d = fkt.DictFileParser(RELEASES / name).readDictFile()
    assert _norm(d.toString()) == _norm(_text(name))


# === #calc =====================================================================


@pytest.mark.parametrize(
    "line",
    [
        '#calc "1+2"',
        '#calc "$a * 2"',
        "#calc #{ 1 + 2 #}",
    ],
    ids=["string", "string-with-variable", "inline-code-block"],
)
@XF_T027
def test_toplevel_calc_parses_without_type_error(tmp_path, line):
    first, _, _ = _roundtrip(tmp_path, _top(line))
    assert first.x.value == 1


@pytest.mark.parametrize(
    "line",
    ['#calc "1+2"', "#calc #{ 1 + 2 #}"],
    ids=["string", "inline-code-block"],
)
@XF_T027
def test_toplevel_calc_round_trips(tmp_path, line):
    _, second, text = _roundtrip(tmp_path, _top(line))
    assert _contains_run(_norm(text), _norm(line))
    assert second.toString() == text


@XF_T027
def test_toplevel_multiline_calc_code_block_round_trips(tmp_path):
    block = "#calc #{\n    const scalar a = 1;\n    return a + 2;\n#}"
    first, _, text = _roundtrip(tmp_path, _top(block))
    assert _contains_run(_norm(text), _norm(block))
    assert first.x.value == 1


@pytest.mark.parametrize(
    "line",
    [
        _lines("foundation-14.cylinder.blockMeshDict", 27, 27, "cylRadius"),
        _lines("foundation-14.aerofoilNACA0012Steady.U", 22, 22, "liftDir"),
        _lines("foundation-14.aerofoilNACA0012Steady.U", 25, 25, "Uinlet"),
    ],
)
@XF_T027
def test_real_value_position_calc_round_trips(tmp_path, line):
    """The form tutorials use: `key #calc "...";` (321 uses across the tested releases)."""
    first, second, text = _roundtrip(tmp_path, _top(line))
    assert _contains_run(_norm(text), _norm(line))
    assert second.toString() == text


@XF_T027
def test_real_value_position_neg_round_trips(tmp_path):
    line = SNIPPETS["neg"]
    _, second, text = _roundtrip(tmp_path, _top(line))
    assert _contains_run(_norm(text), _norm(line))
    assert second.toString() == text


@XF_T027
def test_real_cylinder_blockMeshDict_calc_and_neg_lines_survive(tmp_path):
    """Directive lines of a real file (the whole file may fail for other reasons)."""
    name = "foundation-14.cylinder.blockMeshDict"
    wanted = [
        ln for ln in _text(name).splitlines() if re.match(r"\w+\s+#(calc|neg)\b", ln)
    ]
    assert len(wanted) > 10
    body = "\n".join(wanted) + "\n\nx 1;\n"
    first, _, text = _roundtrip(tmp_path, body)
    assert all(_contains_run(_norm(text), _norm(ln)) for ln in wanted)
    assert first.x.value == 1


# === #if / #ifeq / #else / #endif ===============================================


def _block_lines(name, first, last):
    return _text(name).split("\n")[first - 1 : last]


@XF_T026
def test_real_squareBend_if_block_is_one_verbatim_directive(tmp_path):
    first, _, _ = _roundtrip(tmp_path, _top(SNIPPETS["if"]))
    (d,) = _verbatims(first)
    assert d.keyword == "if"
    assert d.text.strip() == SNIPPETS["if"]


@XF_T026
def test_real_squareBend_if_block_is_written_back_in_full(tmp_path):
    _, _, text = _roundtrip(tmp_path, _top(SNIPPETS["if"]))
    assert _contains_run(
        [ln.rstrip() for ln in text.splitlines()], SNIPPETS["if"].split("\n")
    )


@XF_T026
def test_entries_inside_if_block_are_not_editable_attributes(tmp_path):
    """Ticket: entries inside `#if` blocks are part of the verbatim text."""
    first, _, _ = _roundtrip(tmp_path, _top(SNIPPETS["if"]))
    assert "nxin" not in vars(first)
    assert "nxout" not in vars(first)


@XF_T026
def test_real_squareBend_file_keeps_if_block_and_following_eval(tmp_path):
    name = "esi-v2606.squareBend.blockMeshDict"
    d = fkt.DictFileParser(RELEASES / name).readDictFile()
    out = d.toString()
    assert _contains_run(
        [ln.rstrip() for ln in out.splitlines()], SNIPPETS["if"].split("\n")
    )
    assert "zmin" in out and "#eval" in out
    assert d.nxin.value == 20


@XF_T026
def test_real_fvSchemes_ifeq_blocks_are_captured_in_divSchemes():
    d = fkt.DictFileParser(RELEASES / "foundation-14.cylinder.fvSchemes").readDictFile()
    found = _verbatims(d.divSchemes)
    assert [v.keyword for v in found] == ["ifeq", "ifeq"]
    assert found[0].text.strip() == SNIPPETS["ifeq"]
    assert found[0].text.strip().endswith("#endif")
    assert "#else" in found[0].text


@XF_T026
def test_real_fvSchemes_ifeq_blocks_are_written_back_in_full():
    name = "foundation-14.cylinder.fvSchemes"
    out = fkt.DictFileParser(RELEASES / name).readDictFile().toString()
    out_lines = [ln.rstrip() for ln in out.splitlines()]
    assert _contains_run(out_lines, _block_lines(name, 39, 45))
    assert _contains_run(out_lines, _block_lines(name, 60, 64))


@XF_T026
def test_real_fvSchemes_entries_around_the_ifeq_block_stay_editable():
    d = fkt.DictFileParser(RELEASES / "foundation-14.cylinder.fvSchemes").readDictFile()
    assert d.divSchemes.default.value == "none"
    assert d.laplacianSchemes.default is not None


@XF_T026
def test_real_fvSchemes_ifeq_branch_entries_are_not_attributes():
    d = fkt.DictFileParser(RELEASES / "foundation-14.cylinder.fvSchemes").readDictFile()
    assert "turbulence" not in vars(d.divSchemes)


@XF_T026
def test_nested_conditional_is_captured_to_the_matching_endif():
    """good-if1.dict: `#ifeq` ... `#if` ... `#else` ... `#endif` ... `#else` ... `#endif`.
    The ticket says "up to `#endif`"; the real file needs nesting-aware matching."""
    d = fkt.DictFileParser(RELEASES / "esi-v2606.good-if1.dict").readDictFile()
    found = _verbatims(d)
    assert [v.keyword for v in found] == ["ifeq"]
    assert found[0].text.count("#endif") == 2
    assert found[0].text.strip().endswith("#endif")
    assert 'version "other";' in found[0].text


@XF_T026
def test_nested_conditional_round_trips_in_full():
    name = "esi-v2606.good-if1.dict"
    out = fkt.DictFileParser(RELEASES / name).readDictFile().toString()
    start = next(
        i for i, ln in enumerate(_text(name).split("\n")) if ln.startswith("#ifeq")
    )
    block = _text(name).split("\n")[start : start + 13]
    assert _contains_run([ln.rstrip() for ln in out.splitlines()], block)


@XF_T026
def test_unbalanced_brace_in_dead_branch_does_not_end_the_capture():
    """good-if3.dict: `scalarEqLabel false; }` in a dead `#else` branch is text, not syntax."""
    d = fkt.DictFileParser(RELEASES / "esi-v2606.good-if3.dict").readDictFile()
    found = _verbatims(d)
    assert [v.keyword for v in found] == ["ifeq", "ifeq"]
    assert all(v.text.strip().endswith("#endif") for v in found)


@pytest.mark.parametrize("name", ["esi-v2606.good-if1.dict", "esi-v2606.good-if3.dict"])
@XF_T026
def test_conditional_dict_second_write_is_stable(tmp_path, name):
    text = fkt.DictFileParser(RELEASES / name).readDictFile().toString()
    out = tmp_path / "again"
    out.write_text(text)
    assert fkt.DictFileParser(out).readDictFile().toString() == text


@XF_T026
def test_ifeq_in_subdict_is_captured_to_its_endif(tmp_path):
    body = (
        "sub\n{\n    a 1;\n#ifeq $mode graded\n    b 2;\n#else\n    b 3;\n#endif\n"
        "    c 4;\n}\n\nx 1;\n"
    )
    first, _, text = _roundtrip(tmp_path, body)
    assert [v.keyword for v in _verbatims(first.sub)] == ["ifeq"]
    assert first.sub.c.value == 4
    assert first.x.value == 1
    assert _contains_run(
        [ln.rstrip() for ln in text.splitlines()],
        ["#ifeq $mode graded", "    b 2;", "#else", "    b 3;", "#endif"],
    )


@XF_T026
def test_if_without_endif_raises_foamkit_error_with_file_and_line(tmp_path):
    """Unterminated conditional: never consume to end of file silently."""
    path = _write(tmp_path, "a 1;\n#if 0\nb 2;\nc 3;\n", "badIf")
    with pytest.raises(FoamKitError) as err:
        fkt.DictFileParser(path).readDictFile()
    assert "badIf" in str(err.value)
    # the opening `#if 0` is on the second body line
    assert str(HEADER.count("\n") + 2) in str(err.value)


@XF_T026
@pytest.mark.parametrize("line", ["#else", "#endif"])
def test_stray_else_or_endif_raises_foamkit_error_with_file_and_line(tmp_path, line):
    path = _write(tmp_path, f"a 1;\n{line}\nb 2;\n", "strayBlockEnd")
    with pytest.raises(FoamKitError) as err:
        fkt.DictFileParser(path).readDictFile()
    assert "strayBlockEnd" in str(err.value)
    assert str(HEADER.count("\n") + 2) in str(err.value)


# === #includeEtc / #includeFunc inside sub-dictionaries ======================


SUB_INCLUDES = (
    "boundaryField\n{\n    freestream\n    {\n        type            zeroGradient;\n"
    '        #includeEtc "caseDicts/setConstraintTypes"\n'
    "        #includeFunc patchAverage(patch=inlet, fields=(p U))\n"
    "        value           uniform 0;\n    }\n\n"
    "    wall\n    {\n        type            noSlip;\n    }\n\n"
    '    #includeEtc "caseDicts/setConstraintTypes"\n}\n'
)


def test_includeEtc_in_nested_subdict_keeps_keyword_and_value(tmp_path):
    first, _, text = _roundtrip(tmp_path, SUB_INCLUDES)
    inc = [
        v for v in _walk(first.boundaryField.freestream) if isinstance(v, fkt.ofInclude)
    ]
    assert [type(v) for v in inc] == [fkt.ofIncludeEtc, fkt.ofIncludeFunc]
    assert inc[0].value == "caseDicts/setConstraintTypes"
    assert inc[1].value == "patchAverage(patch=inlet, fields=(p U))"
    assert "#includeEtc" in text


def test_includeEtc_directly_in_boundaryField_keeps_keyword_and_value(tmp_path):
    first, _, _ = _roundtrip(tmp_path, SUB_INCLUDES)
    inc = [
        v for v in vars(first.boundaryField).values() if isinstance(v, fkt.ofIncludeEtc)
    ]
    assert [v.value for v in inc] == ["caseDicts/setConstraintTypes"]


def test_includes_in_subdict_are_written_with_their_keywords(tmp_path):
    _, second, text = _roundtrip(tmp_path, SUB_INCLUDES)
    assert _directive_lines(text) == [
        '#includeEtc "caseDicts/setConstraintTypes"',
        "#includeFunc patchAverage(patch=inlet, fields=(p U))",
        '#includeEtc "caseDicts/setConstraintTypes"',
    ]
    assert second.toString() == text


def test_real_externalCoupled_sinclude_in_subdict_survives():
    """Loads today: `#sinclude` inside a sub-dictionary (ESI v2606)."""
    name = "esi-v2606.externalCoupled"
    d = fkt.DictFileParser(RELEASES / name).readDictFile()
    wanted = _norm(_directive_text(_text(name)))
    got = _norm(_directive_text(d.toString()))
    assert wanted == got


@pytest.mark.parametrize(
    "line, written",
    [
        ("#includeModel heatSource", "#includeModel heatSource"),
        ("#includeModel clouds(name=fvModel)", "#includeModel clouds(name=fvModel)"),
        (
            "#includeConstraint limitLowPressure(min=1e4)",
            "#includeConstraint limitLowPressure(min=1e4)",
        ),
        (
            "#includeConstraint limitTemperature(phase=u, min=290, max=3000)",
            "#includeConstraint limitTemperature(phase=u, min=290, max=3000)",
        ),
    ],
)
@XF_T029
def test_foundation_includeModel_and_includeConstraint_are_written_as_read(
    tmp_path, line, written
):
    """Inventory directives (Foundation 11-14).  Today they are written quoted
    (`#includeModel "heatSource"`) and the `(...)` argument form fails to load.
    Whether this belongs to T-016 or to a T-015 follow-up is not stated in the ticket."""
    _, second, text = _roundtrip(tmp_path, _top(line))
    assert _directive_lines(text) == [written]
    assert second.toString() == text


# === unknown directives =========================================================


UNKNOWN = [
    "#frobnicate",
    "#frobnicate 1 2 3",
    "#frobnicate   spaced    out   ",
    '#frobnicate "a string"',
    "#frobnicate (a b)",
    "#frobnicate $var;",
]


@WRAPPERS
@pytest.mark.parametrize("line", UNKNOWN)
def test_unknown_directive_parses_to_unknown_verbatim(tmp_path, wrap, line):
    first, _, _ = _roundtrip(tmp_path, wrap(line))
    (d,) = _verbatims(first)
    assert type(d) is fkt.ofVerbatimDirective
    assert d.keyword == "frobnicate"
    assert d.known is False
    assert d.text.strip() == line.strip()


@WRAPPERS
@pytest.mark.parametrize("line", UNKNOWN)
def test_unknown_directive_is_written_back_byte_for_byte(tmp_path, wrap, line):
    _, second, text = _roundtrip(tmp_path, wrap(line))
    assert line in text.split("\n") or _indent(line) in text.split("\n")
    assert second.toString() == text


def test_unknown_directive_does_not_stop_following_entries(tmp_path):
    first, _, _ = _roundtrip(tmp_path, "a 1;\n#frobnicate x y\nb 2;\nc 3;\n")
    assert (first.a.value, first.b.value, first.c.value) == (1, 2, 3)


def test_unknown_directive_in_subdict_does_not_stop_following_entries(tmp_path):
    first, _, _ = _roundtrip(tmp_path, _sub("#frobnicate x y"))
    assert (first.sub.a.value, first.sub.b.value, first.x.value) == (1, 2, 1)


def test_unknown_directive_text_is_exact_for_odd_spacing(tmp_path):
    line = "#frobnicate\t  tab   and   spaces"
    first, _, text = _roundtrip(tmp_path, f"{line}\n\nx 1;\n")
    (d,) = _verbatims(first)
    assert d.text.strip() == line
    assert line in text


# --- the warning ----------------------------------------------------------------


def test_unknown_directive_logs_a_warning_naming_it(tmp_path, capsys, caplog):
    _read(tmp_path, "#frobnicate x\n\ny 1;\n")
    assert len(_warnings(capsys, caplog, "frobnicate")) == 1


def test_unknown_directive_warns_once_per_name_per_file(tmp_path, capsys, caplog):
    _read(tmp_path, "#frobnicate a\n\n#frobnicate b\n\nsub\n{\n    #frobnicate c\n}\n")
    assert len(_warnings(capsys, caplog, "frobnicate")) == 1


def test_two_unknown_names_warn_once_each(tmp_path, capsys, caplog):
    _read(tmp_path, "#frobnicate a\n\n#gizmo b\n\n#frobnicate c\n\n#gizmo d\n")
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if "WARNING" in ln]
    assert sum("frobnicate" in ln for ln in lines) == 1
    assert sum("gizmo" in ln for ln in lines) == 1


def test_same_unknown_name_in_two_files_warns_once_per_file(tmp_path, capsys, caplog):
    _read(tmp_path, "#frobnicate a\n", "one")
    _read(tmp_path, "#frobnicate a\n", "two")
    assert len(_warnings(capsys, caplog, "frobnicate")) == 2


def test_reading_the_same_file_twice_warns_each_time(tmp_path, capsys, caplog):
    path = _write(tmp_path, "#frobnicate a\n")
    fkt.DictFileParser(path).readDictFile()
    fkt.DictFileParser(path).readDictFile()
    assert len(_warnings(capsys, caplog, "frobnicate")) == 2


def test_warning_is_at_warning_level_not_error(tmp_path, capsys):
    _read(tmp_path, "#frobnicate a\n")
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "ERROR" not in out


@pytest.mark.parametrize("keyword", sorted(VERBATIM_LINE))
def test_registered_directive_does_not_warn(tmp_path, capsys, caplog, keyword):
    """Inference from the ticket (the warning is for *unknown* directives)."""
    _read(tmp_path, _top(VERBATIM_LINE[keyword]))
    out = capsys.readouterr().out
    assert "WARNING" not in out
    assert not [r for r in caplog.records if r.levelname == "WARNING"]


def test_unknown_directive_with_rich_markup_is_warned_literally(tmp_path, capsys):
    """T-025: userMsg prints literally, so `[x]` in a name or text cannot break it."""
    _read(tmp_path, "#frobnicate [bold]x[/bold]\n")
    assert "WARNING" in capsys.readouterr().out


# --- capture boundary ----------------------------------------------------------


def test_capture_ends_at_end_of_line(tmp_path):
    first, _, _ = _roundtrip(tmp_path, "#frobnicate a b\nnext 5;\n")
    (d,) = _verbatims(first)
    assert d.text.strip() == "#frobnicate a b"
    assert first.next.value == 5


@pytest.mark.parametrize(
    "block",
    [
        "#frobnicate (a b\n    c d)",
        "#frobnicate {\n    inner 1;\n    deeper { z 2; }\n}",
        "#frobnicate #{\n    some code\n#}",
        '#frobnicate "quoted string"',
        "#frobnicate (a (b c) d\n    e)",
    ],
    ids=["parens", "braces", "code-block", "string", "nested-parens"],
)
def test_capture_runs_to_the_matching_close(tmp_path, block):
    first, _, text = _roundtrip(tmp_path, f"{block}\nafter 7;\n")
    (d,) = _verbatims(first)
    assert d.text.strip() == block
    assert first.after.value == 7
    assert _contains_run([ln.rstrip() for ln in text.splitlines()], block.split("\n"))


def test_entries_inside_captured_braces_are_not_attributes(tmp_path):
    first, _, _ = _roundtrip(tmp_path, "#frobnicate {\n    inner 1;\n}\nafter 7;\n")
    assert "inner" not in vars(first)


def test_balanced_close_inside_a_string_does_not_end_the_capture(tmp_path):
    """Boundary rules treat `"` as a bracket pair; a `)` inside it is text."""
    first, _, _ = _roundtrip(tmp_path, '#frobnicate ( "a ) b"\n    c)\nafter 7;\n')
    (d,) = _verbatims(first)
    assert d.text.strip().endswith("c)")
    assert first.after.value == 7


@pytest.mark.parametrize(
    "text, lineno",
    [
        ("#frobnicate (a b\nc d\n", 1),
        ("#frobnicate {\n    inner 1;\n", 1),
        ("#frobnicate #{\n    code\n", 1),
        ('#frobnicate "unterminated\nnext 1;\n', 1),
        ("ok 1;\n\n#frobnicate (a b\nc d\n", 3),
    ],
    ids=["paren", "brace", "code-block", "quote", "after-other-entries"],
)
def test_unbounded_unknown_directive_raises_with_file_and_line(tmp_path, text, lineno):
    path = _write(tmp_path, text, "unbalancedFile")
    header_lines = HEADER.count("\n")
    with pytest.raises(FoamKitError) as err:
        fkt.DictFileParser(path).readDictFile()
    msg = str(err.value)
    assert "unbalancedFile" in msg
    assert str(header_lines + lineno) in msg


def test_unbounded_directive_does_not_consume_the_rest_silently(tmp_path):
    path = _write(tmp_path, "#frobnicate (a b\nkeep 1;\nkeep2 2;\n")
    with pytest.raises(FoamKitError):
        fkt.DictFileParser(path).readDictFile()


@pytest.mark.parametrize("keyword", ["#include$x", "#include;x", "#include{x"])
def test_malformed_keyword_still_gives_unknown_directive_error(tmp_path, keyword):
    """Existing T-004 behaviour that must not loosen: tokens that cannot be a word."""
    path = _write(tmp_path, f'{keyword} "a"\n\nx 1;\n')
    with pytest.raises(FoamKitError, match="Unknown directive"):
        fkt.DictFileParser(path).readDictFile()


# --- directives followed by a dictionary on the next line ------------------------
# Real files contradict the ticket's boundary rule: `#codeDict` and `#word "name"`
# open their `{` on the NEXT line, so "a balanced bracket that opens on that line"
# would end the capture at the end of the directive line and leave `{ ... }` as an
# unnamed block.  These tests only require that the real text survives.


@XF_T028
def test_real_codeDict_with_following_block_round_trips(tmp_path):
    _, second, text = _roundtrip(tmp_path, _top(SNIPPETS["codeDict"]))
    assert _contains_run(_norm(text), _norm(SNIPPETS["codeDict"]))
    assert second.toString() == text


@XF_T028
def test_real_word_with_following_block_round_trips(tmp_path):
    _, second, text = _roundtrip(tmp_path, _top(SNIPPETS["word"]))
    assert _contains_run(_norm(text), _norm(SNIPPETS["word"]))
    assert second.toString() == text


@pytest.mark.parametrize(
    "line, lineno",
    [
        ("#message message-word", 18),
        ('#message "message string [] from ${FOAM_API:-unset}"', 21),
        ("#message { message block string from ${FOAM_API:-unset} }", 24),
    ],
)
def test_real_message_forms_round_trip(tmp_path, line, lineno):
    assert _lines("esi-v2606.good-word-expand.dict", lineno, lineno, "#message") == line
    _, second, text = _roundtrip(tmp_path, _top(line))
    assert _contains_run(_norm(text), _norm(line))
    assert second.toString() == text


# === real files, directive lines only ==========================================


ALL_FILES = [
    "esi-v2606.bendJunction.blockMeshDict",
    "foundation-14.roomHeating.fvModels",
    "foundation-14.aerofoilNACA0012Steady.U",
    "foundation-13.aerofoilNACA0012Steady.U",
    "esi-v2606.squareBend.blockMeshDict",
    "foundation-14.engine2Valve2D.fvConstraints",
]
# - Main blocker per file, per test (what it needs besides T-016).
_AERO = {
    "foundation-14.aerofoilNACA0012Steady.U": "T-027",
    "foundation-13.aerofoilNACA0012Steady.U": "T-027",
}
_LOAD_BLOCKERS = {
    **_AERO,
    "esi-v2606.squareBend.blockMeshDict": "T-026",
    "foundation-14.engine2Valve2D.fvConstraints": "T-029",
}
_ORDER_BLOCKERS = {**_LOAD_BLOCKERS, "foundation-14.roomHeating.fvModels": "T-029"}


@pytest.mark.parametrize("name", _file_params(ALL_FILES, _LOAD_BLOCKERS))
def test_real_file_loads(name):
    """No FoamKitError/TypeError on a real file that uses directives."""
    fkt.DictFileParser(RELEASES / name).readDictFile()


@pytest.mark.parametrize("name", _file_params(ALL_FILES, _ORDER_BLOCKERS))
def test_real_file_keeps_its_line_start_directives_in_order(name):
    d = fkt.DictFileParser(RELEASES / name).readDictFile()
    src = [
        " ".join(ln.split())
        for ln in _text(name).splitlines()
        if ln.lstrip().startswith("#")
    ]
    out = [
        " ".join(ln.split())
        for ln in d.toString().splitlines()
        if ln.lstrip().startswith("#")
    ]
    assert out == src


@pytest.mark.parametrize(
    "name",
    _file_params(
        ALL_FILES,
        {**_LOAD_BLOCKERS, "esi-v2606.bendJunction.blockMeshDict": "T-031"},
    ),
)
def test_real_file_second_write_is_stable(tmp_path, name):
    text = fkt.DictFileParser(RELEASES / name).readDictFile().toString()
    out = tmp_path / "again"
    out.write_text(text)
    assert fkt.DictFileParser(out).readDictFile().toString() == text


def test_real_bendJunction_inputMode_is_before_the_dictionary_content():
    d = fkt.DictFileParser(
        RELEASES / "esi-v2606.bendJunction.blockMeshDict"
    ).readDictFile()
    assert [v.keyword for v in _verbatims(d)] == ["inputMode"]


def _without_calc(tmp_path, name):
    """A real file minus its value-position `#calc` lines (T-027), written to tmp_path."""
    kept = [ln for ln in _text(name).split("\n") if "#calc " not in ln]
    path = tmp_path / "noCalc"
    path.write_text("\n".join(kept))
    return path


def test_real_aerofoil_calcInclude_is_verbatim_without_the_calc_entries(tmp_path):
    """Foundation 13: the file gets past `#calcInclude` (full load needs T-027)."""
    path = _without_calc(tmp_path, "foundation-13.aerofoilNACA0012Steady.U")
    d = fkt.DictFileParser(path).readDictFile()
    assert [v.keyword for v in _verbatims(d)] == ["calcInclude"]


def test_real_aerofoil_codeBlock_markers_are_verbatim_without_the_calc_entries(
    tmp_path,
):
    """Foundation 14: the file gets past `#codeBlock`, `#codeInclude`, `#endCodeBlock`."""
    path = _without_calc(tmp_path, "foundation-14.aerofoilNACA0012Steady.U")
    d = fkt.DictFileParser(path).readDictFile()
    assert [v.keyword for v in _verbatims(d)] == [
        "codeBlock",
        "codeInclude",
        "endCodeBlock",
    ]


# === iterDirectives =============================================================


def _case_with_directives(case):
    """pitzDaily with a real Foundation 14 momentumTransport (#print), a real
    ESI `#remove` line in fvSchemes and one unknown directive in fvSolution."""
    shutil.copyfile(RELEASES / PITZ_MT, case / "constant" / "momentumTransport")
    _add_line(case / "system" / "fvSchemes", SNIPPETS["remove"])
    _add_line(case / "system" / "fvSolution", "#frobnicate keep this")
    return case


def _add_line(path, line):
    """Insert `line` before the trailing `// ***` comment (or at the end)."""
    text = path.read_text()
    marker = text.rfind("// ****")
    if marker == -1:
        text = text.rstrip("\n") + f"\n\n{line}\n"
    else:
        text = text[:marker] + f"{line}\n\n" + text[marker:]
    path.write_text(text)


def _keywords_of(pairs):
    return sorted(d.keyword for _, d in pairs)


def test_init_works_on_a_case_with_print(case):
    _case_with_directives(case)
    c = pf.init(path=case)
    assert c.constant.momentumTransport.RAS.model.value == "kEpsilon"


def test_init_case_writes_print_back_unchanged(case):
    _case_with_directives(case)
    c = pf.init(path=case)
    out = c.constant.momentumTransport.toString()
    assert "    #print\n" in out


def test_iterDirectives_is_a_generator_of_pairs(case):
    c = pf.init(path=_case_with_directives(case))
    it = fkt.iterDirectives(c)
    assert iter(it) is it
    pairs = list(it)
    assert pairs
    assert all(isinstance(p, tuple) and len(p) == 2 for p in pairs)
    assert all(isinstance(d, fkt.ofVerbatimDirective) for _, d in pairs)


def test_iterDirectives_status_none_returns_every_verbatim_and_unknown(case):
    c = pf.init(path=_case_with_directives(case))
    assert _keywords_of(fkt.iterDirectives(c)) == ["frobnicate", "print", "remove"]


def test_iterDirectives_status_verbatim(case):
    c = pf.init(path=_case_with_directives(case))
    got = _keywords_of(fkt.iterDirectives(c, status="verbatim"))
    assert got == ["print", "remove"]


def test_iterDirectives_status_unknown(case):
    c = pf.init(path=_case_with_directives(case))
    got = list(fkt.iterDirectives(c, status="unknown"))
    assert _keywords_of(got) == ["frobnicate"]
    assert all(d.known is False for _, d in got)


def test_iterDirectives_verbatim_and_unknown_are_disjoint(case):
    """Reading of the ticket: unknown keywords are 'status=\"unknown\"', not 'verbatim'."""
    c = pf.init(path=_case_with_directives(case))
    ver = _keywords_of(fkt.iterDirectives(c, status="verbatim"))
    assert "frobnicate" not in ver


def test_iterDirectives_status_filters_are_subsets_of_all(case):
    c = pf.init(path=_case_with_directives(case))
    everything = _keywords_of(fkt.iterDirectives(c))
    for status in ("verbatim", "unknown"):
        part = _keywords_of(fkt.iterDirectives(c, status=status))
        assert all(everything.count(k) >= part.count(k) for k in part)


def test_iterDirectives_locations_say_where_each_directive_is(case):
    c = pf.init(path=_case_with_directives(case))
    by_kw = {}
    for loc, d in fkt.iterDirectives(c):
        by_kw.setdefault(d.keyword, []).append(str(loc))
    assert any("momentumTransport" in ln for ln in by_kw["print"])
    assert any("fvSchemes" in ln for ln in by_kw["remove"])
    assert any("fvSolution" in ln for ln in by_kw["frobnicate"])
    assert len({ln for locs in by_kw.values() for ln in locs}) == 3


def test_iterDirectives_accepts_a_folder(case):
    c = pf.init(path=_case_with_directives(case))
    assert _keywords_of(fkt.iterDirectives(c.constant)) == ["print"]
    assert _keywords_of(fkt.iterDirectives(c.system, status="unknown")) == [
        "frobnicate"
    ]


def test_iterDirectives_rejects_an_unknown_status(tmp_path):
    d = _read(tmp_path, "a 1;" + chr(10))
    with pytest.raises(ValueError):
        list(fkt.iterDirectives(d, status="bogus"))


def test_iterDirectives_accepts_a_dict_file():
    d = fkt.DictFileParser(RELEASES / PITZ_MT).readDictFile()
    assert _keywords_of(fkt.iterDirectives(d)) == ["print"]


def test_iterDirectives_finds_directives_in_subdicts(tmp_path):
    d = _read(
        tmp_path, "sub\n{\n    inner\n    {\n        #frobnicate deep\n    }\n}\n"
    )
    assert _keywords_of(fkt.iterDirectives(d)) == ["frobnicate"]


def test_iterDirectives_on_file_without_directives_yields_nothing(tmp_path):
    assert list(fkt.iterDirectives(_read(tmp_path, "a 1;\n"))) == []


def test_iterDirectives_survives_save_and_load(case):
    c = pf.init(path=_case_with_directives(case))
    c.save(path=case)
    loaded = pf.load(path=case)
    assert _keywords_of(fkt.iterDirectives(loaded)) == _keywords_of(
        fkt.iterDirectives(c)
    )
    assert (
        loaded.constant.momentumTransport.toString()
        == c.constant.momentumTransport.toString()
    )


def test_case_with_directives_writes_files_back_with_directives(case):
    c = pf.init(path=_case_with_directives(case))
    c.save(path=case)
    pf.load(path=case).write()
    assert "    #print\n" in (case / "constant" / "momentumTransport").read_text()
    assert "#frobnicate keep this" in (case / "system" / "fvSolution").read_text()
    assert SNIPPETS["remove"] in (case / "system" / "fvSchemes").read_text()


def test_deepcopy_of_case_keeps_directives(case):
    import copy

    c = pf.init(path=_case_with_directives(case))
    c2 = copy.deepcopy(c)
    assert _keywords_of(fkt.iterDirectives(c2)) == _keywords_of(fkt.iterDirectives(c))


@XF_T026
def test_iterDirectives_lists_the_real_ifeq_blocks(case):
    shutil.copyfile(
        RELEASES / "foundation-14.cylinder.fvSchemes", case / "system" / "fvSchemes"
    )
    c = pf.init(path=case)
    got = _keywords_of(fkt.iterDirectives(c, status="verbatim"))
    assert got.count("ifeq") == 2


# === unchanged behaviour (regression guard) ==================================


def test_golden_pitzDaily_case_has_no_directives_to_report(case):
    c = pf.init(path=case)
    assert list(fkt.iterDirectives(c, status="unknown")) == []
