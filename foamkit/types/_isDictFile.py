import logging
from pathlib import Path
from foamkit import getFoamKitConfig

logger = logging.getLogger('foamkit')

#- Bytes that may appear in a text file; ref: https://stackoverflow.com/a/7392391
_TEXT_CHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})

_BANNER_START = \
    '/*--------------------------------*- C++ -*----------------------------------'
_BANNER_LINES = ('=========', '\\\\      /  F ield', '\\\\    /   O peration',
                 '\\\\  /    A nd', '\\\\/     M anipulation')


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

    if isDictFile:
        logger.debug("'%s' is an OpenFOAM dictionary file.", file)
    else:
        logger.debug("'%s' is not an OpenFOAM dictionary file.", file)

    return isDictFile
