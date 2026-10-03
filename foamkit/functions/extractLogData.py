from pathlib import Path
from . import listCases
import re

import logging

log = logging.getLogger("foamkit")

def extractLogData(logFile, searchString, marker=['{','}'],
regex=False, logFileLabels = False, path=str(Path.cwd())):
    """
    Extract data from a log file.  Function parses each line of a log file and
    searches for strings that match the `searchString` pattern.

    Parameters:
        logFile (str):
            The file to search.

        searchString (str):
            The string to match.

        marker (list(str)):
            Bracket markers used to mark the return string.

        regex (bool):
            If `True`, returns the match of searchString from the `re.search()`
            function.  This option ignores the `marker` argument.

        logFileLabels (bool):
            if `True`, also returns a list of log filepath where each match
            was found.

    Returns:
        foundItems (list(str)):
            The values found in the log files.

    Example:
        Extract number of cells from log.checkMesh

        >>> import foamkit.functions as pf
        >>> pf.extractLogData('log.checkMesh', 'cells:            {}')
        ['48313773']


    """
    cases = listCases(path=path)
    foundItems = []
    logfileLabels = []
    for case in cases:
        logFilepath = Path(case) / logFile
        if logFilepath.is_file():
            logFileText = open(logFilepath, "r").read()
            if regex is False:
                #ignore any characters between markers
                searchString_ = searchString.split(marker[0])
                beforeMarkerString = searchString.split(marker[0])[0]
                log.debug('beforeMarkerString: "{}"'.format(beforeMarkerString))
                afterMarkerString = \
                searchString.split(marker[0])[-1].split(marker[1])[-1]
                if afterMarkerString == "":
                    afterMarkerString = "\n"
                log.debug('afterMarkerString: "{}"'.format(afterMarkerString))

                searchString_ = re.escape(beforeMarkerString) + '(.*?)' + \
                re.escape(afterMarkerString)
            else:
                searchString_ = searchString

            log.debug('searchString: {}'.format(searchString_))

            found_ = re.search(searchString_, logFileText)
            foundItems.append(found_.group(1))

            if logFileLabels:
                logFileLabels.append(logFilepath)

    if logFileLabels:
        return foundItems, logFileLabels
    else:
        return foundItems
