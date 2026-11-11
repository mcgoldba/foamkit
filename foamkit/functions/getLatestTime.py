from pathlib import Path
from foamkit.functions.isCase import isCase
from foamkit.functions._paths import latestTime, listTimes

import logging

def getLatestTime(searchDir=None):
    """
    Returns the latest time directory of an OpenFOAM case or directory.  If
    directory is an OpenFOAM, this function searches reconstructed and decomposed directories.

    Time directories are named by decimal or exponent numbers (`0.5`,
    `1e-05`, `-1`) and compared by value; see `timeDirs`.  If the reconstructed
    and 'processor0' latest times are equal, the case type is 'reconstructed'.

    Parameters:
        searchDir [pathlib.Path]:  The location of the OpenFoam case or directory
            to search

    Returns:
        latestTime [str]: The name of the latest time directory ('0' if there
            is none)

        caseType [str]: The type of case containing the `latestTime`.  Either
            'decomposed' or 'reconstructed' (None if `searchDir` is not a case).

    Raises FoamKitError if the directory cannot be read, or if two directories
    (such as `1` and `1.0`) share the latest value.
    """

    logger = logging.getLogger('foamkit')

    if searchDir is None:
        searchDir = Path.cwd()
    

    caseType = None

    #- Get the latest time directory for reconstructed case
    searchDir = Path(searchDir).resolve()
    latest = latestTime(listTimes(searchDir), searchDir)

    if  isCase(searchDir):

        #- Get the latest time for the decomposed case
        p0 = searchDir / 'processor0'
        ptimes = listTimes(p0) if p0.is_dir() else []
        platest = latestTime(ptimes, p0) if ptimes else None

        if platest is not None and float(platest) > float(latest):
            latest = platest
            caseType = 'decomposed'
        else:
            caseType = 'reconstructed'

    logger.debug("latestTime: %s", latest)

    return latest, caseType