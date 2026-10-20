"""Include directives (`#include`, `#sinclude`, `#includeIfPresent`, ...) on read and write (T-004)."""

import pytest

import foamkit.types as fkt
from foamkit import FoamKitError
from conftest import FIXTURES

HEADER = (
    (FIXTURES / "pitzDaily" / "system" / "controlDict")
    .read_text()
    .split("application")[0]
)
# - Built inline, not stored under tests/fixtures: test_golden.py globs that tree
# - and would require a golden file recording the (currently wrong) output.
MIXED_BODY = (
    '#include "mandatory"\n\n'
    '#sinclude "optionalEsi"\n\n'
    '#includeIfPresent "optionalFoundation"\n\n'
    '#includeEtc "caseDicts/setConstraintTypes"\n\n'
    "#includeFunc streamlines\n\n"
    "nx 10;\n"
)


def _mixed(tmp_path):
    path = tmp_path / "includeDirectives"
    path.write_text(HEADER + MIXED_BODY)
    return fkt.DictFileParser(path).readDictFile()


def _roundtrip(tmp_path, body):
    """Parse `body` (after a standard header), write it out, and return both dicts and text."""
    src = tmp_path / "src"
    src.write_text(HEADER + body)
    first = fkt.DictFileParser(src).readDictFile()
    text = first.toString()
    out = tmp_path / "out"
    out.write_text(text)
    second = fkt.DictFileParser(out).readDictFile()
    return first, second, text


def _directive_lines(text):
    """Directive lines as whitespace-normalised strings, in file order."""
    return [
        " ".join(line.split())
        for line in text.splitlines()
        if line.lstrip().startswith("#")
    ]


def _keywords(text):
    return [line.split()[0] for line in _directive_lines(text)]


# --- characterization: behaviour that is correct today ----------------------


@pytest.mark.parametrize(
    "line, cls",
    [
        ('#include "a"', fkt.ofInclude),
        ('#includeEtc "caseDicts/setConstraintTypes"', fkt.ofIncludeEtc),
        ("#includeFunc streamlines", fkt.ofIncludeFunc),
    ],
)
def test_known_include_parses_to_its_type(tmp_path, line, cls):
    first, _, _ = _roundtrip(tmp_path, f"{line}\n\nx 1;\n")
    incl = next(v for v in vars(first).values() if isinstance(v, fkt.ofInclude))
    assert type(incl) is cls


@pytest.mark.parametrize(
    "line, written",
    [
        ('#include "a"', '#include "a"'),
        (
            '#includeEtc "caseDicts/setConstraintTypes"',
            '#includeEtc "caseDicts/setConstraintTypes"',
        ),
        # T-015 (option A): unquoted input is written back unquoted.
        ("#includeFunc streamlines", "#includeFunc streamlines"),
    ],
)
def test_known_include_round_trips(tmp_path, line, written):
    first, second, text = _roundtrip(tmp_path, f"{line}\n\nx 1;\n")
    assert _directive_lines(text) == [written]
    assert second.toString() == text


def test_include_value_has_no_quotes(tmp_path):
    first, _, _ = _roundtrip(tmp_path, '#include "a"\n\nx 1;\n')
    assert first.include0.value == "a"


def test_known_includes_keep_their_keywords_in_mixed_file(tmp_path):
    """The three keywords that work today stay in the fixture's output, in order."""
    text = _mixed(tmp_path).toString()
    kws = _keywords(text)
    assert kws[0] == "#include"
    assert "#includeEtc" in kws
    assert "#includeFunc" in kws


# --- specification: T-004 acceptance criteria -------------------------------


@pytest.mark.parametrize("keyword", ["#sinclude", "#includeIfPresent"])
def test_optional_include_keeps_its_keyword(tmp_path, keyword):
    _, _, text = _roundtrip(tmp_path, f'{keyword} "a"\n\nx 1;\n')
    assert _directive_lines(text) == [f'{keyword} "a"']


@pytest.mark.parametrize("keyword", ["#sinclude", "#includeIfPresent"])
def test_optional_include_second_write_is_stable(tmp_path, keyword):
    _, second, text = _roundtrip(tmp_path, f'{keyword} "a"\n\nx 1;\n')
    assert second.toString() == text
    assert _keywords(text) == [keyword]


@pytest.mark.parametrize("keyword", ["#sinclude", "#includeIfPresent"])
def test_optional_include_keeps_its_value(tmp_path, keyword):
    """The path is not lost or re-quoted when the keyword is preserved."""
    first, _, _ = _roundtrip(tmp_path, f'{keyword} "some/path"\n\nx 1;\n')
    incl = next(v for v in vars(first).values() if isinstance(v, fkt.ofInclude))
    assert incl.value == "some/path"


@pytest.mark.parametrize("keyword", ["#includeFoo", "#includeModel", "#includeFooBar"])
def test_unknown_include_keyword_is_kept(tmp_path, keyword):
    """Any other `#include*` keyword is never rewritten to `#include`."""
    _, _, text = _roundtrip(tmp_path, f'{keyword} "c"\n\nx 1;\n')
    assert _directive_lines(text) == [f'{keyword} "c"']


def test_mixed_directives_keep_every_keyword_in_order(tmp_path):
    d = _mixed(tmp_path)
    assert _keywords(d.toString()) == [
        "#include",
        "#sinclude",
        "#includeIfPresent",
        "#includeEtc",
        "#includeFunc",
    ]


def test_mixed_directives_are_stable_on_rewrite(tmp_path):
    first = _mixed(tmp_path)
    text = first.toString()
    out = tmp_path / "out"
    out.write_text(text)
    assert fkt.DictFileParser(out).readDictFile().toString() == text


def test_mixed_directives_keep_following_entries(tmp_path):
    d = _mixed(tmp_path)
    assert d.nx.value == 10


@pytest.mark.parametrize("arg", ["streamlines(U)"])
def test_includeFunc_with_arguments_round_trips_unchanged(tmp_path, arg):
    _, _, text = _roundtrip(tmp_path, f"#includeFunc {arg}\n\nx 1;\n")
    assert _directive_lines(text) == [f"#includeFunc {arg}"]


def test_includeFunc_with_named_arguments_round_trips(tmp_path):
    line = "#includeFunc streamlines(U, name=s)"
    _, _, text = _roundtrip(tmp_path, f"{line}\n\nx 1;\n")
    assert _directive_lines(text) == [line]


# --- review follow-ups -------------------------------------------------------


@pytest.mark.parametrize(
    "keyword", ["#include-x", "#include.x", "#include_x", "#include2"]
)
def test_include_keyword_with_word_characters_is_kept(tmp_path, keyword):
    """ASCII OpenFOAM word characters in an `#include*` keyword round-trip verbatim."""
    _, second, text = _roundtrip(tmp_path, f'{keyword} "a"\n\nx 1;\n')
    assert _directive_lines(text) == [f'{keyword} "a"']
    assert second.toString() == text


@pytest.mark.parametrize(
    "keyword", ["#include$x", "#include;x", "#include(x", "#include{x"]
)
def test_malformed_include_keyword_raises_foamkit_error(tmp_path, keyword):
    """Tokens that cannot be a word must give FoamKitError, never KeyError."""
    path = tmp_path / "bad"
    path.write_text(HEADER + f'{keyword} "a"\n\nx 1;\n')
    with pytest.raises(FoamKitError, match="Unknown directive"):
        fkt.DictFileParser(path).readDictFile()


def test_non_ascii_include_keyword_raises_foamkit_error(tmp_path):
    """Chosen behaviour: non-ASCII is not a valid OpenFOAM word, so loading fails cleanly."""
    path = tmp_path / "bad"
    path.write_text(HEADER + '#includeétc "a"\n\nx 1;\n', encoding="utf-8")
    with pytest.raises(FoamKitError, match="Unknown directive"):
        fkt.DictFileParser(path).readDictFile()


def test_include_dict_keys_are_numbered_per_keyword(tmp_path):
    first, _, _ = _roundtrip(tmp_path, '#sinclude "a"\n\n#include "b"\n\nx 1;\n')
    assert "sinclude0" in vars(first)
    assert "include0" in vars(first)
    assert first.sinclude0.value == "a"
    assert first.include0.value == "b"


def test_include_if_present_dict_key(tmp_path):
    first, _, _ = _roundtrip(tmp_path, '#includeIfPresent "a"\n\nx 1;\n')
    assert "includeIfPresent0" in vars(first)


@pytest.mark.parametrize("cls", [fkt.ofIncludeEtc, fkt.ofIncludeFunc])
def test_fixed_keyword_subclasses_reject_keyword_change(cls):
    obj = cls("a")
    before = obj.toString()
    with pytest.raises(AttributeError):
        obj.keyword = "#sinclude"
    assert obj.toString() == before
