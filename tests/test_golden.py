"""Characterization tests: parsed dictionaries must print exactly as before."""
from pathlib import Path

import pytest

import foamkit.functions as pf
import foamkit.types as pt
from conftest import FIXTURES, REPO, assert_golden

DICT_FILES = sorted(
    p for p in FIXTURES.rglob("*")
    if p.is_file() and "postProcessing" not in p.parts
) + [REPO / "templates" / name for name in
     ("fvSolution", "fvSchemes.orig", "fvSchemes.robust")] + [
    REPO / "templates" / "test" / "of.test" / rel for rel in
    ("system/controlDict", "system/controlDict.test", "constant/transportProperties",
     "0.orig/U.orig")]


def _id(path):
    for root in (FIXTURES, REPO / "templates"):
        if root in path.parents:
            return path.relative_to(root).as_posix()
    return path.name


@pytest.mark.parametrize("path", DICT_FILES, ids=_id)
def test_dict_file_to_string(path):
    assert pf.isDictFile(path)
    dictFile = pt.DictFileParser(path).readDictFile()
    assert_golden(f"dicts/{_id(path)}.txt", dictFile.toString())


@pytest.mark.parametrize("path", DICT_FILES, ids=_id)
def test_repeated_writes_converge(path, tmp_path):
    """
    Written files can be read back, and repeated read/write cycles reach a
    fixed point, so `pf write` never degrades a file over time.  The first
    two rewrites may still normalize formatting (e.g. a one-line list such as
    `libs ("lib.so");` becoming a multi-line list).
    """
    texts = []
    src = path
    for i in range(4):
        texts.append(pt.DictFileParser(src).readDictFile().toString())
        src = tmp_path / f"{path.name}.{i}"
        src.write_text(texts[-1])
    assert texts[3] == texts[2]
