from pathlib import Path
import numpy as np
import foamkit.types as pt
from foamkit import userMsg

import logging

logger = logging.getLogger('foamkit')

def getMonitor(name=None, startTime='latestTime', dataFileName=None,
     logPath=None, workingDir=Path.cwd()):
    """
    Get an ofMonitor object from a log file written to the 'postProcessing/'
    directory.

    Data file is either specified by a `field` and `startTime` argument or a 
    `logPath`.  If `logPath` is specified, the `field` and `time` arguments are
    ignored. 

    Post processing data is typically stored as:

    postProcessing/<name>/<startTime>/<dataFile>.dat

    Parameters:
        name [str]:  The field for which data is to be extracted.
        startTime [str]:  The start time from which to read the log 
            data.  Accepts a string value as either `latestTime` or a numerical 
            value indicating the start time.  If `latestTime` data will be read 
            from last time in the `field` directory.  If 'all' collects data
            from all start times available for monitor.
        logPath [str]: The path of the log file to read.  If specified, the
            `field` argument is ignored.

    Returns:
        data [np.array]:    Log file data written as a numpy array

    """

    # logging.getLogger('foamkit').setLevel(logging.DEBUG)

    if startTime == 'all':
        allTimes = True
    else:
        allTimes = False

    if logPath is None:
        if startTime == 'latestTime' or startTime == 'all':
            timePath = Path(workingDir) / 'postProcessing' / name
            startTime = 0
            for time in timePath.iterdir():
                try:
                    time_ = float(time.name)
                    if time_ > float(startTime):
                        startTime = time.name
                except ValueError:
                    pass            
            startTime = str(startTime)
        logPathParent = (Path(workingDir) / 'postProcessing' / name 
        / str(startTime))

    if dataFileName is None:
        #TODO:  This just takes the first log file in the list.  Is there a 
        # better way?
        logFileNames = []
        for path in logPathParent.iterdir():
            if path.is_file():
                logFileNames.append(path.name)
        if len(logFileNames) > 1:
            userMsg("Found multiple log files, defualting to last item in list: " \
                +str(logFileNames), "WARNING"
            )
        elif len(logFileNames) == 0:
            userMsg("Could not find any log file in directory {logPathParent}",
            "ERROR")
        logPath = logPathParent / logFileNames[-1]
    else:
        logPath = logPathParent / dataFileName

    logger.debug(f"logPath: {logPath}")

    monitor = pt.MonitorParser(logPath).makeOFMonitor()
    # data = np.loadtxt(logPath, delimiter="\s+")

    return monitor