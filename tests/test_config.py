"""FoamKit configuration lookup."""
import os
import time

import pytest

import foamkit
from foamkit import getFoamKitConfig


@pytest.fixture
def isolatedConfig(tmp_path, monkeypatch):
    """Point the user/package config paths at empty temp locations."""
    monkeypatch.setattr(foamkit, "USER_CONFIG", tmp_path / "user" / "config.ini")
    monkeypatch.setattr(foamkit, "LEGACY_USER_CONFIG", tmp_path / "legacy" / "config.ini")
    monkeypatch.setattr(foamkit, "PACKAGE_CONFIG", tmp_path / "pkg" / "config.ini")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    #- make sure the mtime changes even on coarse-grained filesystems
    stamp = time.time() + 10 * len(text)
    os.utime(path, (stamp, stamp))


def test_defaults_when_no_config(isolatedConfig):
    assert getFoamKitConfig("debug") is False
    assert getFoamKitConfig("dict_filesize_limit") == 10000000
    assert getFoamKitConfig("unknown_key") is None


def test_values_are_typed(isolatedConfig):
    """'False' in a config file must not be truthy."""
    _write(foamkit.PACKAGE_CONFIG,
           "[default]\ndebug = False\ndict_filesize_limit = 123\nother = x\n")
    assert getFoamKitConfig("debug") is False
    assert getFoamKitConfig("dict_filesize_limit") == 123
    assert getFoamKitConfig("other") == "x"


def test_precedence(isolatedConfig):
    _write(foamkit.PACKAGE_CONFIG, "[default]\ndebug = False\n")
    _write(foamkit.USER_CONFIG, "[default]\ndebug = True\n")
    assert getFoamKitConfig("debug") is True
    _write(isolatedConfig / ".params" / "config.ini", "[user]\ndebug = no\n")
    assert getFoamKitConfig("debug") is False


def test_user_section_overrides_default(isolatedConfig):
    _write(foamkit.USER_CONFIG, "[default]\ndebug = False\n[user]\ndebug = on\n")
    assert getFoamKitConfig("debug") is True


def test_changes_are_picked_up(isolatedConfig):
    _write(foamkit.USER_CONFIG, "[default]\ndict_filesize_limit = 1\n")
    assert getFoamKitConfig("dict_filesize_limit") == 1
    _write(foamkit.USER_CONFIG, "[default]\ndict_filesize_limit = 22\n")
    assert getFoamKitConfig("dict_filesize_limit") == 22


def test_package_config_is_found():
    """The shipped config.ini is read (it was never found on Windows)."""
    assert foamkit.PACKAGE_CONFIG.is_file()
    assert foamkit.PACKAGE_CONFIG in foamkit.configSearchPaths()


def test_userMsg_error_raises(capsys):
    with pytest.raises(foamkit.FoamKitError) as err:
        foamkit.userMsg("boom", "ERROR")
    assert err.value.code == 1
    assert isinstance(err.value, SystemExit)
    assert "boom" in capsys.readouterr().out
