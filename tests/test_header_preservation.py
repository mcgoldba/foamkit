"""Header preserved on write (T-006, plan bugs B3, B4 and the same-line `FoamFile {`).

Only the header lines (everything up to and including the closing
`\\*---...---*/` banner line) are compared, because body whitespace is T-019/T-020.

Fixtures are the real, byte-exact files described in test_banner_variants.py:
tests/fixtures/headers/*.controlDict (ESI v2606, foam-extend 4.1 and 5.0) and
tests/fixtures/pitzDaily (Foundation open banner).

B4 decision (for the implementer): the over-long-line tests accept either fix,
"the intended attribute is truncated" or "the truncation path is removed
because header text is kept verbatim".  Both satisfy them; the old behaviour
(creating a stray `line0` attribute) does not.
"""

import re
import shutil

import pytest

import foamkit.functions as pf
import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import FIXTURES

HEADERS = FIXTURES / "headers"
REAL_FILES = {
    "foundation_open": FIXTURES / "pitzDaily" / "system" / "controlDict",
    "esi_v2606": HEADERS / "esi-v2606.controlDict",
    "foam_extend_4.1": HEADERS / "foam-extend-4.1.controlDict",
    "foam_extend_5.0": HEADERS / "foam-extend-5.0.controlDict",
}
BOXED = ["esi_v2606", "foam_extend_4.1", "foam_extend_5.0"]
CLOSING = re.compile(r"^\\\*-+\*/$", re.M)


def _src(name):
    return REAL_FILES[name].read_bytes().replace(b"\r\n", b"\n").decode()


def _header_of(text):
    """Text from the start up to and including the closing banner line."""
    m = CLOSING.search(text)
    assert m, "no closing banner line"
    return text[: m.end()] + "\n"


def _written(path):
    return fkt.DictFileParser(path).readDictFile().toString()


# --- characterization: what already works ------------------------------------


def test_fixture_headers_are_what_the_tests_assume():
    """Guard: seven-line banners, boxed ones have `|` on the five inner lines."""
    for name in REAL_FILES:
        lines = _header_of(_src(name)).split("\n")[:-1]
        assert len(lines) == 7, name
    for name in BOXED:
        inner = _header_of(_src(name)).split("\n")[1:6]
        assert all(ln.startswith("|") and ln.endswith("|") for ln in inner), name


def test_foundation_open_banner_is_written_back_byte_for_byte():
    out = _written(REAL_FILES["foundation_open"])
    assert _header_of(out) == _header_of(_src("foundation_open"))


@pytest.mark.parametrize(
    "path",
    sorted(p for p in (FIXTURES / "pitzDaily" / "system").iterdir()),
    ids=lambda p: p.name,
)
def test_every_foundation_fixture_header_is_written_back_byte_for_byte(path):
    text = path.read_bytes().replace(b"\r\n", b"\n").decode()
    assert _header_of(_written(path)) == _header_of(text)


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_line_attributes_stay_populated_with_the_banner_text(name):
    h = fkt.DictFileParser(REAL_FILES[name]).readDictFile()._header
    for attr in ("line1", "line2", "line3", "line4", "line5"):
        assert isinstance(getattr(h, attr), str), attr
    product = "foam-extend" if name.startswith("foam_extend") else "OpenFOAM"
    assert product in h.line2


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_reading_a_header_does_not_change_the_body_keywords(name):
    d = fkt.DictFileParser(REAL_FILES[name]).readDictFile()
    assert d.endTime.value == 2000


# --- specification: B3, header bytes preserved -------------------------------


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_header_bytes_are_preserved_on_write(name):
    out = _written(REAL_FILES[name])
    assert _header_of(out) == _header_of(_src(name))


@pytest.mark.parametrize("name", BOXED)
def test_boxed_banner_keeps_its_pipe_borders(name):
    out_lines = _written(REAL_FILES[name]).split("\n")
    for ln in out_lines[1:6]:
        assert ln.startswith("|") and ln.endswith("|"), ln


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_header_survives_a_second_write(tmp_path, name):
    first = _written(REAL_FILES[name])
    again = tmp_path / "controlDict"
    again.write_bytes(first.encode())
    assert _header_of(_written(again)) == _header_of(_src(name))


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_header_with_crlf_source_is_written_back_with_the_same_lines(tmp_path, name):
    path = tmp_path / "controlDict"
    path.write_bytes(_src(name).replace("\n", "\r\n").encode())
    out = _written(path).replace("\r\n", "\n")
    assert _header_of(out) == _header_of(_src(name))


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_header_is_preserved_through_case_write(case, name):
    shutil.copy(REAL_FILES[name], case / "system" / "controlDict")
    pf.init(path=case).save(path=case)
    pf.load(path=case).write()
    on_disk = (case / "system" / "controlDict").read_bytes().decode()
    assert _header_of(on_disk.replace("\r\n", "\n")) == _header_of(_src(name))


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_only_the_header_is_in_scope_the_foamfile_block_is_still_written(name):
    """Guard against fixing the header by dropping the block that follows it."""
    out = _written(REAL_FILES[name])
    assert out.split("*/\n", 1)[1].startswith("FoamFile\n{\n")


def test_edit_keeps_header_and_changes_the_edited_value(tmp_path):
    d = fkt.DictFileParser(REAL_FILES["esi_v2606"]).readDictFile()
    d.endTime = 500
    out = d.toString()
    assert _header_of(out) == _header_of(_src("esi_v2606"))
    assert re.search(r"^endTime\s+500;", out, flags=re.M)


def test_default_header_for_a_new_dict_file_still_has_a_closing_banner():
    """Characterization (new files are T-009): the default header is unchanged in shape."""
    text = fkt.ofDictFile().toString()
    assert CLOSING.search(text)
    assert text.startswith("/*--")


# --- specification: B4 ------------------------------------------------------


def _raw_lines(inner_index, long_text):
    raw = list(fkt.OF_HEADER)
    raw[inner_index] = raw[inner_index][:29] + long_text
    return raw


@pytest.mark.parametrize("idx", [1, 2, 3, 4])
def test_overlong_header_line_does_not_create_a_stray_attribute(idx):
    h = fkt.ofHeader(_raw_lines(idx, "x" * 80))
    assert not hasattr(h, "line0")


@pytest.mark.parametrize("idx", [1, 2, 3, 4])
def test_overlong_header_line_is_truncated_on_the_intended_attribute_or_kept(idx):
    """Either `line<idx>` is cut to 51 chars (B4 fixed) or kept in full (B4 removed)."""
    long_text = "x" * 80
    h = fkt.ofHeader(_raw_lines(idx, long_text))
    value = getattr(h, f"line{idx}")
    assert len(value) == 51 or long_text in value


@pytest.mark.parametrize("idx", [1, 2, 3, 4])
def test_overlong_header_line_leaves_the_other_attributes_alone(idx):
    short = fkt.ofHeader(list(fkt.OF_HEADER))
    h = fkt.ofHeader(_raw_lines(idx, "x" * 80))
    for other in (1, 2, 3, 4, 5):
        if other != idx:
            assert getattr(h, f"line{other}") == getattr(short, f"line{other}")


# --- specification: same-line `FoamFile {` (B10 part owned by T-006) -----------

NEXT_LINE = (
    "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
    "    class       dictionary;\n    object      fvSchemes;\n}\n"
)
SAME_LINE = NEXT_LINE.replace("FoamFile\n{\n", "FoamFile {\n")
BODY = "\napplication     simpleFoam;\n\nendTime         2000;\n"
BANNER = _header_of(_src("foundation_open"))
VARIANTS = {
    "bare": ("", ""),
    "foundation_banner": (BANNER, ""),
    "esi_banner": (_header_of(_src("esi_v2606")), ""),
}


def _write_file(tmp_path, text, name="in"):
    path = tmp_path / name
    path.write_bytes(text.encode())
    return path


@pytest.mark.parametrize("variant", list(VARIANTS))
def test_same_line_foamfile_populates_foamfile_attribute(tmp_path, variant):
    banner = VARIANTS[variant][0]
    path = _write_file(tmp_path, banner + SAME_LINE + BODY)
    d = fkt.DictFileParser(path).readDictFile()
    assert d._foamFile is not None
    assert d._foamFile.format.value == "ascii"
    assert d._foamFile.object.value == "fvSchemes"


@pytest.mark.parametrize("variant", list(VARIANTS))
def test_same_line_foamfile_is_not_an_ordinary_entry(tmp_path, variant):
    banner = VARIANTS[variant][0]
    path = _write_file(tmp_path, banner + SAME_LINE + BODY)
    d = fkt.DictFileParser(path).readDictFile()
    assert "FoamFile" not in {k for k in vars(d) if not k.startswith("_")}
    assert d.endTime.value == 2000


@pytest.mark.parametrize("variant", list(VARIANTS))
def test_same_line_foamfile_write_one_equals_write_two(tmp_path, variant):
    banner = VARIANTS[variant][0]
    path = _write_file(tmp_path, banner + SAME_LINE + BODY)
    first = _written(path)
    second = _written(_write_file(tmp_path, first, "out"))
    assert first == second


@pytest.mark.parametrize("variant", list(VARIANTS))
def test_same_line_foamfile_is_written_like_the_next_line_form(tmp_path, variant):
    banner = VARIANTS[variant][0]
    same = _written(_write_file(tmp_path, banner + SAME_LINE + BODY, "same"))
    nxt = _written(_write_file(tmp_path, banner + NEXT_LINE + BODY, "next"))
    assert same == nxt


def test_next_line_foamfile_write_one_equals_write_two(tmp_path):
    """Characterization: the next-line form already settles on the first write."""
    first = _written(_write_file(tmp_path, BANNER + NEXT_LINE + BODY))
    assert first == _written(_write_file(tmp_path, first, "out"))


def test_next_line_foamfile_populates_foamfile_attribute(tmp_path):
    d = fkt.DictFileParser(_write_file(tmp_path, BANNER + NEXT_LINE + BODY))
    assert d.readDictFile()._foamFile is not None


@pytest.mark.parametrize("name", list(REAL_FILES))
def test_same_line_foamfile_in_a_real_header_keeps_the_header(tmp_path, name):
    src = _src(name).replace("\nFoamFile\n{\n", "\nFoamFile {\n", 1)
    assert "FoamFile {\n" in src  # guard: the substitution applied
    out = _written(_write_file(tmp_path, src))
    assert _header_of(out) == _header_of(_src(name))
    reread = fkt.DictFileParser(_write_file(tmp_path, out, "o")).readDictFile()
    assert reread._foamFile is not None


# --- review follow-ups -------------------------------------------------------


@pytest.mark.parametrize("banner", ["", BANNER], ids=["bare", "banner"])
def test_no_space_brace_raises_foamkit_error_when_parsed_directly(tmp_path, banner):
    """As on HEAD: `FoamFile{` is not readable (T-021 owns accepting it)."""
    block = "FoamFile{\n    format ascii;\n    class dictionary;\n}\n"
    path = _write_file(tmp_path, banner + block + BODY)
    with pytest.raises(FoamKitError):
        fkt.DictFileParser(path).readDictFile()


SHORT_HEADER = "note */\n"


def _short_header_file(tmp_path):
    return _write_file(tmp_path, SHORT_HEADER + _src("esi_v2606"))


def test_short_header_does_not_raise_index_error(tmp_path):
    """Loading or a FoamKitError are both fine; an IndexError is the bug."""
    try:
        fkt.DictFileParser(_short_header_file(tmp_path)).readDictFile()
    except FoamKitError:
        pass


def test_short_header_loads_and_is_written_back_verbatim(tmp_path):
    """Preferred outcome: the file loads and its short header is kept as is."""
    path = _short_header_file(tmp_path)
    out = _written(path)
    assert out.startswith(SHORT_HEADER)
    assert fkt.DictFileParser(path).readDictFile().endTime.value == 2000


def test_init_does_not_crash_on_a_short_header_file(case):
    (case / "system" / "shortDict").write_bytes(
        (SHORT_HEADER + _src("esi_v2606")).encode()
    )
    pf.init(path=case)
