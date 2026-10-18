"""Regression tests for fixed bugs (each test failed before its fix)."""
import os
import shutil
import stat
import sys
import threading

import pytest

import foamkit
import foamkit.functions as fkf
import foamkit.types as fkt
from conftest import FIXTURES

HEADER = (FIXTURES / "pitzDaily" / "system" / "controlDict").read_text().split("application")[0]


def _parse(tmp_path, body, name="testDict"):
    path = tmp_path / name
    path.write_text(HEADER + body)
    return fkt.DictFileParser(path).readDictFile()


def _rewrite(tmp_path, dictFile, name="rewritten"):
    path = tmp_path / name
    path.write_text(dictFile.toString())
    return fkt.DictFileParser(path).readDictFile()


def test_large_dictionary_parses(tmp_path):
    """Files with more than 5000 top-level lines used to exit silently."""
    n = 3000
    d = _parse(tmp_path, "".join(f"value{i}  {i}.5;\n\n" for i in range(n)))
    assert d.value2999.value == 2999.5


def test_named_function_entry_keeps_its_name(tmp_path):
    """`halfX #eval{...};` was written back as `eval0 #eval{...};`."""
    d = _parse(tmp_path, "nx 10;\n\nhalfX #eval{ $nx / 2 };\n")
    assert "halfX" in vars(d)
    assert "halfX" in d.toString() and "eval0" not in d.toString()


@pytest.mark.parametrize("entry, bracket", [
    ('x #eval "2 * $nx";', '"'),
    ("x #eval{ 2 * $nx };", "{"),
    ("x #eval { 2 * $nx };", "{"),
])
def test_eval_bracket_style_round_trips(tmp_path, entry, bracket):
    d = _parse(tmp_path, f"nx 10;\n\n{entry}\n")
    assert d.x.value == "2 * $nx"
    assert d.x.vBracketType == {'"': 0, "{": 1}[bracket]
    assert d.x.feType == "eval"
    again = _rewrite(tmp_path, d)
    assert again.x.value == "2 * $nx"
    assert again.toString() == d.toString()


def test_multiline_scalar_table(tmp_path):
    d = _parse(tmp_path, "t table\n(\n    (0 0)\n    (1 10)\n);\n")
    assert isinstance(d.t, fkt.ofTable)
    assert d.t.value.loc[1, 0] == 10


def test_vector_table_round_trips(tmp_path):
    """Vector tables crashed, or were mistaken for a bounding box."""
    d = _parse(tmp_path, "U table ((0 (0 0 0)) (1 (10 0 0)));\n")
    assert isinstance(d.U, fkt.ofTable)
    assert list(d.U.value.loc[1]) == [10, 0, 0]
    again = _rewrite(tmp_path, d)
    assert again.toString() == d.toString()
    assert "(1     (10 0 0))" in d.toString()


def test_bound_box_still_detected(tmp_path):
    d = _parse(tmp_path, "box (0 0 0) (1 2 3);\n")
    assert isinstance(d.box, fkt.ofBoundBox)
    assert d.box.value == [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]]


def test_lone_keyword_round_trips(tmp_path):
    """`grad(U);` was written as `grad(U)     ;`, which failed to re-parse."""
    d = _parse(tmp_path, "cache\n{\n    grad(U);\n}\n")
    assert "grad(U);" in d.toString()
    _rewrite(tmp_path, d)
    #- files written by older versions are still readable
    old = _parse(tmp_path, "cache\n{\n    grad(U)     ; \n}\n", name="old")
    assert "grad(U);" in old.toString()


def test_verbatim_code_is_stable(tmp_path):
    """Coded function object code gained indentation/blank lines per write."""
    body = ("functions\n{\n    coded1\n    {\n        type coded;\n"
            "        codeExecute\n        #{\n            Info<< 1 << endl;\n"
            "            if (true)\n            {\n                Info<< 2;\n"
            "            }\n        #};\n    }\n}\n")
    d = _parse(tmp_path, body)
    code = [v for k, v in vars(d.functions.coded1).items()
            if isinstance(v, fkt.ofCodeExecute)][0]
    assert code.value == "Info<< 1 << endl;\nif (true)\n{\n    Info<< 2;\n}"
    text = d.toString()
    for i in range(3):
        d = _rewrite(tmp_path, d, name=f"r{i}")
        assert d.toString() == text


def test_del_entry_and_clear(tmp_path):
    d = _parse(tmp_path, "a 1;\n\nb 2;\n")
    del d.a
    assert "a" not in vars(d) and "a " not in d.toString().split("// * *")[1]
    d.clear()
    assert "b " not in d.toString().split("// * *")[1]
    assert d._foamFile is not None


def test_clean_returns_cleared_copy(tmp_path, capsys):
    d = _parse(tmp_path, "a 1;\n\nb 2;\n")
    cleaned = fkf.clean(d)
    assert d.b.value == 2
    assert "b" not in vars(cleaned)
    assert capsys.readouterr().out == ""


def test_parser_errors_are_reported(tmp_path, capsys):
    """Parser failures used to `sys.exit()` with status 0 and no message."""
    path = tmp_path / "broken"
    path.write_text("no header here\n")
    with pytest.raises(foamkit.FoamKitError) as err:
        fkt.DictFileParser(path).readDictFile()
    assert err.value.code == 1
    assert "Invalid OpenFOAM file" in capsys.readouterr().out


def test_isMeshed(case):
    assert fkf.isMeshed(case) is False
    mesh = case / "constant" / "polyMesh"
    mesh.mkdir()
    for f in ("points", "faces", "owner", "neighbour", "boundary"):
        (mesh / f).write_text("")
    assert fkf.isMeshed(case) is True


def test_isDecomposed_isReconstructed(case):
    assert fkf.isDecomposed(case) is False
    assert fkf.isReconstructed(case) is True
    (case / "processor0" / "0").mkdir(parents=True)
    (case / "processor0" / "100").mkdir()
    assert fkf.isDecomposed(case) is True
    assert fkf.isReconstructed(case) is False


def test_cloneCase_local_path_with_spaces(case, tmp_path):
    (case / "100").mkdir()                       # results: not copied
    (case / "postProcessing" / "probes").exists()
    dest = tmp_path / "my clone"
    fkf.cloneCase(case, dest)
    assert (dest / "system" / "controlDict").is_file()
    assert (dest / "0" / "U").is_file()
    assert not (dest / "100").exists()
    assert not (dest / "postProcessing").exists()


def test_cloneCase_remote_source_is_an_error(case, tmp_path):
    with pytest.raises(foamkit.FoamKitError):
        fkf.cloneCase(case, tmp_path / "x", sshSrc="user@host")


def test_cloneCases_accepts_path_objects(case, tmp_path):
    src = case.parent
    (src / ".params").mkdir()
    (src / ".params" / "study.json").write_text("{}")
    dest = tmp_path / "dest"
    fkf.cloneCases(src, dest)
    assert (dest / "pitzDaily" / "system" / "controlDict").is_file()
    assert (dest / ".params" / "study.json").is_file()


def test_extractLogData_with_labels(case):
    (case / "log.checkMesh").write_text("    cells:            12225\n")
    found, paths = fkf.extractLogData("log.checkMesh", "cells:            {}",
                                     logFileLabels=True, path=str(case))
    assert found == ["12225"]
    assert paths == [case / "log.checkMesh"]


def test_readInputs_builds_one_unit_registry(monkeypatch):
    import pint
    import importlib
    _unitDecoder = importlib.import_module("foamkit.functions._unitDecoder")
    _unitDecoder._unitRegistry.cache_clear()
    created = []
    original = pint.UnitRegistry
    monkeypatch.setattr(pint, "UnitRegistry",
                        lambda *a, **k: created.append(1) or original(*a, **k))
    params = fkf.readInputs(str(FIXTURES.parent.parent / "templates" / "test" /
                               "of.test" / "inputParameters"))
    assert len(params) > 10
    assert len(created) == 1


@pytest.mark.skipif(sys.platform == "win32", reason="needs an executable shell script")
def test_allRun_with_large_output_does_not_deadlock(case):
    script = case / "Allrun"
    script.write_text("#!/bin/sh\nhead -c 2000000 /dev/zero | tr '\\0' 'x'\n"
                      "head -c 2000000 /dev/zero | tr '\\0' 'y' >&2\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    c = fkt.CaseParser(case).initOFCase()
    t = threading.Thread(target=c.allRun, daemon=True)
    t.start()
    t.join(30)
    assert not t.is_alive(), "allRun deadlocked on a full pipe"


def test_matplotlib_not_imported_by_package():
    import subprocess
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys, foamkit.functions; print('matplotlib' in sys.modules, 'pint' in sys.modules)"],
        capture_output=True, text=True, check=True, cwd=str(FIXTURES.parent.parent))
    assert out.stdout.split() == ["False", "False"]
