from pathlib import Path
import numpy as np
import foamkit.types as pt

import logging

logger = logging.getLogger('foamkit')

def getProbe(field=None, startTime='latestTime', workingDir=Path.cwd(),
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

    # logging.getLogger('foamkit').setLevel(logging.DEBUG)

    if logPath is None:
        if startTime == 'latestTime':
            timePath = Path(workingDir) / 'postProcessing' / 'probes'
            startTime = 0
            for time in timePath.iterdir():
                try:
                    time_ = float(time.name)
                    if time_ > float(startTime):
                        startTime = time.name
                except ValueError:
                    pass            
            startTime = str(startTime)
        logPath = (Path(workingDir) / 'postProcessing' / 'probes' 
        / str(startTime) / field)

    logger.debug(f"logPath: {logPath}")

    probe = pt.ofProbe(logPath)
    # data = np.loadtxt(logPath, delimiter="\s+")

    return probe