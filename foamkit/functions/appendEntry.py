import os

from .dictUtil import _appendBlockEntryWithLineNum, _appendBlockEntryWithBlockName, _findEndOfHeader, _findEndOfDict

def appendEntry(value, location, filename, blockList=None, lineNum=None, searchValues=False,
                insert=False, whitespace=False):
    """
    Append an ofType into a dictoinary file.

    Parameters
    ----------

    value: ofType
        The OpenFOAM value to append.

    blockList: list(str)
        The list of sub dictionaries into which the value is to appended.

    lineNum: int
        The line number at which to append the value.  This argument is ignored
        if 'blockList' is specified.

    insert: bool
        If `True`, the `value` is inserted at the beggining of the dictionary
        instead of appending to the end.

    """
    if blockList is not None:
        _appendBlockEntryWithBlockName(value, blockList,
                                       searchValues=searchValues,
                                       whitespace=whitespace)
    elif lineNum is not None:
        _appendBlockEntryWithLineNum(value, lineNum,
                                     searchValues=searchValues,
                                     whitespace=whitespace)
    else:
        #log.warning("Neither 'blockList' or 'lineNum' was specified."\
        #            "  Appending entry to end of dict")
        if insert:
            _appendBlockEntryWithLineNum(value,
                            _findEndOfHeader(os.path.join(
                                location, filename)),
                            searchValues=searchValues,
                            whitespace=whitespace
                            )
        else:
            _appendBlockEntryWithLineNum(value,
                    _findEndOfDict(os.path.join(location, filename)),
                    searchValues=searchValues,
                    whitespace=whitespace
                    )
