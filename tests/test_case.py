"""Case-level behaviour: init -> save (JSON cache) -> load -> edit -> write."""
import copy
import json

import pytest

import foamkit
import foamkit.functions as pf
import foamkit.types as pt
from conftest import assert_golden

DICT_FILES = [("system", "controlDict"), ("system", "fvSchemes"),
              ("system", "fvSolution"), ("system", "blockMeshDict"),
              ("constant", "transportProperties"), ("t_0", "U"), ("t_0", "p")]


def test_init_parses_case_folders(case):
    c = pf.init(path=case)
    assert type(c).__name__ == "ofCase"
    assert c._name == "pitzDaily"
    assert c.system.controlDict.endTime.value == 2000
    assert c.constant.momentumTransport.RAS.model.value == "kEpsilon"
    assert c.t_0.U.internalField.value.value == [0, 0, 0]
    #- postProcessing is not part of the case model
    assert not hasattr(c, "postProcessing")


def test_save_load_round_trip(case):
    c = pf.init(path=case)
    c.save(path=case)
    assert (case / ".params" / "_case.json").is_file()

    loaded = pf.load(path=case)
    for folder, name in DICT_FILES:
        assert loaded[folder][name].toString() == c[folder][name].toString()


def test_load_does_not_reparse_case(case, monkeypatch):
    """`load` builds the case from the JSON cache only."""
    pf.init(path=case).save(path=case)

    parsed = []
    original = pt.FolderParser.makeOFFolder
    monkeypatch.setattr(pt.FolderParser, "makeOFFolder",
                        lambda self: parsed.append(self.path) or original(self))
    loaded = pf.load(path=case)
    assert parsed == []
    assert loaded.system.controlDict.endTime.value == 2000


def test_load_without_cache_warns_and_returns_none(case, capsys):
    assert pf.load(path=case) is None
    assert "No cached case data found" in capsys.readouterr().out


def test_edit_and_write(case):
    pf.init(path=case).save(path=case)
    c = pf.load(path=case)
    c.system.controlDict.endTime = 500
    c.write()

    written = (case / "system" / "controlDict").read_text()
    assert_golden("case/controlDict.written.txt", written)
    assert pt.DictFileParser(case / "system" / "controlDict").readDictFile() \
        .endTime.value == 500
    #- The previous cache is kept as a backup
    assert (case / ".params" / "_case.backup0").is_file()


def test_restore_from_backup(case, chdir):
    chdir(case)
    pf.init(path=case).save(path=case)
    c = pf.load(path=case)
    c.write()                                   # backup0 = endTime 2000
    c.system.controlDict.endTime = 1
    c.save(path=case)

    restored = pf.restore()
    assert restored.system.controlDict.endTime.value == 2000
    assert not (case / ".params" / "_case.backup0").exists()


def test_restore_without_backup_is_an_error(case, chdir):
    chdir(case)
    with pytest.raises(foamkit.FoamKitError):
        pf.restore()


def test_deepcopy_is_independent(case):
    c = pf.init(path=case)
    c2 = copy.deepcopy(c)
    assert type(c2).__name__ == "ofCase"
    assert c2._path == c._path
    assert c2.system.controlDict.toString() == c.system.controlDict.toString()

    c2.system.controlDict.endTime = 1
    assert c.system.controlDict.endTime.value == 2000
    assert c2.system._path == c.system._path


def test_deepcopy_prints_nothing(case, capsys):
    copy.deepcopy(pf.init(path=case))
    assert capsys.readouterr().out == ""


def test_initOFCase_does_not_parse(case):
    c = pt.CaseParser(case).initOFCase()
    assert vars(c.system).keys() == {"_path", "_type"}
    assert vars(c.constant).keys() == {"_path", "_type"}


def test_defaults_follow_working_directory(case, chdir, tmp_path):
    """Default paths are resolved at call time, not import time."""
    chdir(case)
    assert pf.isCase()
    c = pf.init()
    assert c._path == case.resolve()
    chdir(tmp_path)
    assert not pf.isCase()


def test_json_cache_is_valid_json(case):
    pf.init(path=case).save(path=case)
    data = json.loads((case / ".params" / "_case.json").read_text())
    assert data["_type"] == "ofCase"
    assert data["system"]["controlDict"]["_type"] == "ofDictFile"
