"""The dict/list end scan must ignore brackets inside strings, comments and code (T-035).

Specification tests for docs/tickets/T-035-brace-scan-ignores-strings-comments.md
(issue #47).  Reviewer shape: `d { e { <line> inner 2; } mid 3; }`, where `<line>` has
a `{`, `}`, `(` or `)` inside a quoted string, a `//` comment, a `/* */` comment or a
`#{ ... #}` code block.  Today `_findDictOrListEndLine` counts every bracket
character, so the file loads with entries in the wrong scope (`}` variants) or fails
with "Could not locate end of dict" (`{` variants), and the structure shifts on
every write.

Every document is built by `_doc`, which nests `depth` dictionaries (d, e, f), puts
the shape lines and `inner 2;` in the innermost one, and puts one uniquely named
`mid<k>` entry after the close of each level.  The expected scope of every entry is
therefore exact (`_scopes` is compared with the expected map), not just "it loads".

Open questions the ticket leaves, and what these tests assume:
- `#fooBar /* ( */` followed by lines `}` and `)` (and `/* " */ x` followed by `}` and
  `"`): the bracket inside a comment is not an opener, so the directive ends at its
  line, the next `}` really closes the dictionary, and the file is genuinely
  unbalanced.  Pinned as `FoamKitError` naming the file; the line is not pinned.
  The other reading (the comment bracket opens a capture that swallows `}` and `)`)
  would make the file load; see test_swallowing_shapes_*.
- A stray closing brace is reported with the file name only (the ticket names the
  line only for an unclosed opener).
"""

import re
import time

import pytest

import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import TESTS
from test_directives import HEADER

HL = HEADER.count("\n")
RELEASES = TESTS / "releases"
NAMES = ["d", "e", "f"]
NL = "\n"
LETTERS = ["wa", "wb", "wc", "wd"]  # file names without digits


# --- helpers ------------------------------------------------------------------


def _doc(depth, shape_lines, extras=()):
    """Return (body, expected_scopes) for `depth` nested dicts around `shape_lines`."""
    names = NAMES[:depth]
    lines = []
    for j, name in enumerate(names):
        lines += [f"{'    ' * j}{name}", f"{'    ' * j}{{"]
    pad = "    " * depth
    lines += [pad + ln if ln else ln for ln in shape_lines]
    lines += [f"{pad}inner 2;"]
    for j in range(depth - 1, -1, -1):
        lines += [f"{'    ' * j}}}", f"{'    ' * j}mid{j} {j + 3};"]
    expected = {"": sorted([names[0], "mid0"])}
    for j in range(1, depth):
        expected["/".join(names[:j])] = sorted([names[j], f"mid{j}"])
    expected["/".join(names)] = sorted(["inner", *extras])
    return NL.join(lines) + NL, expected


def _scopes(obj, prefix=""):
    """`{path: sorted keys}` ignoring private keys, comments and directives."""
    keys = []
    out = {}
    for k, v in vars(obj).items():
        if k.startswith(("_", "unnamed_")) or type(v).__name__ in (
            "ofComment",
            "ofVerbatimDirective",
        ):
            continue
        keys.append(k)
        if isinstance(v, dict):
            out.update(_scopes(v, f"{prefix}{k}/"))
    out[prefix.rstrip("/")] = sorted(keys)
    return out


def _walk(obj):
    for key, val in list(vars(obj).items()):
        if key.startswith("_"):
            continue
        yield val
        if isinstance(val, dict):
            yield from _walk(val)


def _verbatims(obj):
    return [v for v in _walk(obj) if isinstance(v, fkt.ofVerbatimDirective)]


def _read(tmp_path, body, name="wa"):
    path = tmp_path / name
    path.write_text(HEADER + body)
    return fkt.DictFileParser(path).readDictFile()


def _writes(tmp_path, body, n=3):
    """Read `body`, then write/read `n` times; return (first object, [texts])."""
    first = _read(tmp_path, body, "wa")
    texts = [first.toString()]
    for k in range(1, n):
        path = tmp_path / LETTERS[k]
        path.write_text(texts[-1])
        texts.append(fkt.DictFileParser(path).readDictFile().toString())
    return first, texts


def _norm(text):
    return [" ".join(ln.split()) for ln in text.splitlines() if ln.strip()]


def _contains_run(haystack, needle):
    n = len(needle)
    return any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


def _raises_naming(tmp_path, body, *lines):
    """The body raises FoamKitError naming the file and one of the body `lines`."""
    path = tmp_path / "braceScanFile"
    path.write_text(HEADER + body)
    with pytest.raises(FoamKitError) as err:
        fkt.DictFileParser(path).readDictFile()
    msg = str(err.value)
    assert "braceScanFile" in msg, msg
    if lines:
        wanted = "|".join(str(HL + n) for n in lines)
        assert re.search(rf"\bline (?:{wanted})\b", msg), msg
    return msg


DEPTHS = pytest.mark.parametrize("depth", [1, 2, 3])


# --- ordinary-entry shapes -----------------------------------------------------
# (id, lines, extra keys in the innermost scope)
ORDINARY = [
    ("string-close", ['note "a } b";'], ["note"]),
    ("string-open", ['note "a { b";'], ["note"]),
    ("string-open-and-close", ['note "} {";'], ["note"]),
    ("line-comment-close", ["// comment }"], []),
    ("line-comment-open", ["// comment {"], []),
    ("trailing-line-comment-close", ["note 1; // }"], ["note"]),
    ("trailing-line-comment-open", ["note 1; // {"], ["note"]),
    ("list-string-close", ['x ( "}" );'], ["x"]),
    ("list-string-open", ['x ( "{" );'], ["x"]),
    ("list-string-rparen", ['x ( ")" );'], ["x"]),
    ("list-string-lparen", ['x ( "(" );'], ["x"]),
    ("block-comment-close", ["/* } */"], []),
    ("block-comment-open", ["/* { */"], []),
    ("block-comment-multiline", ["/* first }", "   second { */"], []),
    (
        "code-block-close",
        ["codeExecute", "#{", '    Info<< "}" << endl;', "#};"],
        [],
    ),
    (
        "code-block-open",
        ["codeExecute", "#{", '    Info<< "{" << endl;', "#};"],
        [],
    ),
    (
        "code-block-comment-close",
        ["codeExecute", "#{", "    // }", "#};"],
        [],
    ),
    (
        "code-block-comment-open",
        ["codeExecute", "#{", "    /* { */", "#};"],
        [],
    ),
]
# Edge cases from the ticket's risks list.
EDGE = [
    ("escaped-quote", ['note "a \\" } b";'], ["note"]),
    ("comment-opener-in-string", ['note "/* }";'], ["note"]),
    ("apostrophe-in-comment", ["// don't }"], []),
    ("quote-in-line-comment", ['// say "hi }'], []),
    ("line-comment-opener-in-block-comment", ["/* // } */"], []),
    ("block-comment-opener-in-line-comment", ["// /* }"], []),
]
SHAPES = [pytest.param(ln, ex, id=i) for i, ln, ex in ORDINARY + EDGE]
WRITE_SHAPES = [pytest.param(ln, ex, id=i) for i, ln, ex in ORDINARY + EDGE]
_ONE_LINE_LISTS = {
    "list-string-close",
    "list-string-open",
    "list-string-lparen",
    "list-string-rparen",
}
THREE_WRITE_SHAPES = [
    pytest.param(ln, ex, id=i, marks=[]) for i, ln, ex in ORDINARY + EDGE
]


@DEPTHS
@pytest.mark.parametrize("lines, extras", SHAPES)
def test_ordinary_shape_keeps_every_entry_in_its_scope(tmp_path, depth, lines, extras):
    body, expected = _doc(depth, lines, extras)
    assert _scopes(_read(tmp_path, body)) == expected


@DEPTHS
@pytest.mark.parametrize("lines, extras", SHAPES)
def test_ordinary_shape_values_stay_with_their_entries(tmp_path, depth, lines, extras):
    body, _ = _doc(depth, lines, extras)
    d = _read(tmp_path, body)
    node = d
    for name in NAMES[:depth]:
        node = getattr(node, name)
    assert node.inner.value == 2
    assert getattr(d, "mid0").value == 3
    assert "mid" not in vars(d)


@DEPTHS
@pytest.mark.parametrize("lines, extras", SHAPES)
def test_ordinary_shape_creates_no_brace_keys(tmp_path, depth, lines, extras):
    body, _ = _doc(depth, lines, extras)
    keys = [k for scope in _scopes(_read(tmp_path, body)).values() for k in scope]
    assert not [k for k in keys if any(c in k for c in "{}()")]


@DEPTHS
@pytest.mark.parametrize("lines, extras", THREE_WRITE_SHAPES)
def test_ordinary_shape_writes_three_times_identically(tmp_path, depth, lines, extras):
    body, expected = _doc(depth, lines, extras)
    first, texts = _writes(tmp_path, body)
    assert texts[0] == texts[1] == texts[2]


@DEPTHS
@pytest.mark.parametrize("lines, extras", WRITE_SHAPES)
def test_ordinary_shape_survives_the_write_with_the_same_scopes(
    tmp_path, depth, lines, extras
):
    body, expected = _doc(depth, lines, extras)
    first, texts = _writes(tmp_path, body, 2)
    again = tmp_path / "wd"
    again.write_text(texts[0])
    assert _scopes(fkt.DictFileParser(again).readDictFile()) == expected


@pytest.mark.parametrize(
    "lines",
    [
        ['note "a } b";'],
        ['note "a { b";'],
        ["// comment }"],
        ["/* } */"],
        pytest.param(
            ['x ( "}" );'],
            marks=pytest.mark.xfail(strict=True, reason="T-020: list layout"),
        ),
    ],
)
def test_single_line_shape_text_is_written_back(tmp_path, lines):
    body, _ = _doc(2, lines)
    _, texts = _writes(tmp_path, body, 1)
    assert _contains_run(_norm(texts[0]), _norm(NL.join(lines)))


def test_one_line_list_read_write_read_gains_an_empty_item(tmp_path):
    """Characterization of the pre-existing bug behind XF_LIST_EMPTY_ITEM: no brackets
    in strings or comments are involved."""
    first = _read(tmp_path, "x ( 1 );" + NL, "wa")
    path = tmp_path / "wb"
    path.write_text(first.toString())
    again = fkt.DictFileParser(path).readDictFile()
    assert again.toString() == first.toString()


# --- list shapes ------------------------------------------------------------------
# A multi-line list value whose items hide a bracket in a string or comment.
LIST_ITEMS = [
    ("string-rparen", ['    "a )"', '    "b"']),
    ("string-lparen", ['    "a ("', '    "b"']),
    ("string-rbrace", ['    "a }"', '    "b"']),
    ("string-lbrace", ['    "a {"', '    "b"']),
    ("line-comment-rparen", ["    // note )", '    "b"']),
    ("line-comment-lparen", ["    // note (", '    "b"']),
    ("line-comment-rbrace", ["    // note }", '    "b"']),
    ("line-comment-lbrace", ["    // note {", '    "b"']),
    ("block-comment-rparen", ["    /* ) */", '    "b"']),
    ("block-comment-lparen", ["    /* ( */", '    "b"']),
    ("block-comment-rbrace", ["    /* } */", '    "b"']),
    ("block-comment-lbrace", ["    /* { */", '    "b"']),
]
LIST_SHAPES = [
    pytest.param(["items", "("] + items + [");"], ["items"], id=i)
    for i, items in LIST_ITEMS
]


@DEPTHS
@pytest.mark.parametrize("lines, extras", LIST_SHAPES)
def test_list_shape_keeps_every_entry_in_its_scope(tmp_path, depth, lines, extras):
    body, expected = _doc(depth, lines, extras)
    assert _scopes(_read(tmp_path, body)) == expected


@DEPTHS
@pytest.mark.parametrize("lines, extras", LIST_SHAPES)
def test_list_shape_writes_three_times_identically(tmp_path, depth, lines, extras):
    body, _ = _doc(depth, lines, extras)
    _, texts = _writes(tmp_path, body)
    assert texts[0] == texts[1] == texts[2]


@pytest.mark.parametrize("lines, extras", LIST_SHAPES)
def test_list_shape_text_is_written_back(tmp_path, lines, extras):
    body, _ = _doc(2, lines, extras)
    _, texts = _writes(tmp_path, body, 1)
    assert _contains_run(_norm(texts[0]), _norm(NL.join(lines[2:-1])))


def test_list_with_close_paren_in_string_keeps_following_entries_in_scope(tmp_path):
    """Characterization: a one-line list with a `)` in a string is scoped correctly today."""
    body = 'd\n{\n    e\n    {\n        x ( ")" );\n        inner 2;\n    }\n    mid 3;\n}\n'
    d = _read(tmp_path, body)
    assert d.d.e.inner.value == 2
    assert d.d.mid.value == 3
    assert "mid" not in vars(d)


# --- directive shapes (ordinary directive lines) ----------------------------------
DIRECTIVE_LINES = [
    '#message "a } b"',
    '#fooBar ( "}" )',
    "#fooBar // }",
    "#fooBar /* } */",
    "#fooBar #{ } #}",
    '#remove ( "}" )',
    '#message "a { b"',
    '#fooBar ( "{" )',
    "#fooBar // {",
    "#fooBar /* { */",
    "#fooBar #{ { #}",
    '#remove ( "{" )',
    # a bracket inside a comment on the directive line is not an opener
    "#fooBar /* ( */",
    "#fooBar /* ) */",
    '#fooBar /* " */ x',
    # edge cases: `//` or `/*` inside a string, an escaped quote
    '#fooBar "http://x }"',
    '#fooBar "/* }"',
    '#fooBar "a \\" } b"',
]


@DEPTHS
@pytest.mark.parametrize("line", DIRECTIVE_LINES)
def test_directive_shape_keeps_every_entry_in_its_scope(tmp_path, depth, line):
    body, expected = _doc(depth, [line])
    assert _scopes(_read(tmp_path, body)) == expected


@DEPTHS
@pytest.mark.parametrize("line", DIRECTIVE_LINES)
def test_directive_shape_is_one_verbatim_directive_in_the_innermost_dict(
    tmp_path, depth, line
):
    body, _ = _doc(depth, [line])
    d = _read(tmp_path, body)
    node = d
    for name in NAMES[:depth]:
        node = getattr(node, name)
    (found,) = _verbatims(d)
    assert found in vars(node).values()
    assert found.text.strip() == line


@DEPTHS
@pytest.mark.parametrize("line", DIRECTIVE_LINES)
def test_directive_shape_writes_three_times_identically(tmp_path, depth, line):
    body, _ = _doc(depth, [line])
    _, texts = _writes(tmp_path, body)
    assert texts[0] == texts[1] == texts[2]
    assert _contains_run(_norm(texts[0]), _norm(line))


# `#fooBar /* { */` followed LATER in the same dict by a compensating `}` that is
# itself inert (a comment or a string): the brace in the first comment is not an
# opener, so neither of them changes the structure.
COMPENSATED = [
    pytest.param(["#fooBar /* { */", "// }"], [], id="line-comment"),
    pytest.param(["#fooBar /* { */", 'note "}";'], ["note"], id="string"),
    pytest.param(["#fooBar /* { */", "note 1;", "// }"], ["note"], id="entry-between"),
    pytest.param(["#fooBar /* ( */", 'note ")";'], ["note"], id="paren-string"),
    pytest.param(
        ['#fooBar /* " */ x', '// "', "note 1;"], ["note"], id="quote-comment"
    ),
]


@DEPTHS
@pytest.mark.parametrize("lines, extras", COMPENSATED)
def test_comment_bracket_with_later_compensating_inert_bracket(
    tmp_path, depth, lines, extras
):
    """Today `inner` vanishes into the directive text and `mid` moves inward."""
    body, expected = _doc(depth, lines, extras)
    d = _read(tmp_path, body)
    assert _scopes(d) == expected
    (found,) = _verbatims(d)
    assert found.text.strip() == lines[0]


@DEPTHS
@pytest.mark.parametrize("lines, extras", COMPENSATED)
def test_comment_bracket_with_later_compensating_inert_bracket_is_stable(
    tmp_path, depth, lines, extras
):
    body, _ = _doc(depth, lines, extras)
    _, texts = _writes(tmp_path, body)
    assert texts[0] == texts[1] == texts[2]


# Directive followed by the lines the capture used to swallow.  Reading the comment
# as a comment, the `}` closes the dictionary, so the document has one `}` too
# many (and, in the quote case, an unterminated string): it is genuinely unbalanced.
SWALLOWING = [
    pytest.param(["#fooBar /* ( */", "}", ")"], id="paren"),
    pytest.param(['#fooBar /* " */ x', "}", '"'], id="quote"),
]


@DEPTHS
@pytest.mark.parametrize("lines", SWALLOWING)
def test_swallowing_shapes_are_unbalanced_and_raise_naming_the_file(
    tmp_path, depth, lines
):
    body, _ = _doc(depth, lines)
    _raises_naming(tmp_path, body)


@DEPTHS
def test_lone_quote_line_after_comment_directive_names_its_line(tmp_path, depth):
    lines = ['#fooBar /* " */ x', "}", '"']
    body, _ = _doc(depth, lines)
    _raises_naming(tmp_path, body, 2 * depth + 3)


# --- genuinely unbalanced input -----------------------------------------------------


def test_unclosed_dict_names_file_and_opening_line(tmp_path):
    body = "d\n{\n    e\n    {\n        inner 2;\n    }\ntail 1;\n"
    _raises_naming(tmp_path, body, 1, 2)


def test_extra_closing_brace_raises_naming_the_file(tmp_path):
    body = "d\n{\n    inner 2;\n}\n}\ntail 1;\n"
    _raises_naming(tmp_path, body)


def test_unclosed_dict_is_reported_even_with_brace_strings_inside(tmp_path):
    body = 'd\n{\n    note "}";\n    inner 2;\ntail 1;\n'
    _raises_naming(tmp_path, body, 1, 2)


def test_extra_closing_brace_after_a_brace_string_is_still_reported(tmp_path):
    body = 'd\n{\n    note "}";\n    inner 2;\n}\n}\ntail 1;\n'
    _raises_naming(tmp_path, body)


@pytest.mark.parametrize("where", ["top", "depth2"])
def test_unterminated_string_names_file_and_line(tmp_path, where):
    if where == "top":
        body, line = 'a 1;\nnote "never closed;\nb 2;\n', 2
    else:
        body = 'd\n{\n    e\n    {\n        note "never closed;\n        inner 2;\n    }\n}\n'
        line = 5
    _raises_naming(tmp_path, body, line)


@pytest.mark.parametrize("where", ["top", "depth2"])
def test_unterminated_block_comment_names_file_and_line(tmp_path, where):
    if where == "top":
        body, line = "a 1;\n/* never closed\nb 2;\n", 2
    else:
        body = (
            "d\n{\n    e\n    {\n        /* never closed\n        inner 2;\n    }\n}\n"
        )
        line = 5
    _raises_naming(tmp_path, body, line)


@pytest.mark.parametrize("where", ["top", "depth2"])
def test_unterminated_code_block_names_file_and_line(tmp_path, where):
    if where == "top":
        body, line = "a 1;\ncodeExecute\n#{\n    foo();\nb 2;\n", 3
    else:
        body = "d\n{\n    e\n    {\n        codeExecute\n        #{\n            foo();\n        inner 2;\n    }\n}\n"
        line = 6
    _raises_naming(tmp_path, body, line)


def test_unterminated_string_does_not_scan_to_the_end_of_the_file_silently(tmp_path):
    body = 'd\n{\n    note "never closed;\n' + "".join(
        f"    k{i} 1;\n" for i in range(50)
    )
    path = tmp_path / "braceScanFile"
    path.write_text(HEADER + body)
    with pytest.raises(FoamKitError):
        fkt.DictFileParser(path).readDictFile()


# --- bounded and linear ------------------------------------------------------------
BIG_LINES = ['"}"', '"{"', '")"', '"("', '"}{"', '"{{ }}"']


def test_large_input_with_brackets_in_strings_parses_in_bounded_time(tmp_path):
    n = 100_000
    shape = [f"k{i} {BIG_LINES[i % len(BIG_LINES)]};" for i in range(n)]
    body, expected = _doc(2, shape, [f"k{i}" for i in range(n)])
    start = time.perf_counter()
    d = _read(tmp_path, body)
    parse_time = time.perf_counter() - start
    assert parse_time < 120
    assert len(vars(d.d.e)) >= n
    assert d.d.e.inner.value == 2
    assert d.d.mid1.value == 4
    assert d.mid0.value == 3


def test_large_input_writes_and_rereads_identically(tmp_path):
    n = 20_000
    shape = [f"k{i} {BIG_LINES[i % len(BIG_LINES)]};" for i in range(n)]
    body, _ = _doc(2, shape)
    start = time.perf_counter()
    _, texts = _writes(tmp_path, body, 2)
    assert time.perf_counter() - start < 120
    assert texts[0] == texts[1]


def test_long_comment_and_code_block_input_parses_in_bounded_time(tmp_path):
    code = ["codeExecute", "#{"] + [
        f'    Info<< "}}{{{i}" << endl;' for i in range(20_000)
    ]
    code += ["#};"]
    comments = [f"// close }} {i}" for i in range(20_000)]
    body, expected = _doc(2, code + comments)
    start = time.perf_counter()
    assert _scopes(_read(tmp_path, body)) == expected
    assert time.perf_counter() - start < 120


def test_deep_nesting_with_brackets_in_strings_does_not_hit_the_recursion_limit(
    tmp_path,
):
    depth = 30
    lines = []
    for j in range(depth):
        lines += [f"n{j}", "{", f'    note{j} "}}";']
    lines += ["inner 2;"]
    for j in range(depth - 1, -1, -1):
        lines += ["}", f"mid{j} 3;"]
    d = _read(tmp_path, NL.join(lines) + NL)
    node = d
    for j in range(depth):
        node = getattr(node, f"n{j}")
    assert node.inner.value == 2
    assert d.mid0.value == 3


# --- real files keep their outcomes ----------------------------------------------------
# - Outcome per file in tests/releases/ before T-035: top-level keys when it loads,
# - else the exception type.  None of these files triggers the bug.
REAL_OUTCOMES = {
    "esi-v2606.bendJunction.blockMeshDict": ["scale", "d0", "d1", "d2"],
    "esi-v2606.externalCoupled": ["externalCoupled"],
    "foundation-11.controlDict": ["application", "solver", "startFrom"],
    "foundation-14.cylinder.momentumTransport": ["simulationType", "RAS", "LES"],
    "foundation-14.pitzDaily.momentumTransport": ["simulationType", "RAS"],
    "foundation-14.roomHeating.fvModels": ["includeModel0"],
    "esi-v2606.freePiston.U": ValueError,
    "esi-v2606.good-if1.dict": FoamKitError,
    "esi-v2606.good-if3.dict": FoamKitError,
    "esi-v2606.good-word-expand.dict": FoamKitError,
    "esi-v2606.potentialFoam-cylinder.blockMeshDict": FoamKitError,
    "esi-v2606.squareBend.blockMeshDict": FoamKitError,
    "foundation-13.aerofoilNACA0012Steady.U": TypeError,
    "foundation-14.aerofoilNACA0012Steady.U": TypeError,
    "foundation-14.cylinder.blockMeshDict": TypeError,
    "foundation-14.cylinder.fvSchemes": FoamKitError,
    "foundation-14.engine2Valve2D.fvConstraints": FoamKitError,
    "foundation-14.floatingBeam.blockMeshDict": ValueError,
    # - Load since T-041 and write since T-042 (an `#include` inside the `blocks` and
    # - `boundary` lists is one include item).
    "foundation-14.helmholtzResonance.blockMeshDict": [
        "scale",
        "vertices",
        "x1",
        "x2",
        "x3",
    ],
    "esi-v2606.helmholtzResonance.blockMeshDict": [
        "scale",
        "vertices",
        "x1",
        "x2",
        "x3",
    ],
    "foundation-14.trayedPipe.createZonesDict": FoamKitError,
    # - Added with T-041: the multi-entry-line files load (rotatingCube stops earlier on
    # - value-position `#calc`, T-027).
    "foundation-14.rotatingCube.blockMeshDict": TypeError,
    "foundation-14.refineMeshSector.blockMeshDict": ["Ax", "Ay", "Bx", "By"],
    "foundation-11.refineFieldDirs.blockMeshDict": ["convertToMeters", "Ax", "Ay"],
    "foundation-11.damBreak.fvSchemes": ["ddtSchemes", "gradSchemes", "divSchemes"],
    # - Added with T-040: both hung before (one-line `{ ... }` sub-dicts and list items);
    # - they load with every entry (timeout-guarded in tests/test_one_line_blocks.py).
    "foundation-11.rotorDisk.snappyHexMeshDict": [
        "includeEtc0",
        "castellatedMesh",
        "snap",
        "addLayers",
        "geometry",
        "castellatedMeshControls",
        "snapControls",
        "addLayersControls",
    ],
    "foundation-11.heatedDuct.snappyHexMeshDict": [
        "includeEtc0",
        "castellatedMesh",
        "snap",
        "addLayers",
        "geometry",
        "castellatedMeshControls",
        "addLayersControls",
    ],
}


def test_every_release_file_has_a_pinned_outcome():
    names = {p.name for p in RELEASES.iterdir() if not p.name.startswith(".")}
    assert names == set(REAL_OUTCOMES)


@pytest.mark.parametrize("name", sorted(REAL_OUTCOMES))
def test_release_file_outcome_is_unchanged(name):
    expected = REAL_OUTCOMES[name]
    if isinstance(expected, type):
        with pytest.raises(expected):
            fkt.DictFileParser(RELEASES / name).readDictFile().toString()
    else:
        d = fkt.DictFileParser(RELEASES / name).readDictFile()
        d.toString()
        keys = [k for k, v in vars(d).items() if not k.startswith("_")]
        keys = [k for k in keys if type(vars(d)[k]).__name__ != "ofComment"]
        assert keys[: len(expected)] == expected
