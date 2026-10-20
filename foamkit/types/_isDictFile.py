import logging
import re
from pathlib import Path
from foamkit import getFoamKitConfig

logger = logging.getLogger('foamkit')

#- Bytes that may appear in a text file; ref: https://stackoverflow.com/a/7392391
_TEXT_CHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})

_BANNER_START = \
    '/*--------------------------------*- C++ -*----------------------------------'
_BANNER_LINES = ('=========', '\\\\      /  F ield', '\\\\    /   O peration',
                 '\\\\  /    A nd', '\\\\/     M anipulation')

#- Header-less files: how much of the text is searched for the FoamFile block
_FOAMFILE_SCAN_LIMIT = 4096
_FOAMFILE_KEY = re.compile(r'(?:^|[\s;{])(?:class|format)\s')


def _hasHeaderlessFoamFile(text):
    """
    Checks if `text` starts (after blank lines) with a `FoamFile { ... }` block
    that contains a `class` or `format` entry.  Only the first
    `_FOAMFILE_SCAN_LIMIT` characters are examined, and an unterminated block
    is rejected.
    """
    head = text[:_FOAMFILE_SCAN_LIMIT]
    #- Start of the first non-blank line (indentation is not skipped)
    start = head.rfind('\n', 0, len(head) - len(head.lstrip())) + 1
    if not head.startswith('FoamFile', start):
        return False
    after = start + len('FoamFile')
    #- The keyword must be followed by whitespace: `FoamFile{` is not parsed
    if after < len(head) and not head[after].isspace():
        return False
    brace = len(head) - len(head[after:].lstrip())
    if brace >= len(head) or head[brace] != '{':
        return False
    end = head.find('}', brace)
    eol = head.find('\n', brace)
    #- `{` ends its line, and the first `}` starts its own line
    if end < 0 or not 0 <= eol < end or head[brace + 1:eol].strip():
        return False
    if head[head.rfind('\n', 0, end) + 1:end].strip():
        return False
    #- Only `;` and/or a `//` comment may follow the `}` on its line
    eol = text.find('\n', end)
    tail = text[end + 1:eol if eol >= 0 else len(text)]
    if tail.startswith(';'):
        tail = tail[1:]
    tail = tail.strip()
    if tail and not tail.startswith('//'):
        return False
    return _FOAMFILE_KEY.search(head, brace, end) is not None


def _isDictFile(file):
    """
    Checks if the argument file is an OpenFOAM dictionary file.  It is assumed
    that all OpenFOAM dictionary files start with a block comment header of the
    form:

/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  6
     \\\\/     M anipulation  |
-------------------------------------------------------------------------------
Description
    {Description of file contents}...

\\\\*---------------------------------------------------------------------------*/

    Files larger than the `dict_filesize_limit` config value, binary files and
    files that are not valid UTF-8 are rejected.  The search for the header
    uses whole-string operations rather than a Python loop over the lines, as
    this check runs for every file in a case.

    Parameters:
        file (str or Path):  The path of the file to test.
    """
    file = Path(file)

    logger.debug("Checking file: %s", file)

    if file.is_dir():
        return False

    #- Skip large files
    if file.stat().st_size > int(getFoamKitConfig('dict_filesize_limit')):
        return False

    data = file.read_bytes()

    #- check for binary
    if data[:1024].translate(None, _TEXT_CHARS):
        return False

    try:
        text = data.decode('utf8')
    except UnicodeDecodeError:
        return False
    #- Universal newlines, as when reading the file in text mode
    if '\r' in text:
        text = text.replace('\r\n', '\n').replace('\r', '\n')

    isDictFile = False

    #- The banner starts at the first line beginning with '/*' and must be
    #  followed by at least seven more lines.  (`str.find` is much faster
    #  than a multiline regex on large files.)
    if text.startswith('/*'):
        start = 0
    else:
        start = text.find('\n/*')
        start = start + 1 if start >= 0 else None
    if start is not None:
        block = text[start:].split('\n', 7)
        if (len(block) == 8 and block[7] != ''
                and block[0].startswith(_BANNER_START)
                and all(s in l for s, l in zip(_BANNER_LINES, block[1:6]))):
            isDictFile = True

    #- Header-less file that starts directly with a FoamFile block
    if not isDictFile:
        isDictFile = _hasHeaderlessFoamFile(text)

    if isDictFile:
        logger.debug("'%s' is an OpenFOAM dictionary file.", file)
    else:
        logger.debug("'%s' is not an OpenFOAM dictionary file.", file)

    return isDictFile
