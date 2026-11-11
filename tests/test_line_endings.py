"""`case.write()` keeps each file's line endings (T-085, issue #113).

Specification tests for docs/tickets/T-085-keep-line-endings-on-write.md.  Everything
is compared as BYTES (`write_bytes` / `read_bytes`), so a test means the same thing on
Linux and Windows CI.

Today `DictFileParser` reads with universal newlines (the ending is lost) and
`ofCase.write` writes in text mode (`\n` becomes `os.linesep`), so:

    source   Windows (os.linesep CRLF)     Linux (os.linesep LF)
    LF       CRLF written (bug)            LF kept
    CRLF     CRLF kept                     LF written (bug)

Tests that fail on only one OS carry an OS-conditional strict xfail (see `_bug_on`);
on the other OS they pass today and act as characterization tests.  A new file is
written with `os.linesep` today, so it fails on Windows only.  The mixed-ending file
(option A of the ticket, ROADMAP's stated default) fails on every OS.
"""

import json
import re
import shutil

import pytest

import foamkit.functions as pf
import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import FIXTURES

PITZ = FIXTURES / "pitzDaily"
ENDINGS = {"LF": b"\n", "CRLF": b"\r\n"}


LF, CR = ENDINGS["LF"], b"\r"
ENDING_PARAMS = ["LF", "CRLF"]


def _files(case):
    """Every case file (not the `.params` cache) as {relative posix path: bytes}."""
    return {
        p.relative_to(case).as_posix(): p.read_bytes()
        for p in sorted(case.rglob("*"))
        if p.is_file() and ".params" not in p.relative_to(case).parts
    }


def _make_case(tmp_path, ending, name="case"):
    """A copy of the pitzDaily fixture with every file's lines ended by `ending`."""
    case = tmp_path / name
    shutil.copytree(PITZ, case)
    for p in case.rglob("*"):
        if p.is_file():
            text = p.read_bytes().replace(b"\r\n", b"\n")
            p.write_bytes(text.replace(b"\n", ENDINGS[ending]))
    return case


def _assert_all_endings(files, ending):
    for name, data in files.items():
        if ending == "LF":
            assert b"\r" not in data, name
        else:
            assert data.count(b"\n") == data.count(b"\r\n"), name
            assert b"\r\r" not in data, name


def _cache_round_trip(case):
    pf.init(path=case).save(path=case)
    return pf.load(path=case)


def test_fixture_copies_have_the_intended_endings(tmp_path):
    lf = _files(_make_case(tmp_path, "LF", "lf"))
    crlf = _files(_make_case(tmp_path, "CRLF", "crlf"))
    assert lf and lf.keys() == crlf.keys()
    _assert_all_endings(lf, "LF")
    _assert_all_endings(crlf, "CRLF")
    assert all(crlf[k] == lf[k].replace(b"\n", b"\r\n") for k in lf)


@pytest.mark.parametrize("ending", ENDING_PARAMS)
def test_unedited_init_write_is_byte_identical_to_source(tmp_path, ending):
    case = _make_case(tmp_path, ending)
    before = _files(case)
    pf.init(path=case).write()
    assert _files(case) == before


@pytest.mark.parametrize("ending", ENDING_PARAMS)
def test_unedited_cache_round_trip_write_is_byte_identical_to_source(tmp_path, ending):
    case = _make_case(tmp_path, ending)
    before = _files(case)
    _cache_round_trip(case).write()
    assert _files(case) == before


@pytest.mark.parametrize("ending", ENDING_PARAMS)
def test_init_write_gives_every_line_the_source_ending(tmp_path, ending):
    case = _make_case(tmp_path, ending)
    pf.init(path=case).write()
    _assert_all_endings(_files(case), ending)


@pytest.mark.parametrize("ending", ENDING_PARAMS)
def test_cache_round_trip_write_gives_every_line_the_source_ending(tmp_path, ending):
    case = _make_case(tmp_path, ending)
    _cache_round_trip(case).write()
    _assert_all_endings(_files(case), ending)


@pytest.mark.parametrize("ending", ENDING_PARAMS)
def test_edited_and_new_entries_get_the_source_ending(tmp_path, ending):
    case = _make_case(tmp_path, ending)
    c = pf.init(path=case)
    c.system.controlDict.endTime = 3000
    c.system.controlDict.brandNewEntry = 7
    c.write()
    data = (case / "system" / "controlDict").read_bytes()
    assert b"3000" in data and b"brandNewEntry" in data
    _assert_all_endings({"controlDict": data}, ending)


@pytest.mark.parametrize("ending", ENDING_PARAMS)
def test_edited_entry_after_cache_round_trip_gets_the_source_ending(tmp_path, ending):
    case = _make_case(tmp_path, ending)
    c = _cache_round_trip(case)
    c.system.controlDict.endTime = 3000
    c.write()
    data = (case / "system" / "controlDict").read_bytes()
    assert b"3000" in data
    _assert_all_endings({"controlDict": data}, ending)


@pytest.mark.parametrize("ending", ["LF", "CRLF"])
def test_write_never_doubles_the_carriage_return(tmp_path, ending):
    """Pins the T-020a interaction: the ending is applied once, never `\r\r\n`."""
    case = _make_case(tmp_path, ending)
    c = pf.init(path=case)
    c.system.controlDict.endTime = 3000
    c.write()
    assert all(b"\r\r" not in d for d in _files(case).values())


def test_new_file_is_written_with_lf(tmp_path):
    case = _make_case(tmp_path, "CRLF")
    c = pf.init(path=case)
    new = fkt.ofDictFile(name="extraDict")
    new.foo = 1
    c.system.extraDict = new
    c.write()
    data = (case / "system" / "extraDict").read_bytes()
    assert b"foo" in data
    _assert_all_endings({"extraDict": data}, "LF")


def test_mixed_endings_raise_foamkiterror_naming_file_and_line(tmp_path):
    case = _make_case(tmp_path, "LF")
    target = case / "system" / "controlDict"
    lines = target.read_bytes().split(b"\n")
    lines[3] += b"\r"  # line 4 ends CRLF, line 1 ends LF
    mixed = b"\n".join(lines)
    target.write_bytes(mixed)
    case_obj = pf.init(path=case)
    case_obj.system.controlDict.endTime = 3000
    # - Not `pytest.raises`: its failure is not an AssertionError (strict xfail `raises`).
    try:
        case_obj.write()
    except FoamKitError as e:
        msg = str(e)
    else:
        raise AssertionError("write() of a mixed-ending file raised no FoamKitError")
    assert "controlDict" in msg
    assert re.search(r"\b4\b", msg), msg
    assert target.read_bytes() == mixed  # the mixed file is not written


def test_mixed_file_leaves_every_other_file_and_the_cache_untouched(tmp_path):
    case = _make_case(tmp_path, "LF")
    target = case / "system" / "fvSchemes"
    lines = target.read_bytes().split(LF)
    lines[3] += CR  # line 4 ends CRLF, line 1 ends LF
    target.write_bytes(LF.join(lines))
    before = _files(case)
    case_obj = pf.init(path=case)
    case_obj.system.controlDict.endTime = 3000
    with pytest.raises(FoamKitError, match="fvSchemes"):
        case_obj.write()
    assert _files(case) == before
    assert not (case / ".params").exists()  # no cache save or backup either


def _edit_cache(case, edit):
    """Apply `edit(key, parent_dict)` to every `_newline` / `_mixedLine` in the cache."""
    path = case / ".params" / "_case.json"
    data = json.loads(path.read_text())

    def walk(o):
        if isinstance(o, dict):
            for key in list(o):
                if key in ("_newline", "_mixedLine"):
                    edit(key, o)
                walk(o[key] if key in o else None)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    path.write_text(json.dumps(data))


def test_old_cache_without_line_ending_keys_loads_and_writes_lf(tmp_path):
    case = _make_case(tmp_path, "LF")
    pf.init(path=case).save(path=case)
    _edit_cache(case, lambda key, d: d.pop(key))
    loaded = pf.load(path=case)
    assert loaded.system.controlDict._newline == "\n"
    loaded.system.controlDict.endTime = 3000
    loaded.write()
    data = (case / "system" / "controlDict").read_bytes()
    assert b"3000" in data
    _assert_all_endings({"controlDict": data}, "LF")


def test_cache_holding_a_mixed_line_still_errors_after_load(tmp_path):
    case = _make_case(tmp_path, "LF")
    pf.init(path=case).save(path=case)
    _edit_cache(
        case, lambda key, d: d.update(_mixedLine=4) if key == "_mixedLine" else None
    )
    loaded = pf.load(path=case)
    before = _files(case)
    with pytest.raises(FoamKitError, match=r":4\b"):
        loaded.write()
    assert _files(case) == before
