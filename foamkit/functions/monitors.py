import subprocess
import sys
import os
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import pandas as pd
import logging
import re
import copy
from foamkit import userMsg
import foamkit.types as pt
from foamkit.functions.getProbe import getProbe
from foamkit.functions.getMonitor import getMonitor

logger = logging.getLogger("foamkit")

plt.style.use('ggplot')

# def monitor(value='U', time='latestTime', supplement=None, 
#     workingDir=Path.cwd(), title=None, filter=None, yrange = None,
#     logScale=False, all=False):

def monitors(monitorDict):
    """
    Create plots of multiple monitors in the same plot window

    Parameters:
        monitorDict [dict(dict)]: dictionary containing monitor parameters, were each 
            key is the monitor name, and the values are dictionary of argumrents
            supplied to `foamkit.monitor`


    Example:
        >>> pf.monitors({
            'residuals': {
                'filter': 'initial'
                'log': True
            },
            'p': {}.
            'U': {
                'filter': 'Probe 0'
            }
            })

    """
    for value in monitorDict.keys():
        if title is None:
            title = Path(workingDir).name

        try:
            monitor = getMonitor(name=value, startTime=time, 
                        workingDir=workingDir)
        except FileNotFoundError:
            monitor = getProbe(value, time, workingDir)

        if filter is not None:
            columns_ = [monitor.data.columns[i] for i, item in 
            enumerate(monitor.data.columns) if re.search(filter, item)]
        else:
            columns_ = monitor.data.columns

    # x = monitor.data.index.to_numpy(dtype=float)
    # y = monitor.data.iloc[:,filteredColumnIdx].to_numpy(dtype=float)


    # fig, ax = plt.subplots(figsize=(4,3))
    # # line, = ax.plot(x,y)
    # lines = ax.plot(data=monitor.data)
    # if yrange is not None:
    #     ax.set_ylim(yrange)
    # if logScale:
    #     ax.set_yscale('log')


    # def updatePlot(_, monitor, filterIdx, lines):
    def updatePlot(i):
        #TODO:  This function should update existing monitors with new value,
        # rather than rereading the whole monitor file every loop.
        # logger.info("Updating monitor data...")
        monitor.update()
        x = pd.to_numeric(monitor.data.index).to_numpy().reshape((-1, 1))
        # try:
        #     x = [int(v) for v in x]
        # except:
        #     x = [float(v) for v in x]

        Y = monitor.data[columns_].apply(pd.to_numeric).to_numpy()

        logger.debug(f"Y: {Y}")

        if any(not np.isnan(v) for v in Y.flatten()) is False:
            userMsg("No data found for plot!", "WARNING")
            return

        # lines_ = []

        # for line, y in zip(lines, Y):

        # fig.set_data(x,y)


        # logger.info("Redrawing...")

        plt.cla()
        # df_ = monitor.data.iloc[:,filteredColumnIdx].apply(pd.to_numeric)
        # fig = df_.plot()
        for i, label in enumerate(columns_):
            plt.plot(x,Y[:,i], label=label)



        # plt.xlabel(monitor.data.index.name)
        # plt.ylabel('Value')
        # plt.title(monitor._name)
        # plt.legend()
        # if logScale:
        #     plt.yscale('log')
        # if yrange is not None:
        #     plt.ylim(yrange)

        plt.xlabel(monitor.data.index.name)
        plt.ylabel('Value')
        if isinstance(monitor, pt.ofProbe):
            plt.title(monitor._field)
        else:
            plt.title(monitor._name)
        plt.legend()
        if logScale:
            plt.yscale('log')
        if yrange is not None:
            plt.ylim(yrange)

    ani = FuncAnimation(plt.gcf(), updatePlot, 
        #fargs=(monitor, filteredColumnIdx, lines),
        interval=1000)

    plt.tight_layout() 

    plt.show()