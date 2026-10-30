"""One-line `{ ... }` blocks: sub-dicts and lists of dicts (T-040, absorbs T-022).

Specification tests for docs/tickets/T-040-one-line-list-of-dicts.md (issue #54).

Every parse runs in a child process (tests/probe_runner.py), so a hang fails a test
instead of stalling the suite.  All inputs run in ONE child (interpreter start and the
pandas import are slow here); the parent is the watchdog: a case that exceeds its limit
(4 s; 8-9 s for the real files and the 10^4-item list; never more than 10 s) gets the
child killed, is reported as status "hang", and the rest run in a fresh child.

The T-040 xfail markers were removed when the fix landed.  The tests marked "T-020" (a
byte-identical write of an unedited one-line block) stay strict xfails: the block is
written multi-line with every entry kept, which the sibling tests (`..._keeps_every_entry`,
`..._write_1_equals_...`) pin.  The table below is the behaviour BEFORE the fix.

Outcome of each input on this branch (after T-041), recorded when these tests were
written.  e = FoamKitError "... one-line '{ ... }' blocks with several entries are not
supported yet (T-040)"; "empty" = loads without error and the content is silently lost:

    x ( a { v 1; } b { v 2; } );            e
    x ( { v 1; } );  x ( a { v 1; } );      empty list
    x ( a { b { v 1; } } );  x ( { } );     empty list
    x ( { v 1; } { v 2; } );                e
    x ( { v 0; } ... { v 9999; } );         e, fast (no hang)
    x
(
    a { v 1; }
);                [empty dict]
    x
(
    { v 1; }
    { v 2; }
);    ["v 1", "v 2"] (strings, not dicts)
    x
(
    a { v 1; }
    b { v 2; }
);  HANG (killed at the limit)
    p { type probes; }                      loads, p is EMPTY (also after #include)
    p { type probes; }  in functions { }    e
    sub { b 2; }  then z 3; y 4;            sub EMPTY, z and y kept
    a { b { c 1; } }  /  p {type probes;}   empty dicts
    p { type probes;  (unterminated)        IndexError, not FoamKitError
    rotorDisk / heatedDuct snappyHexMeshDict   HANG
    pf.init with a one-line block           FoamKitError (several entries)

Real files (byte-exact copies in tests/releases/, which is outside the golden glob).
Each was verified by `git hash-object` against the blob of the OpenFOAM-11 clone at
9cbf94f (the clones check out CRLF; these bytes are the LF raw download):
- foundation-11.rotorDisk.snappyHexMeshDict, blob cb34af345d5f40a3e469927ece3ede3a029164d6:
  https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-11/9cbf94f/tutorials/incompressibleFluid/rotorDisk/system/snappyHexMeshDict
- foundation-11.heatedDuct.snappyHexMeshDict, blob af568a04f2a88d7f4fd1dce4d6b74352436cdd1e:
  https://raw.githubusercontent.com/OpenFOAM/OpenFOAM-11/9cbf94f/tutorials/multiRegion/CHT/heatedDuct/system/snappyHexMeshDict
"""

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading

import pytest

from conftest import FIXTURES, REPO, TESTS
from test_directives import HEADER

NL = "\n"
HL = HEADER.count(NL)
RELEASES = TESTS / "releases"
RUNNER = TESTS / "probe_runner.py"
ROTOR = RELEASES / "foundation-11.rotorDisk.snappyHexMeshDict"
DUCT = RELEASES / "foundation-11.heatedDuct.snappyHexMeshDict"
FILE = (
    "probeDict"  # a letters-only file name, so line numbers in messages are unambiguous
)
XF_LAYOUT = pytest.mark.xfail(
    strict=True,
    reason="T-020: an unedited one-line block written back byte-identical needs "
    "T-020's source text (T-040 only has to keep every entry)",
)

# --- running a group of inputs in a child process ---------------------------------------


def _start(specs, cwd):
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join([str(REPO), os.environ.get("PYTHONPATH", "")]),
    )
    proc = subprocess.Popen(
        [sys.executable, str(RUNNER), str(specs)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
        cwd=cwd,
    )
    lines = queue.Queue()

    def pump():
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    return proc, lines


def probe(cases, tmp_path):
    """Run `cases` ({label: spec}) in child processes.  Return {label: result dict}.

    The parent is the watchdog: a case that takes longer than its `limit` seconds
    (at most 10) gets the child killed and is reported as status "hang"; the remaining
    cases then run in a fresh child.  Each child gets 60 s to import foamkit.
    """
    results = {}
    todo = dict(cases)
    n = 0
    while todo:
        n += 1
        specs = (tmp_path / f"specs{'abcdefghij'[n % 10]}.json").resolve()
        specs.write_text(json.dumps(todo))
        proc, lines = _start(specs, tmp_path)
        wait = 60.0
        try:
            for label, spec in todo.items():
                while True:
                    try:
                        line = lines.get(timeout=wait)
                    except queue.Empty:
                        line = ""
                    if line is None or line == "":
                        break
                    res = json.loads(line)
                    if res.get("ready"):
                        wait = min(spec.get("limit", 5.0), 10.0)
                        continue
                    break
                if not line:
                    reason = "killed" if line == "" else "child exited early"
                    results[label] = {"label": label, "status": "hang", "stage": reason}
                    break
                results[label] = res
                nxt = list(todo).index(label) + 1
                if nxt < len(todo):
                    wait = min(list(todo.values())[nxt].get("limit", 5.0), 10.0)
        finally:
            proc.kill()
            proc.wait()
        todo = {k: v for k, v in cases.items() if k not in results}
        if (
            n > len(cases) + 1
        ):  # pragma: no cover - cannot happen, but never loop forever
            break
    return results


def doc(body):
    return HEADER + body + NL


def case(body, limit=4.0, header=True):
    return {"text": doc(body) if header else body, "name": FILE, "limit": limit}


def loaded(res):
    """The result of a clean read/write/read/write cycle, else fail with the outcome."""
    detail = (
        f"{res['status']} in {res.get('stage')}: {res.get('etype')} {res.get('msg')}"
    )
    assert res["status"] == "ok", f"{res['label']}: {detail}"
    return res


def failed(res):
    assert res["status"] == "error", f"{res['label']}: expected FoamKitError, got {res}"
    return res


def line_of(msg, n):
    return re.search(rf"\bline {n}\b", msg, re.IGNORECASE)


def tree(res, n=1):
    return loaded(res)[f"tree{n}"]


def cycles_agree(res):
    """Write 1 == write 2 == write 3 and every re-read has the tree of the first read."""
    r = loaded(res)
    assert r["w1"] == r["w2"] == r["w3"]
    assert r["tree1"] == r["tree2"] == r["tree3"]


# --- the inputs -----------------------------------------------------------------------------
# - Labels are prefixed by group; ALL of them run in ONE probe() call (module fixture
# - `res`), so a green run costs one interpreter start.  A hang costs a restart.

BIG = 10_000
BIG_LIST = "x ( " + " ".join(f"{{ v {i}; }}" for i in range(BIG)) + " );"
LISTS = {
    "two_named": ("x ( a { v 1; } b { v 2; } );", [{"v": 1}, {"v": 2}]),
    "one_anonymous": ("x ( { v 1; } );", [{"v": 1}]),
    "one_named": ("x ( a { v 1; } );", [{"v": 1}]),
    "nested": ("x ( a { b { v 1; } } );", [{"b": {"v": 1}}]),
    "several_entries": ("x ( { v 1; w 2; } );", [{"v": 1, "w": 2}]),
    "empty_item": ("x ( { } );", [{}]),
    "two_anonymous": ("x ( { v 1; } { v 2; } );", [{"v": 1}, {"v": 2}]),
    "multi_line_named": ("x\n(\n    a { v 1; }\n);", [{"v": 1}]),
    "multi_line_anonymous": (
        "x\n(\n    { v 1; }\n    { v 2; }\n);",
        [{"v": 1}, {"v": 2}],
    ),
    "multi_line_named_two": (
        "x\n(\n    a { v 1; }\n    b { v 2; }\n);",
        [{"v": 1}, {"v": 2}],
    ),
    "trailing_comment": ("x ( { v 1; } ); // two", [{"v": 1}]),
    "brace_in_string": ('x ( { s "a}b"; } );', [{"s": '"a}b"'}]),
}
INCLUDE = '#include "other"'
SUB = {
    "top_level": ("p { type probes; }", {"p": {"type": "probes"}}),
    "in_functions": (
        "functions\n{\n    p { type probes; }\n}",
        {"functions": {"p": {"type": "probes"}}},
    ),
    "after_include": (
        INCLUDE + NL + "p { type probes; }",
        {"include0": "other", "p": {"type": "probes"}},
    ),
    "in_functions_after_include": (
        "functions\n{\n    " + INCLUDE + "\n    p { type probes; }\n}",
        {"functions": {"unnamed_1": "other", "p": {"type": "probes"}}},
    ),
    "several_entries": (
        "p { type probes; fields (p U); }",
        {"p": {"type": "probes", "fields": ["p", "U"]}},
    ),
    "nested": ("a { b { c 1; } }", {"a": {"b": {"c": 1}}}),
    "spaced_foundation_11": (
        "g { f10 { dSph 10e-3; value 0.0; } }",
        {"g": {"f10": {"dSph": 10e-3, "value": 0.0}}},
    ),
    "then_entry": ("d { a 1; } e 2;", {"d": {"a": 1}, "e": 2}),
    "entry_then": ("e 2; d { a 1; }", {"e": 2, "d": {"a": 1}}),
    "alone_then_entries": (
        "sub { b 2; }\nz 3;\ny 4;",
        {"sub": {"b": 2}, "z": 3, "y": 4},
    ),
    "two_in_a_row": ("a { x 1; } b { y 2; }", {"a": {"x": 1}, "b": {"y": 2}}),
    "trailing_comment": ("p { type probes; } // note", {"p": {"type": "probes"}}),
    "brace_in_string": ('p { s "a}b"; t 2; }', {"p": {"s": '"a}b"', "t": 2}}),
    "no_inner_space": ("p {type probes;}", {"p": {"type": "probes"}}),
}
SUB_EMPTY = {
    "empty": ("p { }", {"p": {}}),
    "empty_then_entry": ("d { } e 2;", {"d": {}, "e": 2}),
}
WRITE = {
    "sub": (
        "p { type probes; fields (p U); }",
        {"p": {"type": "probes", "fields": ["p", "U"]}},
    ),
    "nested": ("a { b { c 1; } }", {"a": {"b": {"c": 1}}}),
    "list": ("x ( { v 1; } );", {"x": [{"v": 1}]}),
}
# - (body, line of the unterminated opener within the body, 1-based)
MALFORMED = {
    "only_line": ("p { type probes;", 1),
    "entries_around": ("a 1;\np { type probes;\nq 2;\nr 3;", 2),
    "list_item": ("x ( { v 1; );", 1),
    "nested_open": ("p { a { b 1; }", 1),
}
# - One-line `#{ ... #}` code blocks: they load today and must keep doing so.
CODE_BLOCKS = {
    "directive_code_in_subdict": (
        "d\n{\n    e\n    {\n        #fooBar #{ } #}\n        inner 2;\n    }\n    mid 3;\n}",
        ["d"],
    ),
    "directive_code_top": ("a 1;\n#fooBar #{ { #}\nb 2;", ["a", "b"]),
}
REAL = {"rotor": ROTOR, "duct": DUCT}
# - (body, line of the `origin` entry within the body, 1-based).  Full `#eval` support is
# - T-044; here the list must never load EMPTY (T-040 rewrites one-line `{ }` handling in
# - lists, and `#eval{ ... }` looks like one).
EVAL_LISTS = {
    "top_level": ("origin (#eval{0.5 * $S} 0 0);", 1),
    "top_level_spaced": ("origin (#eval {0.5 * $S} 0 0);", 1),
    "in_sub_dict": ("slab\n{\n    origin (#eval{0.5 * $S} 0 0);\n}", 3),
}
# - Pathological nesting (untrusted input): each is loaded or refused with FoamKitError,
# - never a RecursionError or a hang.
DEEP = 10_000
DEEP_INPUTS = {
    "braces": "a " + "{ b " * (DEEP - 1) + "{ c 1; " + "} " * DEEP,
    "list_items": "x " + "( { " * (DEEP // 2) + " } )" * (DEEP // 2) + ";",
    "lists": "x " + "( " * DEEP + ")" * DEEP + ";",
    "unclosed": "a " + "b { " * DEEP,
}
# - Uniform lists `N{value}` are values, not one-line blocks (review round 1): they loaded
# - and round-tripped before T-040 and must keep doing so.  Two are real ESI lines
# - (v2412/v2606 twoSimpleRotors and twoSquaresOutDomain fvSchemes).
UNIFORM = {
    "esi_searchBoxDivisions": "searchBoxDivisions  3{(64 64 1)};",
    "plain": "x 3{0};",
    "spaced": "x 3 {0};",
    "typed": "x List<scalar> 3{0.5};",
    "nonuniform": "value nonuniform List<scalar> 4{0};",
    "in_dict": "d\n{\n    x 3{0};\n    y 2;\n}",
    "in_one_line_block": "d { x 3{0}; y 2; }",
}
UNIFORM_TEXT = {
    "esi_searchBoxDivisions": "3{(64 64 1)}",
    "plain": "3{0}",
    "spaced": "3 {0}",
    "typed": "List<scalar> 3{0.5}",
    "nonuniform": "nonuniform List<scalar> 4{0}",
    "in_dict": "3{0}",
    "in_one_line_block": "3{0}",
}
# - `#eval{ }` / `#codeStream { }` in a list: refused only for a list that opens and closes
# - on one line (that used to load EMPTY); an item of a multi-line list loaded correctly
# - before T-040 (ESI filmPanel0 blockMeshDict) and must still load.
EVAL_MULTI_LINE = (
    "vertices\n(\n    (#eval{$xcore + $xside}  0   $zmin)\n    (1 2 3)\n);"
)
# - Comments right after the `{` must not hide the entry that follows (silent drop).
COMMENT_AFTER_BRACE = {
    "sub": ("p { /* c */ a 1; }", {"p": {"a": 1}}),
    "nested": ("p { q { /* c */ a 1; } }", {"p": {"q": {"a": 1}}}),
    "list_item": ("x ( a { /* c */ v 1; } );", {"x": [{"v": 1}]}),
    "multi_line": ("p { /* c */\n    a 1;\n}", {"p": {"a": 1}}),
}
# - Input a one-line block cannot hold yet: FoamKitError naming the line, never a
# - TypeError or a silent drop.
REFUSED_IN_BLOCK = {
    "include_then_entry": 'p { #include "f" a 1; }',
    "includeEtc_then_entry": 'p { #includeEtc "x" a 1; }',
    "two_includeFunc": "functions { #includeFunc residuals #includeFunc probes }",
    "semicolon_in_parens": "d { a (1;2); b 2; }",
    "keyword_before_foamfile": "x FoamFile { a 1; }",
}
INCLUDE_FUNC = {
    "args_on_two_lines": "#includeFunc foo(a,\n    b)\nz 1;",
    "args_open_paren_on_next_line": "#includeFunc foo\n(a, b)\nz 1;",
}


def _case_dir(tmp_path_factory):
    """A copy of the pitzDaily case whose controlDict has one-line sub-dicts."""
    case_dir = tmp_path_factory.mktemp("case") / "pitzDaily"
    shutil.copytree(FIXTURES / "pitzDaily", case_dir)
    ctrl = case_dir / "system" / "controlDict"
    text = ctrl.read_text()
    assert "functions\n{\n" in text  # guard: the fixture still has the block
    text = text.replace(
        "functions\n{\n",
        "functions\n{\n    oneLine { type probes; fields (p U); }\n",
        1,
    )
    ctrl.write_text(text + "\ntopProbe { type probes; }\n")
    return case_dir


def _real_spec(path):
    return {"text": path.read_text(), "name": "snappyHexMeshDict", "limit": 8.0}


@pytest.fixture(scope="module")
def res(tmp_path_factory):
    cases = {}
    for k, (body, _) in LISTS.items():
        cases[f"list:{k}"] = case(body)
    cases["list:big"] = case(BIG_LIST, limit=9.0)
    cases["list:big"]["cycles"] = (
        1  # one read+write: three would exceed 9 s on Python 3.9
    )
    for k, (body, _) in {**SUB, **SUB_EMPTY}.items():
        cases[f"sub:{k}"] = case(body)
    for k, (body, _) in WRITE.items():
        cases[f"write:{k}"] = case(body)
    for k, (body, _) in MALFORMED.items():
        cases[f"bad:{k}"] = case(body)
    for k, (body, _) in CODE_BLOCKS.items():
        cases[f"code:{k}"] = case(body)
    cases["init"] = {
        "kind": "init",
        "case": str(_case_dir(tmp_path_factory)),
        "limit": 8.0,
    }
    for k, (body, _) in EVAL_LISTS.items():
        cases[f"eval:{k}"] = case(body)
    for k, body in INCLUDE_FUNC.items():
        cases[f"incl:{k}"] = case(body)
    cases["macro"] = case(
        "x 1;" + NL + "d { $x; rotationAngle 60; }" + NL + "e { $d; rotationAngle 90; }"
    )
    for k, body in UNIFORM.items():
        cases[f"uniform:{k}"] = case(body)
    cases["evalmulti"] = case(EVAL_MULTI_LINE)
    cases["codestream_list"] = case("x ( #codeStream { a } );")
    cases["includeFunc_braces"] = case("#includeFunc foo(a={b 1;})")
    for k, (body, _) in COMMENT_AFTER_BRACE.items():
        cases[f"comment:{k}"] = case(body)
    for k, body in REFUSED_IN_BLOCK.items():
        cases[f"refused:{k}"] = case(body)
    for k, body in DEEP_INPUTS.items():
        cases[f"deep:{k}"] = case(body, limit=8.0)
    for k, path in REAL.items():
        cases[f"real:{k}"] = _real_spec(path)
    return probe(cases, tmp_path_factory.mktemp("probe"))


# --- lists of dicts ---------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(LISTS))
def test_list_of_dicts_keeps_every_item_and_entry(res, name):
    assert tree(res[f"list:{name}"])["x"] == LISTS[name][1]


@pytest.mark.parametrize("name", sorted(LISTS))
def test_list_of_dicts_write_1_equals_write_2_equals_write_3(res, name):
    cycles_agree(res[f"list:{name}"])
    assert tree(res[f"list:{name}"])["x"] == LISTS[name][1]


@pytest.mark.parametrize("name", sorted(LISTS))
def test_list_of_dicts_input_does_not_hang(res, name):
    assert res[f"list:{name}"]["status"] != "hang", res[f"list:{name}"]


@pytest.mark.parametrize("name", sorted(LISTS))
def test_list_of_dicts_never_loses_items_silently(res, name):
    """A load that succeeds must have every item and entry; failing loudly is allowed."""
    r = res[f"list:{name}"]
    assert r["status"] != "hang", r
    if r["status"] == "ok":
        assert r["tree1"]["x"] == LISTS[name][1]


def test_big_one_line_list_of_dicts_keeps_every_item(res):
    items = tree(res["list:big"])["x"]
    assert len(items) == BIG
    assert items[0] == {"v": 0}
    assert items[-1] == {"v": BIG - 1}


def test_big_one_line_list_of_dicts_does_not_hang(res):
    assert res["list:big"]["status"] != "hang", res["list:big"]


# --- one-line sub-dicts ------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(SUB))
def test_one_line_sub_dict_keeps_every_entry(res, name):
    assert tree(res[f"sub:{name}"]) == SUB[name][1]


@pytest.mark.parametrize("name", sorted(SUB))
def test_one_line_sub_dict_write_1_equals_write_2_equals_write_3(res, name):
    cycles_agree(res[f"sub:{name}"])
    assert tree(res[f"sub:{name}"]) == SUB[name][1]


@pytest.mark.parametrize("name", sorted({**SUB, **SUB_EMPTY}))
def test_one_line_sub_dict_input_does_not_hang(res, name):
    assert res[f"sub:{name}"]["status"] != "hang", res[f"sub:{name}"]


@pytest.mark.parametrize("name", sorted(SUB_EMPTY))
def test_empty_one_line_sub_dict_loads_and_is_stable(res, name):
    """Characterization: an empty block is the one one-line form that works today."""
    cycles_agree(res[f"sub:{name}"])
    assert tree(res[f"sub:{name}"]) == SUB_EMPTY[name][1]


@pytest.mark.parametrize("name", sorted(SUB))
def test_one_line_sub_dict_never_drops_entries_silently(res, name):
    """A load that succeeds must have all the entries; failing loudly is allowed."""
    r = res[f"sub:{name}"]
    if r["status"] == "ok":
        assert r["tree1"] == SUB[name][1]


def test_spaced_foundation_11_sub_dict_reads_dSph(res):
    """`g.f10.dSph` reads 10e-3."""
    assert tree(res["sub:spaced_foundation_11"])["g"]["f10"]["dSph"] == pytest.approx(
        10e-3
    )


def test_entry_after_one_line_sub_dict_keeps_both_a_and_e(res):
    """`d { a 1; } e 2;`: since T-041 `e` is kept; T-040 keeps `a` as well."""
    assert tree(res["sub:then_entry"]) == {"d": {"a": 1}, "e": 2}


def test_pf_init_does_not_hang_on_one_line_sub_dicts_in_controlDict(res):
    assert res["init"]["status"] != "hang", res["init"]


def test_pf_init_loads_a_controlDict_with_one_line_sub_dicts(res):
    ctrl = tree(res["init"])
    assert ctrl["endTime"] == 2000  # guard: the rest of the file is read
    assert ctrl["topProbe"] == {"type": "probes"}
    assert ctrl["functions"]["oneLine"] == {"type": "probes", "fields": ["p", "U"]}


# --- writing ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(WRITE))
def test_unedited_one_line_block_is_written_with_every_entry_kept(res, name):
    """Fallback contract (multi-line is fine): the written text still has all entries."""
    r = loaded(res[f"write:{name}"])
    assert r["tree2"] == WRITE[name][1]
    for word in re.findall(r"[A-Za-z]\w*", WRITE[name][0]):
        assert word in r["w1"], word


@pytest.mark.parametrize("name", sorted(WRITE))
def test_unedited_one_line_block_write_1_equals_write_2_equals_write_3(res, name):
    cycles_agree(res[f"write:{name}"])
    assert loaded(res[f"write:{name}"])["tree1"] == WRITE[name][1]


@pytest.mark.parametrize("name", sorted(WRITE))
@XF_LAYOUT
def test_unedited_one_line_block_is_written_on_one_line_byte_identical(res, name):
    """Goal layout: the block's source line comes back unchanged (indent aside)."""
    written = [ln.strip() for ln in loaded(res[f"write:{name}"])["w1"].split(NL)]
    assert WRITE[name][0] in written


# --- malformed input -----------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_unterminated_one_line_block_does_not_hang(res, name):
    assert res[f"bad:{name}"]["status"] != "hang", res[f"bad:{name}"]


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_unterminated_one_line_block_never_loads_silently(res, name):
    assert res[f"bad:{name}"]["status"] == "error", res[f"bad:{name}"]


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_unterminated_one_line_block_raises_foamkit_error(res, name):
    r = failed(res[f"bad:{name}"])
    assert r["etype"] == "FoamKitError", f"{r['etype']}: {r['msg']}"


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_unterminated_one_line_block_error_names_file_and_line(res, name):
    r = failed(res[f"bad:{name}"])
    assert r["etype"] == "FoamKitError", f"{r['etype']}: {r['msg']}"
    assert FILE in r["msg"]
    assert line_of(r["msg"], HL + MALFORMED[name][1]), r["msg"]


# --- `#eval{ }` as a list item: never an empty list (T-044 owns the value) ---------------------


@pytest.mark.parametrize("name", sorted(EVAL_LISTS))
def test_eval_list_input_does_not_hang(res, name):
    assert res[f"eval:{name}"]["status"] != "hang", res[f"eval:{name}"]


@pytest.mark.parametrize("name", sorted(EVAL_LISTS))
def test_eval_list_never_loads_empty(res, name):
    """Either all three items are kept, or FoamKitError names the file and line."""
    r = res[f"eval:{name}"]
    assert r["status"] != "hang", r
    if r["status"] == "ok":
        node = r["tree1"]
        if name == "in_sub_dict":
            node = node["slab"]
        assert len(node["origin"]) == 3, node
    else:
        assert r["etype"] == "FoamKitError", f"{r['etype']}: {r['msg']}"
        assert FILE in r["msg"]
        assert line_of(r["msg"], HL + EVAL_LISTS[name][1]), r["msg"]


@pytest.mark.parametrize("name", sorted(EVAL_LISTS))
@pytest.mark.xfail(
    strict=True, reason="T-044: #eval{ } as a list item is not loaded yet"
)
def test_eval_list_keeps_all_three_items_verbatim(res, name):
    node = tree(res[f"eval:{name}"])
    node = node["slab"] if name == "in_sub_dict" else node
    items = node["origin"]
    assert len(items) == 3
    assert "#eval" in str(items[0]) and "$S" in str(items[0])
    assert items[1:] == [0, 0]


# --- multi-line #includeFunc arguments (T-022's "possible addition") -------------------------
# - OpenFOAM Foundation 11-14 accept them (functionEntry::readFuncNameArgs reads to the
# - matching ')' across newlines, and a '(' on the next line), ESI v2412 does not (it reads
# - one whitespace-delimited word).  foamkit raises FoamKitError today; Foundation accepts,
# - so the form is expected to load and round-trip.


@pytest.mark.parametrize("name", sorted(INCLUDE_FUNC))
def test_multi_line_includeFunc_arguments_do_not_hang(res, name):
    assert res[f"incl:{name}"]["status"] != "hang", res[f"incl:{name}"]


@pytest.mark.parametrize("name", sorted(INCLUDE_FUNC))
def test_multi_line_includeFunc_arguments_round_trip(res, name):
    r = loaded(res[f"incl:{name}"])
    assert r["w1"] == r["w2"] == r["w3"]
    assert r["tree1"]["z"] == 1  # the rest of the file is not swallowed
    assert re.search(r"#includeFunc\s+foo\(\s*a,\s*b\)", r["w1"])


# --- pathological nesting ---------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(DEEP_INPUTS))
def test_deeply_nested_input_is_loaded_or_refused_with_foamkit_error(res, name):
    r = res[f"deep:{name}"]
    assert r["status"] != "hang", r
    if r["status"] == "error":
        assert r["etype"] == "FoamKitError", f"{r['etype']}: {r['msg']}"
        assert FILE in r["msg"]


# --- `$macro;` inside a one-line block (Foundation 11 impeller createNonConformalCouplesDict) ----


def test_macro_inside_a_one_line_block_is_kept_not_dropped(res):
    """`d { $x; rotationAngle 60; }` keeps the macro and the entry, and is stable."""
    r = loaded(res["macro"])
    assert r["w1"] == r["w2"] == r["w3"]
    assert re.search(r"\$x;", r["w1"])
    assert re.search(r"\$d;", r["w1"])
    assert r["tree1"]["d"]["rotationAngle"] == 60
    assert r["tree1"]["e"]["rotationAngle"] == 90


# --- review round 1 ------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(UNIFORM))
def test_uniform_list_is_a_value_not_a_one_line_block(res, name):
    r = loaded(res[f"uniform:{name}"])
    assert r["w1"] == r["w2"] == r["w3"]
    assert UNIFORM_TEXT[name] in r["w1"]


def test_uniform_list_in_a_dict_keeps_its_neighbour(res):
    assert tree(res["uniform:in_dict"])["d"]["y"] == 2
    assert tree(res["uniform:in_one_line_block"])["d"]["y"] == 2


def test_eval_in_an_item_of_a_multi_line_list_still_loads(res):
    r = loaded(res["evalmulti"])
    assert r["w1"] == r["w2"] == r["w3"]
    assert "(#eval{$xcore + $xside} 0 $zmin)" in r["w1"]
    assert "(1 2 3)" in r["w1"]


def test_codeStream_in_a_one_line_list_is_refused_without_citing_T044(res):
    r = failed(res["codestream_list"])
    assert r["etype"] == "FoamKitError"
    assert line_of(r["msg"], HL + 1), r["msg"]
    assert "T-044" not in r["msg"]


def test_eval_in_a_one_line_list_names_T044(res):
    assert "T-044" in res["eval:top_level"]["msg"]


def test_braces_in_includeFunc_arguments_still_load(res):
    r = loaded(res["includeFunc_braces"])
    assert "foo(a={b 1;})" in r["w1"]
    assert r["w1"] == r["w2"] == r["w3"]


@pytest.mark.parametrize("name", sorted(COMMENT_AFTER_BRACE))
def test_comment_right_after_a_brace_does_not_hide_the_next_entry(res, name):
    r = loaded(res[f"comment:{name}"])
    assert r["tree1"] == COMMENT_AFTER_BRACE[name][1]
    assert r["w1"] == r["w2"] == r["w3"]


@pytest.mark.parametrize("name", sorted(REFUSED_IN_BLOCK))
def test_unreadable_block_content_raises_foamkit_error_naming_the_line(res, name):
    r = failed(res[f"refused:{name}"])
    assert r["etype"] == "FoamKitError", f"{r['etype']}: {r['msg']}"
    assert FILE in r["msg"]
    assert line_of(r["msg"], HL + 1), r["msg"]


# --- linear time on adversarial lines ------------------------------------------------------


def _read_time(tmp_path, body, n):
    import time

    from foamkit import FoamKitError
    import foamkit.types as fkt

    path = tmp_path / f"perf{n}"
    with open(path, "w", newline="\n") as f:
        f.write(doc(body(n)))
    start = time.perf_counter()
    try:
        fkt.DictFileParser(path).readDictFile()
    except FoamKitError:
        pass
    return time.perf_counter() - start


PERF_BODIES = {
    "unclosed_includeFunc": lambda n: "#includeFunc f(\n" * n,
    "includeFunc_paren_on_next_line": lambda n: "#includeFunc f\n(\n" * n,
    "entries_then_blocks_on_one_line": lambda n: (
        "p { " + "a 1; " * n + "q { } " * n + "}"
    ),
}


@pytest.mark.parametrize("name", sorted(PERF_BODIES))
def test_adversarial_input_is_read_in_linear_time(tmp_path, name):
    small = _read_time(tmp_path, PERF_BODIES[name], 1000)
    big = _read_time(tmp_path, PERF_BODIES[name], 4000)
    assert big < 8 * small + 0.5
    assert big < 5


# --- code blocks (must keep working) -----------------------------------------------------------


@pytest.mark.parametrize("name", sorted(CODE_BLOCKS))
def test_one_line_code_block_is_unaffected(res, name):
    r = loaded(res[f"code:{name}"])
    assert r["w1"] == r["w2"] == r["w3"]
    for key in CODE_BLOCKS[name][1]:
        assert key in r["tree1"]
    assert "#{" in r["w1"] and "#}" in r["w1"]


# --- real Foundation 11 files -------------------------------------------------------------


def plain(node):
    """`node` with the quotes of string values removed (so tests do not pin the quoting)."""
    if isinstance(node, dict):
        return {k: plain(v) for k, v in node.items()}
    if isinstance(node, list):
        return [plain(v) for v in node]
    return node.strip('"') if isinstance(node, str) else node


def _source_keys(path):
    """Top-level keywords of a snappyHexMeshDict, read with a regex (independent of foamkit)."""
    keys = []
    depth = 0
    parens = 0  # words inside a multi-line `( ... )` list are not keywords
    for line in path.read_text().split(NL):
        stripped = line.split("//")[0].strip()
        if (
            depth == 0
            and parens == 0
            and re.match(r"^[A-Za-z]\w*(\s+\S.*;)?$", stripped)
            and stripped != "FoamFile"
        ):
            keys.append(stripped.split()[0])
        depth += stripped.count("{") - stripped.count("}")
        parens += stripped.count("(") - stripped.count(")")
    return keys


RS = ("castellatedMeshControls", "refinementSurfaces")
ROTOR_EXPECT = [
    (
        ("geometry", "fixed", "regions"),
        {
            "patch0": {"name": "slipWall"},
            "patch1": {"name": "outlet"},
            "patch2": {"name": "inlet"},
        },
    ),
    (
        ("castellatedMeshControls", "features"),
        [
            {"file": "fixed.eMesh", "level": 2},
            {"file": "rotatingZone.eMesh", "level": 4},
        ],
    ),
    (RS + ("fixed", "patchInfo"), {"type": "wall"}),
    (
        RS + ("fixed", "regions", "patch2"),
        {"level": [2, 2], "patchInfo": {"type": "patch"}},
    ),
]
DUCT_EXPECT = [
    (
        ("geometry", "heatedDuct", "regions", "heaterExternal"),
        {"name": "heaterExternal"},
    ),
    (
        RS + ("heatedDuct", "regions", "metalExternal"),
        {"level": [1, 1], "patchInfo": {"type": "wall"}},
    ),
    (
        RS + ("heatedDuct", "regions", "fluidInlet"),
        {"level": [0, 0], "patchInfo": {"type": "patch"}},
    ),
    (("addLayersControls", "layers"), {}),
]
EXPECT = {"rotor": ROTOR_EXPECT, "duct": DUCT_EXPECT}


def _at(node, path):
    for key in path:
        node = node[key]
    return node


def test_real_fixtures_are_the_lf_downloads():
    assert b"\r" not in ROTOR.read_bytes()
    assert b"\r" not in DUCT.read_bytes()


@pytest.mark.parametrize("name", sorted(REAL))
def test_real_snappyHexMeshDict_finishes_within_the_timeout(res, name):
    """Today both hang; after the fix they load (or fail loudly) within the bound."""
    assert res[f"real:{name}"]["status"] != "hang", res[f"real:{name}"]


@pytest.mark.parametrize("name", sorted(REAL))
def test_real_snappyHexMeshDict_loads_with_every_top_level_entry(res, name):
    keys = [k for k in tree(res[f"real:{name}"]) if not k.startswith("include")]
    assert keys == _source_keys(REAL[name])
    assert len(keys) >= 5  # guard: the regex found the entries


@pytest.mark.parametrize("name", sorted(REAL))
def test_real_snappyHexMeshDict_keeps_the_content_of_the_one_line_blocks(res, name):
    t = plain(tree(res[f"real:{name}"]))
    for path, expected in EXPECT[name]:
        assert _at(t, path) == expected, path


def test_heatedDuct_keeps_all_eight_one_line_regions(res):
    t = plain(tree(res["real:duct"]))
    regions = t["geometry"]["heatedDuct"]["regions"]
    assert list(regions) == [
        "metalInlet",
        "heaterInlet",
        "fluidInlet",
        "metalOutlet",
        "heaterOutlet",
        "fluidOutlet",
        "metalExternal",
        "heaterExternal",
    ]
    assert all(v == {"name": k} for k, v in regions.items())


# - rotorDisk has `inGroups (fixed);`, a one-line list with ONE element.  On main (before
# - T-040, with no `{ }` involved) it is written `inGroups    ( fixed);` (golden-pinned,
# - e.g. `libs ( "libsampling.so");`) and that text is read back as a multi-line list, so
# - write 1 differs from write 2 (then write 2 == write 3).  Not T-040's; the one-line
# - list wart belongs with T-037/T-020 (re-flow) and the golden files pin the first write.
XF_ONE_ELEMENT_LIST = pytest.mark.xfail(
    strict=True,
    reason="pre-existing, not T-040: a one-line one-element list `x (a);` is written "
    "`x ( a);` and read back as a multi-line list (goldens pin the first write)",
)


@pytest.mark.parametrize("name", sorted(REAL))
def test_real_snappyHexMeshDict_write_2_equals_write_3(res, name):
    r = loaded(res[f"real:{name}"])
    assert r["w2"] == r["w3"]
    assert r["tree1"] == r["tree2"] == r["tree3"]


@pytest.mark.parametrize(
    "name", ["duct", pytest.param("rotor", marks=XF_ONE_ELEMENT_LIST)]
)
def test_real_snappyHexMeshDict_write_1_equals_write_2(res, name):
    r = loaded(res[f"real:{name}"])
    assert r["w1"] == r["w2"] == r["w3"]
    assert r["tree1"] == r["tree2"] == r["tree3"]
