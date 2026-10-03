import os
import sys
from shutil import copyfile
import warnings

from foamkit.types import ofDictFile, ofDict, ofList, ofInt, ofFloat, \
    ofStr, ofBool, ofDimensionedScalar, ofVector, ofDimensionedVector, TAB_STR

import logging

log = logging.getLogger("foamkit")

def _appendBlockEntryWithBlockName(
    ofValue,
    blockList,
    searchValues=False,
    whitespace = False
):

    if ofValue.location is None or ofValue.filename is None:
        raise ValueError("The 'location' and 'filename' of the OpenFOAM type"\
                         " must be specified to update the dictionary file.")

    file = os.path.join(
            os.getcwd(),
            ofValue.location,
            ofValue.filename
    )

    #- Check if the file exists
    open(file)

    copyfile(file, file+"_old")

    start, stop = _ofDictFindBlockEntryStartStop(
        os.path.join(ofValue.location, ofValue.filename),
        blockList,
        searchValues=searchValues
    )

    if start is None: # if the block wasnt found:
        #TODO: This needs to be a recursive call to handle any number of
        #       subdictionaries
        start = _findEndOfDict(os.path.join(ofValue.location, ofValue.filename))
        parentDict = ofDict(name=blockList[-1], value=[],
                           location=ofValue.location, filename=ofValue.filename
                           )

        _appendBlockEntryWithLineNum(parentDict, start, whitespace=True)

        stop = start+ len(str(parentDict).split('\n'))
        start=stop # start at new dict whitespace

    verbose=True

    if hasattr(ofValue, 'name') is True and ofValue.name is not None:
        print("Appending entry '"+ofValue.name+"' into block "
              +blockList[len(blockList)-1]+" at line "+str(stop)+
              " of file: "+str(os.path.join(ofValue.location, ofValue.filename)))
        verbose=False
    else:
        print("Appending unnamed entry into block "+blockList[len(blockList)-1]+
              " at line "+str(stop)+" of file: "+
              str(os.path.join(ofValue.location, ofValue.filename)))

    _appendBlockEntryWithLineNum(ofValue, stop,
                             indent=len(blockList), whitespace=whitespace, verbose=verbose)

    #try:
        # with open(file+"_old") as old, open(file, "w") as new:
        #     for i, line in enumerate(old):
        #         if i == stop:
        #             #- build insert string with indents
        #             insertStr = ofValue.asString().split('\n')
        #             for i in range(len(blockList)):
        #                 for j in range(len(insertStr)):
        #                     insertStr[j] = TAB_STR + insertStr[j]
        #             #- Write lines
        #             for l in insertStr:
        #                 new.write(l+'\n')
        #             new.write(line)
        #         else:
        #             new.write(line)
    #except:
    #    copyfile(file+"_old", file)
    #    raise

def _replaceStringEntry(key, val, file, silent=False):
    #- Use "_ofDictReplaceEntry(...,rType='string')" instead
    found = False

    with open(file+"_old", 'r') as old, open(file, 'w') as new:
        for line in old:
            #if key in line:
            if key in line:
                found = True
            new.write(line.replace(key, str(val)))


    return found

def _replaceSingleLineEntry(ofValue, file, silent=False):
    #- Use "_ofDictReplaceEntry(...,rType='singleLine')" instead
    #- Replaces a single line based on OpenFOAM variable name
    #- WARNING: Does NOT search for variables of same name defined within
    #  different blocks.  A new nethod will need to be created if this search
    #  is needed.
    found = False

    key = ofValue.name
    string = ofValue.asString()
    logStr = ofValue.valueStr

    with open(file+"_old", 'r') as old, open(file, 'w') as new:

        for line in old:
            #if key in line:
            #if line.strip().startswith(key) is True:
            if (len(line.split()) > 0 and
                line.split()[0] == key):
                #- Ensure that the found key is a single lined value
                if line.split('//')[0].rstrip()[-1] != ';':
                    new.write(line)
                    continue
                #- Save any line comments:
                comment = ""
                if '//' in line:
                    commentList = line.split('//')[1:]
                    for c in commentList:
                        comment+='//'+c
                #- Count the number of leading spaces
                nSpaces = len(line) - len(line.lstrip(" "))
                pre = ''
                for _ in range(nSpaces):
                    pre += ' '
                new.write(pre+string+comment)
                found=True
                if not silent:
                    relPath = file[len(os.getcwd()):]
                    print("'"+str(key)+"' changed to '"+logStr+"' in file:  "+relPath)
                #print('in "if": '+str(key)+', '+str(val))
            else:
                new.write(line)
                #print('in "else": '+str(key)+', '+str(val))

    return found

def _findBlockEntryStartStop(file, blockList, searchValues=False):
    #TODO:  Account for the case of opening anf closing parenthesis or barackets
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
                    raise Exception("End of file '"+relPath+"' reached without finding a match for block '"+str(block)+"'.")
            for i in [0,1]: #search line with block name and next line
                if len(lines[start+i].split(" ")) > 1:
                    #- Search for opening and closing of block on the same line
                    for openChar, closeChar in zip(['(', '{'],[')', '}']):
                        if openChar in lines[start+i]:
                            openStr = openChar
                            closeStr = closeChar
                            start = start+i
                            break
                            if closeStr in lines[start+i]:
                                 print("Warning:  No values found matching block '"+block+"' within "+file)
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
    except:
        copyfile(file+"_old", file)
        raise

    return start, stop


def _appendBlockEntryWithLineNum(
    ofValue,
    lineNum,
    searchValues=False,
    indent=0,
    whitespace=False,
    verbose=True
):
    #- Not complete, use _ofDictAppendBlockEntryWithBlockName() instead

    file = os.path.join(
            os.getcwd(),
            ofValue.location,
            ofValue.filename
    )

    #- Check if the file exists
    open(file)

    copyfile(file, file+"_old")

    printName = ofValue.name or ""

    if verbose:
        print("Appending block '"+str(printName)+"' at line number "+str(lineNum)+
              " of file: "+os.path.join(ofValue.location, ofValue.filename))

    indentStr = ""
    for _ in range(indent):
        indentStr+=TAB_STR

    insertStr = ofValue.asString().split('\n')

    for j in range(len(insertStr)-1):
        insertStr[j] = indentStr+insertStr[j]

    insertStr = '\n'.join(insertStr)

    try:
        with open(file+"_old") as old, open(file, "w") as new:
            for i, line in enumerate(old):
                if i == lineNum:
                    if whitespace:
                        new.write('\n')
                    new.write(insertStr)
                    # if whitespace:
                    #     new.write('\n')
                    new.write(line)
                else:
                    new.write(line)
        os.remove(file+"_old")
    except:
        copyfile(file+"_old", file)
        raise

def _readDictFile(self, file):

    #- Function assumes:
    #   - All entries start on a new line
    #   - Comments on line after C++ code are ignored

    pyOFDict = ofDictFile(os.path.basename(file), [])

    def functionSwitcher(self, status):
        switcher = {
            'commentedBlock': self._getOFDictCommentLineType,
            'comment': None,
            'includeLine': None,
            'empty': None,
            'commentedBlockEnd':  self._getOFDictReadLineType,
            'list': self._getOFDictValueType,
            'dict': self._getOFDictValueType,
            'value': self._storeOFDictValue,
            'multiLineUnknown': self._getOFDictEntryType,
            'dictName': self._newOFDictDict,
            'listName': self._newOFDictList,
            'multiLineValue': self._appendOFDictEntry,
            'multiLineEntryStart': self._storeOFDictMultiLineEntryName,
            'singleLineSingleValuedEntry': self._storeOFDictSingleLineSingleValuedEntry
        }
        return switcher.get(status, self._getOFDictReadLineType)


    def _argSwitcher(func, line, ofType):
        switcher = {
            _getOFDictReadLineType: len(line.split(" ")),
            _storeOFDictValue: (ofType,
                                      line[1:].remove('{()}').split(" ")
                                     )
        }
        return switcher.get(func, line.remove['()'], )

    status = 'start'
    ofType = None
    prevLine = None
    lineStatus = 'read'
    level = 0
    with open(file, 'r') as f:
        for line in f:
            if line.startswith(('//', '#')):
                #- Ignore line comments and includes
                continue
            if lineStatus == 'endMultiLine':
                #- Determine how to interpret the previous line
                [status, lineStatus] = _getOFDictMultiLinePreviousType(line)
            lineStatus = 'read'
            count = 0
            while lineStatus != 'end':
                if lineStatus == 'endMultiLine':
                    prevLine = line
                    break
                count += 1
                if count >= 100: #prevent infinite loop in case of error
                    raise Exception("Maximum number of loops reached.")
                func = functionSwitcher(status)
                if func is not None:
                    [status, lineStatus] = func(_argSwitcher(func, line, ofType))



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

def _getOFDictReadLineType(length):
    switcher = {
        0: ['empty', 'end'],
        1: ['multiLineUnknown', 'readMultiLine'],
        2: ['singleLineSingleValuedEntry', 'read']
    }
    return switcher.get(length, ['singleLineMultiValuedEntry', 'read'])

def _storeOFDictValue(line):
    pass

def _appendOFDictValue(line):
    pass

def _storeOFNamedListValue(line):
    pass

def _getOFDictMultiLinePreviousType(line):
    switcher = {
        '{': 'dictName',
        '(': 'listName'
    }
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


def _ofDictFindBlockEntryStartStop(file, blockList, searchValues=False):
    #TODO:  Account for the case of opening anf closing parenthesis or brackets
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
