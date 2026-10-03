from ..functions import isDictFile
import os
import sys
from pathlib import Path

import logging

log = logging.getLogger("foamkit")

_entryList = []


def _readDictFile(file):
    """
    Reads an OpenFOAM dictionary file and stores values in a python dictionary.

    Parameters:
        file (str or Path): The OpenFOAM dictionary file to read.
    """
    #from of.ofTypes import ofDictFile, ofDict, ofList, ofIntValue, ofFloatValue, ofStrValue

    #- Function assumes:
    #   - All entries start on a new line
    #   - Comments on line after C++ code are ignored

    #pyOFDict = ofDictFile(os.path.basename(file), [])

    if not isDictFile(file):
        raise Exception("File is not a valid OpenFOAM dictionary file:"
                        f"\n{file}")

    def functionSwitcher(status):
        switcher = {
            'commentedBlock': _getOFDictCommentLineType,
            'comment': None,
            'includeLine': None,
            'empty': None,
            'commentedBlockEnd':  _parseLine,
            'list': _getOFDictValueType,
            'dict': _getOFDictValueType,
            'value': _storeOFDictValue,
            'multiLineUnknown': _getOFDictEntryType,
            'dictName': _newOFDictDict,
            'listName': _newOFDictList,
            'multiLineValue': _appendOFDictEntry,
            'multiLineEntryStart': _storeOFDictMultiLineEntryName,
            'singleLineSingleValuedEntry': _storeOFDictSingleLineSingleValuedEntry
        }
        return switcher.get(status, _parseLine)

    status = {
        'inBlockComment': False,
        'inDict': 0,
        'inList': 0,
        'multiLineEntryStart': False
    }

    pyDict = {}

    # - Parse the file line by line for data
    with open(file) as f:
        lines = f.readlines()
        for line in lines:
            line = line.lstrip().rstrip()
            if status['inBlockComment']:
                if line.rstrip()[-2:] == '*/':
                    status['inBlockComment'] = False
                continue
            if status['inList']:
                pass
            if status['inDict']:
                pass
            if status['multiLineEntryStart']:
                pass
            # - Check for block comment
            if line[:1] == '/*':
                status['inBlockComment'] = True
                continue
            # - Check for line comment
            if line[:1] == '//':
                continue
            # - Check for include statement
            if line.startwith('#includeEtc'):
                pyDict.update

            # - Check for single line entry
            # - Check for multi-line entry


def _readDictEntry(status, ofType, lines, i):

    #- Function assumes:
    #   - All entries start on a new line
    #   - Comments on line after C++ code are ignored

    #pyOFDict = ofDictFile(os.path.basename(file), [])

    def functionSwitcher(status):
        switcher = {
            'commentedBlock': _getOFDictCommentLineType,
            'comment': None,
            'includeLine': _storeInclude,
            'empty': None,
            'commentedBlockEnd':  _parseLine,
            'list': _getOFDictValueType,
            'dict': _getOFDictValueType,
            'value': _storeOFDictValue,
            'multiLineUnknown': _getOFDictValueType,
            'startDict': _readDictEntry, # _newOFDictDict,
            'startList': _readList, # _newOFDictList,
            'multiLineValue': _appendOFDictEntry,
            'multiLineEntryStart': _storeOFDictMultiLineEntryName,
            'singleLineSingleValuedEntry': _storeOFDictSingleLineSingleValuedEntry
        }
        return switcher.get(status, _parseLine)

    def _argSwitcher(func, line, ofType):
        switcher = {
            _parseLine: len(line.split(" ")),
            _storeOFDictValue: (ofType,
                                line[1:].remove('{()}').split(" ")
                               )
        }
        return switcher.get(func, line.remove['()'])

    attempts = 0
    while status != 'endDict':
        attempts +=1
        if attempts > 1000:
            log.error("Error reading dictionary file.  Maximum lines exceeded")
            sys.exit()

        func = functionSwitcher(status)
        [status, lineStatus] = func(_argSwitcher(func, lines[i], ofType))

        i += 1



def _readDictFile(file):

    status = 'start'
    ofType = None
    prevLine = None
    lineStatus = 'read'
    level = 0

    dictFile = open(file, 'r')
    lines = dictFile.readlines()

    i = _findEndOfHeader(file)

    attempts = 0
    while True:
        attempts += 1
        if attempts > 1000:
            log.error("Error reading dictionary file.  Maximum lines exceeded")
            sys.exit()
        if i >= len(lines):
            break

        [status, value, i] = _parseLine(lines, i, status)

        if value is not None:
            _entryList.append(value)

        # [status, lineStatus] = _readDictEntry(status, ofType, lines, i)

        i += 1

    return ofDictFile(_entryList,
                      location=Path(file).parent, filename=Path(file).name
                     )

    # with open(file, 'r') as f:
    #     lines = f.readlines()
    #     for i, line in enumerate(lines):
    #         if line.startswith(('//', '#')):
    #             #- Ignore line comments and includes
    #             continue
    #         if lineStatus == 'endMultiLine':
    #             #- Determine how to interpret the previous line
    #             [status, lineStatus] = _getOFDictMultiLinePreviousType(line)
    #         lineStatus = 'read'
    #         count = 0
    #         while lineStatus != 'end':
    #             if lineStatus == 'endMultiLine':
    #                 prevLine = line
    #                 break
    #             count += 1
    #             if count >= 100: #prevent infinite loop in case of error
    #                 raise Exception("Maximum number of loops reached.")
    #             #func = functionSwitcher(status)
    #             # if func is not None
    #                 #[status, lineStatus] = func(_argSwitcher(func, line, ofType))
    #             [status, lineStatus] = _readDictEntry(
    #                                         status, ofType, lines, i
    #                                     )


def _getOFDictCommentLineType(startsWith):
    switcher = {
        '*/': ['commentedBlockEnd', 'end']
    }
    return [switcher.get(startsWith, 'commentedBlock'), 'end']


def _getOFDictValueType(startsWith):
    switcher = {
        '(': 'list',
        '{': 'dict'
    }
    return [switcher.get(startsWith, 'value'), 'read']


def _getOFDictMultiLineEntryType(line):
    switcher = {
        '(': 'list',
        '{': 'dict',
        'FoamFile': 'fileInfoStart'
    }
    return [switcher.get(line, 'value'), 'read']


def _ofMultiLineEntryReadNextLine(line):
    pass


# TODO: Handle case of multiLineEntry with more than 1 word on  first line.
def _parseLine(lines, i, status):
    # switcher = {
    #     "parse": ,
    #     : ['multiLineUnknown', 'readMultiLine'],
    #     2: ['singleLineSingleValuedEntry', 'read']
    # }

    lineList = lines[i].split(" ")

    if len(lineList) == 0:
        # Line is blank
        return [status, None]
    elif len(lineList) == 1:
        listOrDictName = lines[i].lstrip(" ").rstrip(" ")
        return _parseListOrDict(listOrDictName)
    elif len(lineList) == 2:
        return _parseLineLenTwo(lineList, status), i
    else:  # Multiple value entry
        return _parseLineLenGreaterThanTwo(lines, status)

    return switcher.get(length, ['singleLineMultiValuedEntry', 'read'])


def _parseLineLenTwo(lineList, status):
    if lineList[1].startwith('#include'):
        # Found include statement
        return _parseIncludes(lineList[0], lineList[1].rstrip(';'))
    if lineList[1][-1] == ';':
        # Found single line entry
        return _parseSingleLineEntry(lineList[0], lineList[2].rstrip(';'))


def _parseIncludes(key, value):
    """
    Extract value as the appropriate include type
    """

    if key == '#includeEtc':
        return ['parse', ofIncludeEtc(value)]
    elif key == '#includeFunc':
        return ['parse', ofIncludeFunc(value)]
    else:
        return 'parse', ofInclude(value)


def _parseSingleLineEntry(key, value):
    """
    Extract the vlaue as the approriate ofTypes

    Search order:
        - ofFloat, ofInt, ofBool, ofStr
    """
    try:
        v_ = float(value)
        return ['parse', ofFloat(v_, name=key)]
    except ValueError:
        try:
            v_ = int(value)
            return ['parse', ofInt(v_, name=key)]
        except ValueError:
            try:
                v_ = bool(value)
                return ['parse', ofBool(v_, name=key)]
            except ValueError:
                return 'parse', ofStr(value, name=key)

def _parseLineLenGreaterThanTwo(lineList, status):

    # - find the entry type
    for i, char in enumerate(line):
        if char == '{' or char == '(':
            entryName = line[:i].lstrip().rstrip()
            valueList = line[i:].split(" ").rstrip(char+';')
            break

        if entryName:
            _parseListOrDict(entryName)
        else:
            log.error("Invalid syntax found on lin")

    bracket


def _storeOFDictValue(line):
    pass


def _appendOFDictEntry(line):
    pass


def _storeOFNamedListValue(line):
    pass


def _getMultiLineType(line):
    switcher = {
        '{': 'startDict',
        '(': 'startList'

    }

    typeSwitcher = {
        '{': ofDict(),
        '(': ofList()
    }

    _entryList[_entryList.keys[-1]] = typeSwitcher.get(line)

    return [switcher.get(line, 'multiLineValue'), 'read']


def _storeOFDictSingleLineSingleValuedEntry(line):
    values = line.split(" ")
    if len(values) != 2:
        raise Exception("Not able to process line format.")
    if values[1].isnumeric() is True:
        if '.' in values[1]:
            pyOFDict.add(ofFloatValue(values[0], values[1]))
        else:
            pyOFDict.add(ofIntValue(values[0], values[1]))
    elif values[1] in OF_BOOL_VALUES:
        pyOFDict.add(ofBoolValue(values[0], values[1]))
    else:
        pyOFDict.add(ofStrValue(values[0], values[1]))

    return ['newLine', 'end']

def _storeOFDictMultiLineEntryName(line):
    _currentEntryKey = line
    _entryList.update({line: None})

def _ofDictFindBlockEntryStartStop(file, blockList, searchValues=False):
    #TODO:  Account for the case of opening and closing parenthesis or brackets
    #  on the same line.
    relPath = file
    file = os.path.join(os.getcwd(), file)

    if os.path.isfile(file) is False:
        raise FileNotFoundError(file)

    copyfile(file, file+"_old")

    start = 0
    stop = 0

    try:
        old = open(file, 'r')
        for line in old:
            stop+=1
        old.seek(0)
        lines = old.readlines()

        if stop <= 0:
            raise Exception('File is empty: '+file)

        if blockList is not None:

            for block in blockList:
                #- initialize variables to be defined below
                openStr = None
                closeStr = None

                #old.seek(start-1)

                # while 'block' is not the first word in the line:
                while True:
                    lineList = lines[start].strip().split(" ")
                    if block == lineList[0]:
                        break
                    start += 1
                    if start >= stop:
                        log.warning("End of file '"+relPath+"' reached "\
                                "without finding a match for block '"+\
                                str(block)+"'.")
                        return None, stop-1
                for i in [0,1]: #search line with block name and next line
                    if len(lines[start+i].split(" ")) > 1:
                        #- Search for opening and closing of block on the same line
                        for openChar, closeChar in zip(['(', '{'],[')', '}']):
                            if openChar in lines[start+i]:
                                openStr = openChar
                                closeStr = closeChar
                                start = start+i
                                break
#                                if closeStr in lines[start+i]:
#                                    print("Warning:  No values found matching block '"+block+"' within "+file)
                #- If block is not opened on same line assume it is opened on next
                #  line:
                if not openStr:
                    start+=1
                    openStr = lines[start].lstrip()[0]

                if openStr == '(':
                    closeStr = ')'
                elif openStr == '{':
                    closeStr = '}'
                else:
                    raise Exception("Unexpected file format enountered at line "+str(start+1)+" of "+file)
                stop = start

                nOpenStr = 1
                nCloseStr = 0

                while nOpenStr > nCloseStr:
                    if stop >= len(lines)-1:
                        raise Exception("End of file '"+relPath+"' reached without terminating block.")
                    stop+=1
                    nOpenStr+= lines[stop].count(openStr)
                    nCloseStr+= lines[stop].count(closeStr)
            start+=1
        else:  #Search top level.  Find end of file
            if len(lines) > 0:
                start = len(lines)-1
                stop = len(lines)-1
            else:
                start = 0
                stop = 0

    except:
        copyfile(file+"_old", file)
        raise

    return start, stop

def _findEndOfDict(file):
    """
    Returns the line number of an OpenFOAM dictionary corresponding to the
    whitespace after the last entry of the root dictionary.
    """
    #- TODO: Handle the case where a subdict of an existing dictionary is
    #  not found.

    endofDict = None

    with open(file) as f:
        lines = f.readlines()
        nLines = len(lines)
        for i, line in enumerate(reversed(lines)):
            #TODO:  This does not properly handle commented blocks at end of
            #       file.
            if (len(line.strip()) > 0 and
                any([line.lstrip()[:2] == c for c in ['//', '/*']]) is False):
                    endOfDict = nLines - i
                    break
    if endOfDict is None:
        endOfDict = _findEndOfHeader(file)

    log.debug('endofDict: '+str(endOfDict))

    return endOfDict

def _findEndOfHeader(file):
    foamFileFound = False
    with open(file) as f:
        for i, line in enumerate(f.readlines()):
            if line.strip() == 'FoamFile':
                foamFileFound = True
            if (foamFileFound and
                (line[:6] == '*\\----' or
                line[:6] == '// * *')):
                return i+1

    log.error('Invalid OpenFOAM file specified: '+str(file))
    sys.exit()
