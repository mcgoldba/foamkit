from pathlib import Path
import foamkit.types as pt
from foamkit.functions._paths import latestTimeName
from foamkit import userMsg

import logging

logger = logging.getLogger('foamkit')

def getMonitor(name=None, startTime='latestTime', dataFileName=None,
     logPath=None, workingDir=None):
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

    if workingDir is None:
        workingDir = Path.cwd()

    #TODO: 'all' should collect data from every start time; currently it is
    #       treated as 'latestTime'.

    if logPath is None:
        if startTime == 'latestTime' or startTime == 'all':
            startTime = latestTimeName(Path(workingDir) / 'postProcessing' / name)
        logPathParent = (Path(workingDir) / 'postProcessing' / name
        / str(startTime))

        if dataFileName is None:
            #TODO:  This just takes the last log file in the list.  Is there a
            # better way?
            logFileNames = sorted(path.name for path in logPathParent.iterdir()
                                  if path.is_file())
            if len(logFileNames) > 1:
                userMsg("Found multiple log files, defualting to last item in list: " \
                    +str(logFileNames), "WARNING"
                )
            elif len(logFileNames) == 0:
                userMsg(f"Could not find any log file in directory {logPathParent}",
                "ERROR")
            logPath = logPathParent / logFileNames[-1]
        else:
            logPath = logPathParent / dataFileName

    logger.debug("logPath: %s", logPath)

    monitor = pt.MonitorParser(logPath).makeOFMonitor()

    return monitor