from pathlib import Path
import numpy as np
import pandas as pd
import logging
import re
from foamkit import userMsg
import foamkit.types as pt
from foamkit.functions.getProbe import getProbe
from foamkit.functions.getMonitor import getMonitor

logger = logging.getLogger("foamkit")

#- Style applied to monitor and plot windows (scoped to those figures, rather
#  than set globally for every plot in the session on import).
PLOT_STYLE = 'ggplot'

def monitor(value='U', time='latestTime', supplement=None,
    workingDir=None, title=None, filter=None, yrange = None,
    logScale=False, all=False):
    """
    Plot a probe or function object monitor, refreshing every second with the
    data appended since the previous refresh.
    """
    #- matplotlib is slow to import; only load it when plotting.
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    if workingDir is None:
        workingDir = Path.cwd()

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

    def updatePlot(i):
        #- Only the lines written since the last refresh are parsed.
        monitor.update()
        x = pd.to_numeric(monitor.data.index).to_numpy().reshape((-1, 1))

        Y = monitor.data[columns_].apply(pd.to_numeric).to_numpy()

        logger.debug("Y: %s", Y)

        if np.isnan(Y).all():
            userMsg("No data found for plot!", "WARNING")
            return

        plt.cla()
        for i, label in enumerate(columns_):
            plt.plot(x,Y[:,i], label=label)

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

    with plt.style.context(PLOT_STYLE):
        ani = FuncAnimation(plt.gcf(), updatePlot, interval=1000,
                            cache_frame_data=False)

        plt.tight_layout()

        plt.show()
