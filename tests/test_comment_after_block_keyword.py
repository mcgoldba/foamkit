"""A `//` comment after a sub-dict or list keyword (`mixture // air ...`) (T-055, issue #74).

Specification tests for docs/tickets/T-055-comment-after-block-keyword.md.  A keyword line
with a `//` comment, followed by `{` or `(` on the next line, loads under the plain keyword
and the comment text is written back on the keyword line.  No loaded key contains `//`: the
input loads correctly or raises `FoamKitError` naming file and line.

Outcome of the ticket's table on this branch (main 647cb84, after T-052), top level and in a
sub-dict:

    d // c / { a 1; }       silent key change: the key is `d_//_c`; the text is written back
    d //c,  d<TAB>// c      unchanged (`d // c`).  Keys `d_//c` and `d\\t//_c`.
    p / { / d // c / {..}   same, one level down (key `d_//_c` inside `p`)
    p { d // c / { .. } }   FoamKitError "Could not locate the end of 'p' (unbalanced
                            brackets)" (loud, but the input is valid)
    x // c / ( / 1 / );     bare ValueError "Name must be a single word." (no file or line)

Guards that behave as today and are not asserted as a fix here: `"a//b"` as a quoted
keyword (T-036; stored under the attribute `_a//b_`) and `d { a 1; } // c` (T-056; loads as
`d`, the comment is dropped on write).

Real files (byte-exact copies in tests/releases/, outside the golden glob; LF, no CR;
`git hash-object` of each copy equals the blob in the commit and `cmp` shows no difference
to the raw file at that commit).  OpenFOAM-14 (https://github.com/OpenFOAM/OpenFOAM-14,
commit 31554318f4674a8538e6e05bb899332151ef138f, 2026-11-06), extracted with
`git show HEAD:<path>`:

foundation-14.aerofoilNACA0012.physicalProperties  (`mixture // air at room temperature (293 K)`, line 28)
  tutorials/fluid/aerofoilNACA0012/constant/physicalProperties
  blob 88f2723291a3398a195f1b62f1143ad81007227e
foundation-14.simpleRushtonMRF.createBafflesDict.baffles  (`bafflesGroup // group name`, line 21)
  tutorials/incompressibleFluid/simpleRushtonMRF/system/createBafflesDict.baffles
  blob 345603cdc2841f223d30d00d5925c175214912e4
foundation-14.SandiaD_LTS.radiationProperties  (`loTcoeffs // coefss for T < Tcommon` then `(`)
  tutorials/multicomponentFluid/SandiaD_LTS/constant/radiationProperties
  blob bd87e5af5352ca75462d487ff1edc8ede8253c7f
  (also holds `;`-trailing comments (T-056) and comments after list items (T-057): only the
  two keyword-line comments are asserted for this file)
"""

import re

import pytest

import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import TESTS
from test_directives import HEADER

NL = "\n"
RELEASES = TESTS / "releases"
PHYSICAL = RELEASES / "foundation-14.aerofoilNACA0012.physicalProperties"
BAFFLES = RELEASES / "foundation-14.simpleRushtonMRF.createBafflesDict.baffles"
RADIATION = RELEASES / "foundation-14.SandiaD_LTS.radiationProperties"
HL = HEADER.count(NL)
PRIVATE = {
    "_name",
    "_entryTypes",
    "_nUnnamed",
    "_CLASS_VARS",
    "_header",
    "_foamFile",
    "_srcLayout",
    "_newline",
    "_mixedLine",
}


def _load(path):
    return fkt.DictFileParser(path).readDictFile()


def _all_keys(d):
    """Every entry name of an ofDict (attributes; comments and parser internals left out),
    including the ones that start with `_` (a quoted keyword is stored as `_<text>_`)."""
    return [
        k
        for k, v in vars(d).items()
        if k not in PRIVATE
        and not k.startswith("_comment_")
        and type(v).__name__ != "ofComment"
    ]


def _shape(obj):
    """Names of an ofDict, recursively; the leaf values of anything else."""
    if isinstance(obj, fkt.ofDict):
        return {k: _shape(getattr(obj, k)) for k in _all_keys(obj)}
    value = getattr(obj, "value", obj)
    if isinstance(value, (list, tuple)):
        return [_shape(v) for v in value]
    return getattr(value, "value", value)


def _leaves(obj):
    if isinstance(obj, (list, tuple)):
        return [leaf for i in obj for leaf in _leaves(i)]
    value = getattr(obj, "value", obj)
    if isinstance(value, (list, tuple)):
        return _leaves(value)
    return [float(value)]


def _wrap(text, container):
    if container == "top":
        return text
    return "sub\n{\n" + "".join("    " + ln + NL for ln in text.splitlines()) + "}\n"


def _scope(d, container):
    return d if container == "top" else d.sub


def _span(text):
    return "|".join(str(HL + 1 + i) for i in range(text.count(NL)))


def _read_write(tmp_path, text):
    """Write `text` (after a header), read it, write, re-read, write.
    Returns (first, second, text1, text2)."""
    path = tmp_path / "block"
    path.write_text(HEADER + text)
    first = _load(path)
    text1 = first.toString()
    out = tmp_path / "wa"
    out.write_text(text1)
    second = _load(out)
    return first, second, text1, second.toString()


# --- the table (without the /* */ row: T-031) ----------------------------------------------------
# - (id, text, path from the scope to the entry `d`/`x`, comment, leaves of a list entry or
# - None for a dict whose entry is `a 1`)
DICT_ROWS = [
    ("space", "d // c\n{\n    a 1;\n}\n", ("d",), "c"),
    ("no-space", "d //c\n{\n    a 1;\n}\n", ("d",), "c"),
    ("tab", "d\t// c\n{\n    a 1;\n}\n", ("d",), "c"),
    (
        "inside-a-dict",
        "p\n{\n    d // c\n    {\n        a 1;\n    }\n}\n",
        ("p", "d"),
        "c",
    ),
    (
        "inside-a-one-line-brace",
        "p { d // c\n{ a 1; } }\n",
        ("p", "d"),
        "c",
    ),
    (
        "with-neighbours",
        "before 1;\nd // c\n{\n    a 1;\n}\nafter 2;\n",
        ("d",),
        "c",
    ),
    (
        "comment-with-brackets",
        "d // air (293 K), see {a}; b\n{\n    a 1;\n}\n",
        ("d",),
        "air (293 K), see {a}; b",
    ),
]
LIST_ROWS = [
    ("list", "x // c\n(\n    1\n);\n", ("x",), "c"),
    ("list-no-space", "x //c\n(\n    1\n);\n", ("x",), "c"),
    ("list-tab", "x\t// c\n(\n    1\n);\n", ("x",), "c"),
    (
        "list-inside-a-dict",
        "p\n{\n    x // c\n    (\n        1\n    );\n}\n",
        ("p", "x"),
        "c",
    ),
]
CONTAINERS = ["top", "sub"]


def _params(rows):
    return [
        pytest.param(text, path, comment, cont, id=f"{rid}-{cont}")
        for rid, text, path, comment in rows
        for cont in CONTAINERS
    ]


ARGS = "text, path, comment, cont"
ALL = _params(DICT_ROWS) + _params(LIST_ROWS)


def _entry(d, path, cont):
    node = _scope(d, cont)
    for name in path:
        node = getattr(node, name)
    return node


def _keyword_lines(text, keyword, comment):
    """Lines of `text` that hold the comment text and the keyword, `//` aside."""
    return [
        ln
        for ln in text.splitlines()
        if "//" in ln
        and comment in ln
        and re.sub(r"//.*", "", ln).split()[-1:] == [keyword]
    ]


@pytest.mark.parametrize(ARGS, ALL)
def test_loads_under_the_plain_keyword_with_its_entries(
    tmp_path, text, path, comment, cont
):
    first = _read_write(tmp_path, _wrap(text, cont))[0]
    parent = _entry(first, path[:-1], cont)
    assert path[-1] in _all_keys(parent)
    assert not any("//" in k for k in _all_keys(parent))
    entry = getattr(parent, path[-1])
    if path[-1] == "x":
        assert _leaves(entry) == [1.0]
    else:
        assert _all_keys(entry) == ["a"]
        assert entry.a.value == 1


@pytest.mark.parametrize(ARGS, ALL)
def test_comment_is_written_on_the_keyword_line(tmp_path, text, path, comment, cont):
    first, _, text1, _ = _read_write(tmp_path, _wrap(text, cont))
    assert path[-1] in _all_keys(_entry(first, path[:-1], cont))
    assert _keyword_lines(text1, path[-1], comment), text1


@pytest.mark.parametrize(ARGS, ALL)
def test_reread_gives_the_same_keys(tmp_path, text, path, comment, cont):
    first, second, _, _ = _read_write(tmp_path, _wrap(text, cont))
    assert path[-1] in _all_keys(_entry(first, path[:-1], cont))
    assert _shape(first) == _shape(second)


@pytest.mark.parametrize(ARGS, ALL)
def test_second_write_equals_the_first(tmp_path, text, path, comment, cont):
    first, _, text1, text2 = _read_write(tmp_path, _wrap(text, cont))
    assert path[-1] in _all_keys(_entry(first, path[:-1], cont))
    assert text1 == text2


# --- no loaded key contains `//` ---------------------------------------------------------------
KEYWORDS = ["d", "mixture", "x_1"]
SEPARATORS = [" ", "", "\t", "    "]
COMMENTS = ["c", "air at room temperature (293 K)", "a // b", "a { b", "x;y", "", "*/"]
BRACKETS = [("{", "a 1;", "}"), ("(", "1", ");")]


def _property_inputs():
    out = []
    for kw in KEYWORDS:
        for sep in SEPARATORS:
            for comment in COMMENTS:
                for o, body, c in BRACKETS:
                    text = f"{kw}{sep}//{' ' if comment else ''}{comment}\n{o}\n    {body}\n{c}\n"
                    out.append(text)
    return out


PROPERTY = _property_inputs()


def _walk_keys(d):
    for k in _all_keys(d):
        yield k
        v = getattr(d, k)
        if isinstance(v, fkt.ofDict):
            yield from _walk_keys(v)


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize(
    "text", [pytest.param(t, id=repr(t)) for t in PROPERTY[::17]] + [PROPERTY[0]]
)
def test_no_loaded_key_contains_slashes_or_the_load_fails_loudly(tmp_path, text, cont):
    full = _wrap(text, cont)
    path = tmp_path / "prop"
    path.write_text(HEADER + full)
    try:
        d = _load(path)
    except FoamKitError as err:
        assert "prop" in str(err), err
        assert re.search(rf"\bline ({_span(full)})\b", str(err), re.IGNORECASE), err
        return
    assert not any("//" in k for k in _walk_keys(d)), list(_walk_keys(d))


# --- the real files ---------------------------------------------------------------------------------
def _source_comments(path):
    """Text of every `//` comment after the banner line of the file header."""
    body = re.split(
        r"^// \* \* \*[^\n]*\n", path.read_text(), maxsplit=1, flags=re.MULTILINE
    )[-1]
    out = []
    for ln in body.splitlines():
        m = re.search(r"//\s*(.*\S)", ln)
        if m and not m.group(1).startswith(("*", "**")):
            out.append(m.group(1))
    return out


def test_real_files_have_lf_line_endings_only():
    for p in (PHYSICAL, BAFFLES, RADIATION):
        assert b"\r" not in p.read_bytes()


def test_real_physical_properties_loads_with_mixture_key():
    d = _load(PHYSICAL)
    # (a missing attribute reads as None, hence the key check first)
    assert _all_keys(d) == ["thermoType", "mixture"]
    assert _all_keys(d.mixture) == ["specie", "thermodynamics", "transport"]
    assert d.mixture.specie.molWeight.value == pytest.approx(28.9)


def test_real_baffles_dict_loads_with_baffles_group_key():
    d = _load(BAFFLES)
    assert _all_keys(d) == ["internalFacesOnly", "baffles"]
    assert _all_keys(d.baffles) == ["bafflesGroup"]
    assert d.baffles.bafflesGroup.type.value == "faceZone"


def test_real_radiation_properties_raises_for_the_comments_after_list_items():
    """The keyword-line comments load, but the comments after the items (T-057) would be
    dropped on write: that is a FoamKitError naming the file and the line, not a silent loss."""
    with pytest.raises(FoamKitError) as err:
        _load(RADIATION)
    message = str(err.value).replace(chr(10), "")
    assert "radiationProperties" in message
    assert "Line 42 " in message, message
    assert "T-057" in message


@pytest.mark.parametrize("path", [PHYSICAL, BAFFLES], ids=lambda p: p.name)
def test_real_file_round_trip_keeps_every_comment(tmp_path, path):
    d = _load(path)
    assert not any("//" in k for k in _walk_keys(d))
    text1 = d.toString()
    for comment in _source_comments(path):
        assert comment in text1, comment
    out = tmp_path / path.name
    out.write_text(text1)
    assert _shape(_load(out)) == _shape(d)
    assert _load(out).toString() == text1


def test_list_with_comment_after_keyword_and_own_line_comments_loads(tmp_path):
    text = "x // c\n(\n    // own line\n    1\n    2\n);\n"
    first, second, text1, text2 = _read_write(tmp_path, text)
    assert _all_keys(first) == ["x"]
    assert "x // c" in text1 and "own line" in text1
    assert text1 == text2


def test_list_with_comment_after_an_item_raises_with_the_line(tmp_path):
    path = tmp_path / "items"
    path.write_text(HEADER + "x // c\n(\n    1 // one\n    2\n);\n")
    with pytest.raises(FoamKitError) as err:
        _load(path)
    message = str(err.value).replace("\n", "")
    assert "items" in message
    assert f"Line {HL + 3}" in message
    assert "T-057" in message


def test_unclosed_brace_inside_a_verbatim_body_is_not_cut(tmp_path):
    """The `{` that opens mid-line inside a `#codeStream { ... }` body is not split off."""
    path = tmp_path / "verb"
    path.write_text(HEADER + "c #codeStream\n{\n    x { y 1;\n}\n")
    parser = fkt.DictFileParser(path)
    before = list(parser.lines)
    try:
        parser._splitEntries()
    except FoamKitError:
        pass
    assert parser.lines == before


def test_real_files_pinned_in_brace_scan():
    """The three files are in REAL_OUTCOMES (tests/test_brace_scan.py); T-055 updates it."""
    text = (TESTS / "test_brace_scan.py").read_text()
    for p in (PHYSICAL, BAFFLES, RADIATION):
        assert f'"{p.name}"' in text


# --- guards: behave as today ---------------------------------------------------------------------
@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.parametrize(
    ("text", "leaves"),
    [
        pytest.param("d\n{\n    a 1;\n}\n", None, id="dict"),
        pytest.param("x\n(\n    1\n);\n", [1.0], id="list"),
    ],
)
def test_keyword_without_comment_round_trips(tmp_path, text, leaves, cont):
    key = text[0]
    first, second, text1, text2 = _read_write(tmp_path, _wrap(text, cont))
    for d in (first, second):
        assert key in _all_keys(_scope(d, cont))
        entry = getattr(_scope(d, cont), key)
        if leaves is None:
            assert entry.a.value == 1
        else:
            assert _leaves(entry) == leaves
    assert text1 == text2


@pytest.mark.parametrize("cont", CONTAINERS)
def test_comment_on_its_own_line_before_a_keyword_is_kept(tmp_path, cont):
    text = "// c\nd\n{\n    a 1;\n}\n"
    first, second, text1, text2 = _read_write(tmp_path, _wrap(text, cont))
    for d in (first, second):
        assert _all_keys(_scope(d, cont)) == ["d"]
        assert _scope(d, cont).d.a.value == 1
    assert "// c" in text1
    assert text1 == text2


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.usefixtures("regenerated_style")
def test_quoted_keyword_with_slashes_loads_and_is_written_quoted_as_today(
    tmp_path, cont
):
    """Characterisation only (T-036): the key is kept with its quotes and the entries of
    the block are written back; no fix is asserted."""
    text = '"a//b"\n{\n    a 1;\n}\n'
    _, _, text1, text2 = _read_write(tmp_path, _wrap(text, cont))
    assert '"a//b"' in text1
    assert "a           1;" in text1
    assert text1 == text2


@pytest.mark.parametrize("cont", CONTAINERS)
@pytest.mark.usefixtures("regenerated_style")
def test_comment_after_closing_brace_loads_and_is_dropped_as_today(tmp_path, cont):
    """Characterisation only (T-056): `d { a 1; } // c` loads as `d` with `a`, and the
    trailing comment is not written back."""
    text = "d { a 1; } // c\nb 2;\n"
    first, _, text1, text2 = _read_write(tmp_path, _wrap(text, cont))
    scope = _scope(first, cont)
    assert _all_keys(scope) == ["d", "b"]
    assert scope.d.a.value == 1
    assert "// c" not in text1
    assert text1 == text2
