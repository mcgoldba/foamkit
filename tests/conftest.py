"""
Shared fixtures.

Golden files (`tests/golden/`) record the exact output of the parser and
writers.  After an intentional output change, regenerate them with:

    FOAMKIT_UPDATE_GOLDEN=1 python -m pytest

and review the diff before committing.
"""
import os
import shutil
from pathlib import Path

import pytest

TESTS = Path(__file__).parent
FIXTURES = TESTS / "fixtures"
GOLDEN = TESTS / "golden"
REPO = TESTS.parent

UPDATE_GOLDEN = os.environ.get("FOAMKIT_UPDATE_GOLDEN") == "1"


@pytest.fixture
def case(tmp_path):
    """A writable copy of the pitzDaily fixture case."""
    path = tmp_path / "pitzDaily"
    shutil.copytree(FIXTURES / "pitzDaily", path)
    return path


@pytest.fixture
def chdir(monkeypatch):
    """Change the working directory for the duration of a test."""
    def _chdir(path):
        monkeypatch.chdir(path)
        return path
    return _chdir


def assert_golden(name, text):
    """Compare `text` with `tests/golden/<name>` (or write it when updating)."""
    path = GOLDEN / name
    if UPDATE_GOLDEN:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return
    assert path.is_file(), f"Missing golden file {path}; run with FOAMKIT_UPDATE_GOLDEN=1"
    expected = path.read_text(encoding="utf-8")
    assert text.replace("\r\n", "\n") == expected, f"Output differs from {path}"
