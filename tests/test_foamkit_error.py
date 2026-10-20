"""
`FoamKitError` is a standard `Exception` during a one-release transition
(T-017): it keeps `SystemExit` as a second base, and the library no longer
ends the process with `sys.exit()` on error paths.
"""

import ast
from pathlib import Path

import pytest

import foamkit
import foamkit.types as fkt
from foamkit import FoamKitError, userMsg
from foamkit.functions import dictUtil
from foamkit.functions.readDict import readDict

PKG = Path(foamkit.__file__).parent
NOT_FOAM = "/* some other tool */\nkey value;\n"


# --- class layout -------------------------------------------------------


def test_foamkit_error_is_an_exception_subclass():
    assert issubclass(FoamKitError, Exception)


def test_foamkit_error_is_still_a_systemexit_subclass_during_transition():
    assert issubclass(FoamKitError, SystemExit)


def test_userMsg_error_is_caught_by_except_exception(capsys):
    with pytest.raises(Exception) as err:
        userMsg("x", "ERROR")
    assert isinstance(err.value, FoamKitError)


def test_userMsg_error_instance_is_both_exception_and_systemexit(capsys):
    with pytest.raises(FoamKitError) as err:
        userMsg("x", "ERROR")
    assert isinstance(err.value, Exception)
    assert isinstance(err.value, SystemExit)


def test_except_systemexit_still_catches_with_code_preserved(capsys):
    with pytest.raises(SystemExit) as err:
        userMsg("x", "ERROR")
    assert err.value.code == 1
    assert str(err.value) == "x"
    assert err.value.msg == "x"


def test_direct_construction_keeps_msg_code_and_str():
    e = FoamKitError("boom")
    assert (e.code, e.msg, str(e)) == (1, "boom", "boom")


def test_foamkit_error_without_message_still_constructs():
    assert FoamKitError().code == 1


def test_foamkit_error_docstring_announces_systemexit_base_removal():
    doc = " ".join(FoamKitError.__doc__.split())
    assert "SystemExit" in doc
    assert "removed" in doc and "next" in doc


def test_malformed_file_error_is_caught_by_except_exception(tmp_path):
    """A malformed file raises through the normal parser path."""
    path = tmp_path / "bad"
    path.write_text("FoamFile\n\n\n")
    with pytest.raises(Exception) as err:
        fkt.DictFileParser(path).readDictFile()
    assert isinstance(err.value, FoamKitError)


# --- library sys.exit() paths converted ----------------------------------


def test_findEndOfHeader_on_file_without_header_raises_foamkit_error(tmp_path):
    path = tmp_path / "noHeader"
    path.write_text("just some text\n")
    with pytest.raises(FoamKitError):
        dictUtil._findEndOfHeader(str(path))


def test_findEndOfDict_on_empty_file_raises_foamkit_error(tmp_path):
    """Same path, reached through `_findEndOfDict`."""
    path = tmp_path / "empty"
    path.write_text("")
    with pytest.raises(FoamKitError):
        dictUtil._findEndOfDict(str(path))


def test_readDict_on_non_openfoam_file_raises_foamkit_error(tmp_path):
    path = tmp_path / "notFoam"
    path.write_text(NOT_FOAM)
    with pytest.raises(FoamKitError):
        readDict(str(path))


def test_readDict_failure_is_catchable_with_except_exception(tmp_path):
    path = tmp_path / "notFoam"
    path.write_text(NOT_FOAM)
    with pytest.raises(Exception) as err:
        readDict(str(path))
    assert isinstance(err.value, FoamKitError)


# - `_interpretUnitsAndConvert` cannot reach its `sys.exit()` at runtime: it
#  fails earlier with NameError (`UnitRegistry` is never imported) and the
#  branch sits in a closure whose callers use a different signature.  The
#  conversion is therefore checked on the source.
@pytest.mark.parametrize(
    "relpath",
    [
        "functions/dictUtil.py",
        "functions/readDict.py",
        "functions/_interpretUnitsAndConvert.py",
        "functions/load.py",
    ],
)
def test_library_module_does_not_call_sys_exit(relpath):
    tree = ast.parse((PKG / relpath).read_text(encoding="utf-8"))
    calls = [
        n.lineno
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and ast.unparse(n.func) in ("sys.exit", "exit", "quit")
    ]
    assert calls == [], f"sys.exit() still called at lines {calls}"


# --- converted errors must not be swallowed by a bare `except:` -----------


def _bareExceptCallers(path, names):
    """Calls to `names` made inside a `try` that has a bare `except:`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits = []
    for t in ast.walk(tree):
        if isinstance(t, ast.Try) and any(h.type is None for h in t.handlers):
            for stmt in t.body:
                for n in ast.walk(stmt):
                    if isinstance(n, ast.Call) and getattr(n.func, "id", None) in names:
                        hits.append((path.name, n.lineno))
    return hits


def test_callers_of_converted_paths_are_not_inside_bare_except():
    names = {
        "_findEndOfHeader",
        "_findEndOfDict",
        "readDict",
        "_interpretUnitsAndConvert",
    }
    hits = []
    for p in (PKG / "functions").glob("*.py"):
        hits += _bareExceptCallers(p, names)
    assert hits == []
