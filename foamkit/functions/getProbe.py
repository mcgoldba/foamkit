from pathlib import Path
import foamkit.types as pt
from foamkit.functions._paths import latestTimeName

import logging

logger = logging.getLogger('foamkit')

def getProbe(field=None, startTime='latestTime', workingDir=None,
     logPath=None):
    """
    Get an ofProbe object from a log file written to the 'postProcessing/probes'
    directory.

    Data file is either specified by a `field` and `startTime` argument or a 
    `logPath`.  If `logPath` is specified, the `field` and `time` arguments are
    ignored. 

    Post processing data is typically stored as:

    postProcessing/probes/<startTime>/<field>

    Parameters:
        field [str]:  The field for which data is to be extracted.
        startTime [str]:  The start time from which to read the log 
            data.  Accepts a string value as either `latestTime` or a numerical 
            value indicating the start time.  If `latestTime` data will be read 
            from last time in the `field` directory.
        logPath [str]: The path of the log file to read.  If specified, the
            `field` argument is ignored.

    Returns:
        data [np.array]:    Log file data written as a numpy array

    """

    if workingDir is None:
        workingDir = Path.cwd()

    if logPath is None:
        if startTime == 'latestTime':
            startTime = latestTimeName(Path(workingDir) / 'postProcessing' / 'probes')
        logPath = (Path(workingDir) / 'postProcessing' / 'probes'
        / str(startTime) / field)

    logger.debug("logPath: %s", logPath)

    probe = pt.ofProbe(logPath)

    return probe