from pathlib import Path

from foamkit.functions.getLatestTime import getLatestTime

def isDecomposed(caseDir=None):
    """
    Return True if the case has a 'processor0' directory whose latest time is
    at least the latest reconstructed time.

    Parameters:
        caseDir [str or Path]:  The case directory (default: the current
            directory).
    """
    if caseDir is None:
        caseDir = Path.cwd()
    caseDir = Path(caseDir)

    reconstructedTime, _ = getLatestTime(caseDir)
    p0 = caseDir / 'processor0'

    return (p0.is_dir()
            and float(getLatestTime(p0)[0]) >= float(reconstructedTime))
