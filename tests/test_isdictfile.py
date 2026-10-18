"""OpenFOAM dictionary file detection."""
import pytest

import foamkit.functions as pf
from conftest import FIXTURES

#- Normalized to LF, as the variants below add their own line endings
REAL = (FIXTURES / "pitzDaily" / "system" / "controlDict").read_bytes() \
    .replace(b"\r\n", b"\n")
LINES = REAL.split(b"\n")


@pytest.mark.parametrize("name, content, expected", [
    ("real", REAL, True),
    ("crlf", REAL.replace(b"\n", b"\r\n"), True),
    ("cr_only", REAL.replace(b"\n", b"\r"), True),
    ("preceded_by_text", b"some text\n" + REAL, True),
    ("bom", b"\xef\xbb\xbf" + REAL, False),
    ("empty", b"", False),
    ("banner_without_following_line", b"\n".join(LINES[:7]) + b"\n", False),
    ("banner_plus_one_line", b"\n".join(LINES[:8]), True),
    ("invalid_utf8", REAL + b"\n// caf\xe9\n", False),
    ("binary", b"\x00\x01\x02" * 100 + REAL, False),
    ("no_banner", b"FoamFile\n{\n}\n" * 10, False),
    ("indented_banner", b"\n".join(b" " + l for l in LINES), False),
    ("stl", b"solid x\n" + b"facet normal 0 0 1\n" * 1000, False),
])
def test_isDictFile(tmp_path, name, content, expected):
    path = tmp_path / name
    path.write_bytes(content)
    assert pf.isDictFile(path) is expected


def test_directory_is_not_a_dict_file(tmp_path):
    assert pf.isDictFile(tmp_path) is False


def test_files_over_size_limit_are_skipped(tmp_path, monkeypatch):
    import importlib
    mod = importlib.import_module("foamkit.types._isDictFile")
    path = tmp_path / "controlDict"
    path.write_bytes(REAL)
    monkeypatch.setattr(mod, "getFoamKitConfig", lambda key: len(REAL) - 1)
    assert pf.isDictFile(path) is False
