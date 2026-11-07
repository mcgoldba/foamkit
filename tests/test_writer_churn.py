"""
T-019: an unedited read -> write adds no trailing whitespace and no blank line
after the FoamFile block that the source did not have.

Evidence on current code (all 2026-11-07, `toString()` of an unedited read):

- `; ` at the end of every entry written through `_ofTypeBase.toString(ofRep=True)`
  (foamkit/types/__init__.py `str_ += "; "`), in the FoamFile block and elsewhere;
- whitespace-only lines inside nested dictionaries and lists, because
  `ofDict.toString` / `ofList` output is split on "\n" and every piece, including
  the empty ones after `}\n\n`, gets the indent prefix;
- one blank line after the FoamFile `}`, because the parsed FoamFile is an
  `ofDict`, whose `toString` ends in "}\n\n".

Key/value padding and layout are T-020 and are not tested here.
"""

import pytest

import foamkit.types as pt
from conftest import FIXTURES, GOLDEN, TESTS

RELEASES = TESTS / "releases"

SOURCES = [
    # ESI v2606, foam-extend 4.1 / 5.0 headers, Foundation 9 pitzDaily
    FIXTURES / "headers" / "esi-v2606.controlDict",
    FIXTURES / "headers" / "foam-extend-4.1.controlDict",
    FIXTURES / "headers" / "foam-extend-5.0.controlDict",
    FIXTURES / "pitzDaily" / "system" / "controlDict",
    FIXTURES / "pitzDaily" / "system" / "fvSchemes",
    FIXTURES / "pitzDaily" / "0" / "U",
    RELEASES / "foundation-11.controlDict",
    RELEASES / "foundation-11.heatedDuct.snappyHexMeshDict",
    RELEASES / "foundation-14.pitzDaily.momentumTransport",
    RELEASES / "foundation-14.hotWire.controlDict",
    RELEASES / "esi-v2606.floatingObject.dynamicMeshDict",
    RELEASES / "esi-v2606.bendJunction.blockMeshDict",
]


def _write(path):
    return pt.DictFileParser(path).readDictFile().toString().replace("\r\n", "\n")


def _blanks_after_foamfile(text):
    """Blank lines between the FoamFile closing `}` and the next non-blank line."""
    lines = text.replace("\r\n", "\n").split("\n")
    start = lines.index("FoamFile")
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("}"))
    n = 0
    while end + 1 + n < len(lines) and not lines[end + 1 + n].strip():
        n += 1
    return n


def _trailing_ws(text):
    return [
        (i + 1, ln)
        for i, ln in enumerate(text.replace("\r\n", "\n").split("\n"))
        if ln != ln.rstrip()
    ]


def _id(path):
    return path.name


def _params():
    return [pytest.param(p, id=_id(p)) for p in SOURCES]


@pytest.mark.parametrize("path", _params())
def test_no_written_line_ends_in_whitespace(path):
    assert _trailing_ws(_write(path)) == []


@pytest.mark.parametrize("path", _params())
def test_blank_lines_after_foamfile_match_source(path):
    src = _blanks_after_foamfile(path.read_text(encoding="utf-8"))
    assert _blanks_after_foamfile(_write(path)) == src


@pytest.mark.parametrize(
    "blanks",
    [
        0,
        1,
        2,
    ],
)
def test_synthetic_blank_lines_after_foamfile(blanks, tmp_path):
    src = (
        "FoamFile\n{\n    version 2.0;\n    format ascii;\n    class dictionary;\n"
        "    object x;\n}\n" + "\n" * blanks + "a 1;\n"
    )
    f = tmp_path / "x"
    f.write_text(src)
    assert _blanks_after_foamfile(_write(f)) == blanks


def test_goldens_have_no_trailing_whitespace():
    goldens = sorted(p for p in GOLDEN.rglob("*") if p.is_file())
    assert goldens
    bad = {
        p.relative_to(GOLDEN).as_posix(): len(
            _trailing_ws(p.read_text(encoding="utf-8"))
        )
        for p in goldens
    }
    bad = {k: v for k, v in bad.items() if v}
    assert not bad, f"{len(bad)} golden files with trailing whitespace: {bad}"
