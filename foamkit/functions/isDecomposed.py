from pathlib import Path

from foamkit.functions.getLatestTime import getLatestTime

def isDecomposed(caseDir=None) -> bool:
    """
    Return True if the latest time of the case is in 'processor0', that is,
    `getLatestTime` returns 'decomposed'.  If the reconstructed and
    'processor0' latest times are equal, the case counts as reconstructed.

    Parameters:
        caseDir [str or Path]:  The case directory (default: the current
            directory).
    """
    if caseDir is None:
        caseDir = Path.cwd()

    return getLatestTime(caseDir)[1] == 'decomposed'
