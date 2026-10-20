"""Header styles and header-less dictionaries (T-005, plan bug B2).

Real banner headers (Foundation open, ESI boxed, foam-extend boxed) are pinned
as recognised.  Dictionaries that start directly with a `FoamFile` block (no
banner) must also be recognised; those tests fail until T-005 is implemented.

Header *writing* is T-006 and is deliberately not tested here.

The three non-Foundation fixtures in tests/fixtures/headers/ are byte-exact
copies of the real pitzDaily `system/controlDict` files (fetched 2026-10-19):
- esi-v2606.controlDict:
  https://gitlab.com/openfoam/core/openfoam/-/raw/master/tutorials/incompressible/simpleFoam/pitzDaily/system/controlDict
- foam-extend-4.1.controlDict, foam-extend-5.0.controlDict:
  https://sourceforge.net/p/foam-extend/foam-extend-{4.1,5.0}/ci/master/tree/tutorials/incompressible/simpleFoam/pitzDaily/system/controlDict?format=raw
Header-less and negative variants are built inline under tmp_path.
"""

import importlib
import re
import shutil

import pytest

import foamkit.functions as pf
import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import FIXTURES

NL = chr(10)
HEADERS = FIXTURES / "headers"
REAL_FILES = {
    "foundation_open": FIXTURES / "pitzDaily" / "system" / "controlDict",
    "esi_v2606": HEADERS / "esi-v2606.controlDict",
    "foam_extend_4.1": HEADERS / "foam-extend-4.1.controlDict",
    "foam_extend_5.0": HEADERS / "foam-extend-5.0.controlDict",
}


def _lf(path):
    return path.read_bytes().replace(b"\r\n", b"\n").decode()


FOAMFILE = (
    "FoamFile\n"
    "{\n"
    "    version     2.0;\n"
    "    format      ascii;\n"
    "    class       dictionary;\n"
    "    object      fvSchemes;\n"
    "}\n"
)
BODY = (
    "\n"
    "application     simpleFoam;\n"
    "\n"
    "startFrom       startTime;\n"
    "\n"
    "endTime         2000;\n"
    "\n"
    "writeInterval   100;\n"
)
FOUNDATION_HEADER = _lf(REAL_FILES["foundation_open"]).split("FoamFile")[0]


def _write(path, text, newline="\n"):
    path.write_bytes(text.replace("\n", newline).encode())
    return path


def _entries(path):
    """Public entry names of a parsed dictionary file."""
    d = fkt.DictFileParser(path).readDictFile()
    return {k for k in vars(d) if not k.startswith("_")}


def _body_keywords(text):
    """Top-level keywords written at column 0 after the FoamFile block."""
    body = text.split("\n}\n", 1)[1]
    return set(re.findall(r"^([A-Za-z]\w*)", body, flags=re.M))


def _values(path):
    d = fkt.DictFileParser(path).readDictFile()
    return {
        k: getattr(v, "value", v)
        for k, v in vars(d).items()
        if k in ("application", "startFrom", "endTime", "writeInterval")
    }


# --- characterization: real headers are recognised and fully read -----------


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_real_header_is_recognised(name):
    assert pf.isDictFile(REAL_FILES[name]) is True


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_real_header_with_crlf_is_recognised(tmp_path, name):
    path = _write(tmp_path / "controlDict", _lf(REAL_FILES[name]), "\r\n")
    assert pf.isDictFile(path) is True


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_real_header_file_reads_every_entry(name):
    text = _lf(REAL_FILES[name])
    expected = _body_keywords(text) - {"FoamFile"}
    assert expected  # guard: the regex found entries
    assert _entries(REAL_FILES[name]) == expected


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_init_loads_real_header_controlDict(case, name):
    shutil.copy(REAL_FILES[name], case / "system" / "controlDict")
    c = pf.init(path=case)
    assert c.system.controlDict.endTime.value == 2000
    assert "fvSchemes" in vars(c.system)


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_real_header_binary_variant_is_rejected(tmp_path, name):
    path = tmp_path / "bin"
    path.write_bytes(b"\x00\x01\x02" * 100 + REAL_FILES[name].read_bytes())
    assert pf.isDictFile(path) is False


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_real_header_over_size_limit_is_rejected(tmp_path, monkeypatch, name):
    mod = importlib.import_module("foamkit.types._isDictFile")
    size = REAL_FILES[name].stat().st_size
    assert pf.isDictFile(REAL_FILES[name]) is True
    monkeypatch.setattr(mod, "getFoamKitConfig", lambda key: size - 1)
    assert pf.isDictFile(REAL_FILES[name]) is False


@pytest.mark.parametrize(
    "name, content",
    [
        ("log", "Create time\n\nCreate mesh for time = 0\n\nTime = 1\n\nEnd\n"),
        ("script", '#!/bin/sh\ncd "${0%/*}" || exit 1\n./Allrun\n'),
        ("python", "import sys\n\nprint(sys.argv)\n"),
        ("probe_data", "# Time\tp\n0\t1\n1\t2\n"),
        ("stl", "solid x\n" + "facet normal 0 0 1\n" * 50 + "endsolid x\n"),
        ("empty", ""),
        ("plain_text", "Remember to rerun blockMesh.\n"),
        ("c_comment_only", "/* just a comment */\n\nint main() {}\n"),
        ("prose", "Notes on the FoamFile header.\nIt is a dictionary.\n"),
    ],
)
def test_non_openfoam_text_is_rejected(tmp_path, name, content):
    assert pf.isDictFile(_write(tmp_path / name, content)) is False


def test_text_with_banner_start_but_not_a_header_is_rejected(tmp_path):
    """A box that is not the OpenFOAM banner (same first line, other content)."""
    banner_start = "/*--------------------------------*- C++ -*----------------------------------*\\\n"
    text = (
        banner_start + "| my own header |\n| nothing |\n\\*-----*/\nx 1;\ny 2;\nz 3;\n"
    )
    assert pf.isDictFile(_write(tmp_path / "x", text)) is False


# --- characterization: header-less shapes that must stay rejected -----------


@pytest.mark.parametrize(
    "name, content",
    [
        ("repeated_empty_foamfile", "FoamFile\n{\n}\n" * 10),
        (
            "foamfile_without_class_or_format",
            "FoamFile\n{\n    version 2.0;\n}\n" + BODY,
        ),
        ("empty_block_then_body", "FoamFile\n{\n}\n" + BODY),
        ("foamfile_without_brace", "FoamFile\n" + BODY),
        ("longer_first_word", FOAMFILE.replace("FoamFile", "FoamFileExtra") + BODY),
        ("comment_before_foamfile", "// my notes\n" + FOAMFILE + BODY),
        ("text_before_foamfile", "Create time\nReading\n" + FOAMFILE + BODY),
        (
            "class_outside_the_block",
            "FoamFile\n{\n    version 2.0;\n}\nclass dictionary;\n" + BODY,
        ),
        ("bom", "﻿" + FOAMFILE + BODY),
    ],
)
def test_headerless_lookalike_is_rejected(tmp_path, name, content):
    assert pf.isDictFile(_write(tmp_path / name, content)) is False


def test_headerless_binary_is_rejected(tmp_path):
    path = tmp_path / "U"
    path.write_bytes((FOAMFILE + BODY).encode() + b"\x00\x00\x80\x3f" * 400)
    assert pf.isDictFile(path) is False


def test_headerless_invalid_utf8_is_rejected(tmp_path):
    path = tmp_path / "latin1"
    path.write_bytes((FOAMFILE + BODY).encode() + b"\n// caf\xe9\n")
    assert pf.isDictFile(path) is False


def test_headerless_in_a_log_after_other_text_is_rejected(tmp_path):
    text = "Create time\nReading dictionary\n" + FOAMFILE
    assert pf.isDictFile(_write(tmp_path / "log", text)) is False


# --- specification: header-less dictionaries are recognised ------------------


HEADERLESS = {
    "plain": FOAMFILE + BODY,
    "brace_on_same_line": FOAMFILE.replace("FoamFile\n{\n", "FoamFile {\n") + BODY,
    "blank_line_before_brace": FOAMFILE.replace("FoamFile\n{", "FoamFile\n\n{") + BODY,
    "leading_blank_lines": "\n\n" + FOAMFILE + BODY,
    "only_class": FOAMFILE.replace("    format      ascii;\n", "") + BODY,
    "only_format": FOAMFILE.replace("    class       dictionary;\n", "") + BODY,
}
# - Block shapes DictFileParser cannot read yet; they are rejected (skipped by
# - `pf.init`) for now.  T-021 will accept them, which flips the strict xfails.
# - Approved rule: after `{` the rest of its line is blank, and the closing `}`
# - is the first non-whitespace character on its line.
ONE_LINE_BLOCK = "FoamFile { version 2.0; format ascii; class dictionary; }\n"
UNPARSEABLE = {
    "one_line_with_body": ONE_LINE_BLOCK + BODY,
    "one_line_alone": ONE_LINE_BLOCK,
    "content_on_brace_line": "FoamFile { format ascii;\n    class dictionary;\n}\n"
    + BODY,
    "closing_brace_then_content": "FoamFile\n{\n    format ascii;\n"
    "    class dictionary;\n} application simpleFoam;\n\nendTime 2000;\n",
    "closing_brace_space_semicolon": "FoamFile\n{\n    format ascii;\n"
    "    class dictionary;\n} ;\n" + BODY,
    "closing_brace_mid_line": "FoamFile {\n format ascii; class dictionary; }\n" + BODY,
}
UNPARSEABLE_XFAIL = pytest.mark.xfail(
    strict=True, reason="T-021: FoamFile block shape not parseable yet"
)


@pytest.mark.parametrize("variant", list(HEADERLESS))
def test_headerless_file_is_recognised(tmp_path, variant):
    assert pf.isDictFile(_write(tmp_path / "fvSchemes", HEADERLESS[variant])) is True


def test_headerless_file_with_crlf_is_recognised(tmp_path):
    path = _write(tmp_path / "fvSchemes", HEADERLESS["plain"], "\r\n")
    assert pf.isDictFile(path) is True


def test_headerless_file_over_size_limit_is_rejected(tmp_path, monkeypatch):
    """Recognised without the limit, rejected with it."""
    mod = importlib.import_module("foamkit.types._isDictFile")
    text = HEADERLESS["plain"]
    path = _write(tmp_path / "fvSchemes", text)
    assert pf.isDictFile(path) is True
    monkeypatch.setattr(mod, "getFoamKitConfig", lambda key: len(text.encode()) - 1)
    assert pf.isDictFile(path) is False


def test_headerless_parsed_values_equal_those_of_the_open_banner(tmp_path):
    expected = _values(_write(tmp_path / "open", FOUNDATION_HEADER + FOAMFILE + BODY))
    assert expected["endTime"] == 2000  # guard: the reference itself parsed
    assert _values(_write(tmp_path / "bare", HEADERLESS["plain"])) == expected


def test_init_includes_headerless_fvSchemes(case):
    before = set(vars(pf.init(path=case).system))
    assert "fvSchemes" in before  # guard
    _write(case / "system" / "fvSchemes", HEADERLESS["plain"])
    c = pf.init(path=case)
    assert before <= set(vars(c.system))
    assert c.system.fvSchemes.endTime.value == 2000


def test_init_includes_headerless_dictionary_next_to_non_dictionary_files(case):
    (case / "system" / "notes.txt").write_text("Remember to rerun blockMesh.\n")
    (case / "system" / "log.simpleFoam").write_text("Create time\n\nEnd\n")
    _write(case / "system" / "fvSchemes", HEADERLESS["plain"])
    c = pf.init(path=case)
    assert c.system.fvSchemes.endTime.value == 2000
    for name in ("notes_txt", "notes", "log_simpleFoam", "log"):
        assert not hasattr(c.system, name)


@UNPARSEABLE_XFAIL
@pytest.mark.parametrize("shape", list(UNPARSEABLE))
def test_unparseable_block_shape_is_recognised_eventually(tmp_path, shape):
    assert pf.isDictFile(_write(tmp_path / "fvSchemes", UNPARSEABLE[shape])) is True


@pytest.mark.parametrize("shape", list(UNPARSEABLE))
def test_unparseable_block_shape_is_rejected_for_now(tmp_path, shape):
    assert pf.isDictFile(_write(tmp_path / "fvSchemes", UNPARSEABLE[shape])) is False


@pytest.mark.parametrize("shape", list(UNPARSEABLE))
def test_init_skips_unparseable_block_shape(case, shape):
    """As on HEAD: the file is left out and init still succeeds."""
    before = set(vars(pf.init(path=case).system))
    _write(case / "system" / "extraDict", UNPARSEABLE[shape])
    c = pf.init(path=case)
    assert set(vars(c.system)) == before
    assert not hasattr(c.system, "extraDict")


@pytest.mark.parametrize(
    "tail",
    ["", ";", " // end of header", "; // x"],
    ids=["bare", "semicolon", "comment", "semicolon_comment"],
)
def test_headerless_closing_brace_trailer_parses_and_round_trips(tmp_path, tail):
    block = FOAMFILE.replace("}\n", "}" + tail + "\n")
    src = _write(tmp_path / "in", block + BODY)
    assert pf.isDictFile(src) is True
    assert {"application", "endTime"} <= _entries(src)
    assert "}" not in _entries(src)
    text = fkt.DictFileParser(src).readDictFile().toString()
    out = _write(tmp_path / "out", text)
    assert pf.isDictFile(out) is True
    assert fkt.DictFileParser(out).readDictFile().toString() == text


BRACE_LINES = {
    "nl_brace": "FoamFile\n{",
    "same_line_brace": "FoamFile {",
    "tab_brace": "FoamFile\t{",
    "blank_then_brace": "FoamFile\n\n{",
    "content_on_brace_line": "FoamFile { format ascii;",
    "brace_comment": "FoamFile\n{ // c",
}
CLOSING_LINES = {
    "close": "}",
    "close_semi": "};",
    "close_space_semi": "} ;",
    "close_semi_comment": "}; // x",
    "close_comment": "} // x",
    "close_block_comment": "} /* c */",
    "close_then_entry": "} application simpleFoam;",
    "indented_close": "  }",
    "close_tab_semi": "}\t;",
    "close_double_semi": "};;",
    "close_space_semi_comment": "} ;// x",
}
SHORT_BODY = "\napplication simpleFoam;\n\nendTime 2000;\n"


def _generated_block(brace, closing, with_body):
    entries = ["    version 2.0;"]
    if "format" not in brace:
        entries.append("    format ascii;")
    entries.append("    class dictionary;")
    text = brace + "\n" + "\n".join(entries) + "\n" + closing + "\n"
    return text + (SHORT_BODY if with_body else "")


GENERATED = [
    pytest.param(b, c, body, eol, id=f"{b}-{c}-{'body' if body else 'nobody'}-{eol}")
    for b in BRACE_LINES
    for c in CLOSING_LINES
    for body in (True, False)
    for eol in ("lf", "crlf")
    if body or eol == "lf"  # CRLF is only crossed with the body variants (runtime)
]


@pytest.mark.parametrize("brace, closing, with_body, eol", GENERATED)
def test_every_accepted_headerless_variant_loads_and_rewrites(
    tmp_path, brace, closing, with_body, eol
):
    """Invariant: whatever `_isDictFile` accepts must parse, keep its keys and re-read.

    Variants it rejects are skipped (rejecting is always safe).
    """
    text = _generated_block(BRACE_LINES[brace], CLOSING_LINES[closing], with_body)
    src = _write(tmp_path / "in", text, "\r\n" if eol == "crlf" else "\n")
    if not pf.isDictFile(src):
        return
    d = fkt.DictFileParser(src).readDictFile()
    assert not [k for k in vars(d) if k.startswith("}")]
    if with_body:
        assert {"application", "endTime"} <= set(vars(d))
    out = _write(tmp_path / "out", d.toString())
    assert pf.isDictFile(out) is True
    fkt.DictFileParser(out).readDictFile()


def test_blank_line_between_foamfile_and_brace_under_a_banner(tmp_path):
    """Regression: this was an IndexError on HEAD; entries are read and the write is stable."""
    block = "FoamFile\n\n{\n    format ascii;\n    class dictionary;\n}\n"
    src = _write(tmp_path / "in", FOUNDATION_HEADER + block + BODY)
    assert pf.isDictFile(src) is True
    text = fkt.DictFileParser(src).readDictFile().toString()
    assert {"application", "startFrom", "endTime", "writeInterval"} <= _entries(src)
    assert _values(src)["endTime"] == 2000
    out = _write(tmp_path / "out", text)
    assert fkt.DictFileParser(out).readDictFile().toString() == text


@pytest.mark.parametrize(
    "block",
    [
        'FoamFile\n{\n    note "a}b";\n    version 2.0;\n}\nclass dictionary;\n',
        'FoamFile\n{\n    note "a}b";\n    version 2.0;\n}\nformat ascii;\n',
    ],
    ids=["class_after_block", "format_after_block"],
)
def test_quoted_brace_in_block_without_class_or_format_is_rejected(tmp_path, block):
    assert pf.isDictFile(_write(tmp_path / "x", block + BODY)) is False


# --- header-less files are written back without a banner ---------------------


@pytest.mark.parametrize(
    "variant",
    [
        pytest.param(
            v,
            marks=pytest.mark.xfail(
                strict=True,
                reason="T-006: a same-line `FoamFile {` gains one blank line on the "
                "first write",
            ),
        )
        if v == "brace_on_same_line"
        else v
        for v in HEADERLESS
    ],
)
def test_headerless_file_is_written_back_without_a_banner(tmp_path, variant):
    first = fkt.DictFileParser(_write(tmp_path / "in", HEADERLESS[variant]))
    text = first.readDictFile().toString()
    assert text.startswith("FoamFile")
    assert "/*--" not in text
    out = _write(tmp_path / "out", text)
    assert pf.isDictFile(out) is True
    assert fkt.DictFileParser(out).readDictFile().toString() == text


# --- direct DictFileParser use on malformed header-less look-alikes ----------


@pytest.mark.parametrize(
    "text",
    [
        "FoamFileExtra { class dictionary; }" + NL + BODY,
        FOAMFILE.replace("FoamFile", "FoamFileExtra") + BODY,
    ],
    ids=["one_line", "multi_line"],
)
def test_foamfile_prefixed_word_is_not_parsed_as_headerless(tmp_path, text):
    path = _write(tmp_path / "x", text)
    with pytest.raises(FoamKitError, match="Invalid OpenFOAM file specified"):
        fkt.DictFileParser(path).readDictFile()


@pytest.mark.parametrize(
    "text",
    ["FoamFile" + NL * 3, FOUNDATION_HEADER + "FoamFile" + NL * 3],
    ids=["headerless", "with_banner"],
)
def test_file_ending_with_foamfile_raises_foamkit_error(tmp_path, text):
    path = _write(tmp_path / "x", text)
    with pytest.raises(FoamKitError):
        fkt.DictFileParser(path).readDictFile()
