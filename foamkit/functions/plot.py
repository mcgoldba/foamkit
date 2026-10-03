import matplotlib.pyplot as plt
from pathlib import Path
import pandas as pd
import re
import numpy as np
from foamkit import userMsg
import foamkit.types as pt

import logging
logger = logging.getLogger('foamkit')

def plot(relDataFile=None, monitor=None, filter=None, logScale=False, 
    workingDir=Path.cwd(), yrange = None, returnPlot= False):
    """
    Plot data from a log file.  

    Parameters:
        relDataFile [Path]: The path of the log data file relative to the 
        working directory (case directory).  If `monitor` is specified, this 
        argument is ignored.

        monitor [ofMonitor]:  The ofMonitor for which the data is to be plotted.

        filter [str]:  The regex compliant string for which that defines the 
        columns to plot (e.g. `filter='initial'` will only plot columns with the
        string `initial` in its name.)

        logScale [bool]:  If `True` plots the data with a log scale on the 
        y-axis.

        yrange [list(float)]:  The range for the yaxis as a list of 2 values 
            (e.g. `[0, 100]`)

        returnPlot [bool]: If `True`, returns the matplotlib.plt object instead 
            of displaying the figure.

    """

    # with open(dataFile) as f:
    #     line = f.readline()
    #     while line.strip().startswith('#'):
    #         prevline=line
    #         line=f.readline()

    # header = prevline.lstrip('#').split()
    # logger.debug(f"header: {header}")
    # df = pd.read_csv(dataFile, comment='#', index_col=xIndex, sep='\t')
    # logger.debug(f"columns: {df.columns}")
    # df.columns = header[1:]

    if monitor is None:
        if relDataFile is None:
            userMsg("Must provide one of the arguments 'relDataFile' or \
                'monitor'","ERROR")
        dataFile = Path(workingDir) / relDataFile
        monitor = pt.MonitorParser(dataFile).makeOFMonitor()

    #TODO:  This isnt working...
    # if not isinstance(monitor, pt.ofMonitor):
    #     userMsg("Invalid value specified for 'monitor' argument.  Must be an "\
    #         f"ofMonitor type. Got {type(monitor)}.", "ERROR")

    xData = monitor.data.index.to_numpy(dtype=float)

    data = monitor.data.to_numpy().T
    names = monitor.data.columns

    logger.debug(f"names: {names}")
    logger.debug(f"data: {data}")
    logger.debug(f"xData: {xData}")

    if filter is not None:
        filteredNames = []
        filteredData = []
        for data_, name in zip(data, names):
            # data_ = [v if isinstance(v, (float, int)) else 0 for v in data_]
            if re.search(filter, name):
               filteredNames.append(name)
               filteredData.append(data_)
        data = np.array(filteredData, dtype=float)
        names = filteredNames

        if len(filteredData) == 0:
            userMsg(f"Could not find any data matching the filter string \
                {filter}", "ERROR")


    for lineData, name in zip(data, names):
        logger.debug(f"lineData: {lineData}")
        logger.info(f"Adding {name} data to plot")
        plt.plot(xData, lineData, label = name)
    
    plt.xlabel(monitor.data.index.name)
    plt.ylabel('Value')
    plt.title(monitor._name)
    plt.legend()
    if logScale:
        plt.yscale('log')
    if yrange is not None:
        plt.ylim(yrange)

    if returnPlot:
        return plt
    else:
        plt.show()
