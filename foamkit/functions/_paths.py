"""Small path helpers shared by the `foamkit.functions` modules."""
import math
import os
import re
from pathlib import Path
from typing import List

from foamkit import userMsg

# - A time name: a decimal or exponent number, optionally signed.  Not nan,
#  inf, underscores, hex or hidden names.
_TIME_NAME = re.compile(r'[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?')


def _isTime(name: str) -> bool:
    """Is `name` the name of a time directory (a finite number)?"""
    return bool(_TIME_NAME.fullmatch(name)) and math.isfinite(float(name))


def listTimes(directory) -> List[str]:
    """
    Return the names of the time directories in `directory` in numeric order,
    exactly as on disk.  Names with the same value (`1` and `1.0`) are all
    kept, in a fixed order.  Raises FoamKitError if `directory` cannot be read.
    """
    try:
        with os.scandir(directory) as entries:
            names = [e.name for e in entries
                     if _isTime(e.name) and e.is_dir()]
    except OSError as err:
        userMsg("Cannot list the time directories in '%s': %s"
                % (directory, err), 'ERROR')
    return sorted(names, key=lambda name: (float(name), name))


def latestTime(times: List[str], directory) -> str:
    """
    Return the latest of `times` (from `listTimes(directory)`), or '0' if there
    are none.  Raises FoamKitError if two names share the latest value.
    """
    if not times:
        return '0'
    if len(times) > 1 and float(times[-2]) == float(times[-1]):
        userMsg("Cannot tell the latest time in '%s': '%s' and '%s' have the "
                "same value." % (directory, times[-2], times[-1]), 'ERROR')
    return times[-1]


def latestTimeName(directory):
    """
    Return the name of the latest time directory in `directory` (e.g. the
    latest start time in 'postProcessing/probes'), or '0' if there is none.
    """
    return latestTime(listTimes(directory), directory)


def withJsonSuffix(path):
    """Append '.json' to `path` unless it already ends with it."""
    if str(path)[-5:] != '.json':
        return Path(str(path)+'.json')
    return Path(path)
