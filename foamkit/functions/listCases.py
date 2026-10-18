import os
from pathlib import Path
import sys
import re

from .isCase import isCase


def listCases(path=None, absolutePath=False):
    if path is None:
        path = Path.cwd()
    #convert string inputs to Path()
    if isinstance(path, str):
        path = Path(path)

    if isCase(path): #is the root directory an OpenFOAM case?
        if absolutePath:
            return [path]
        else:
            return [Path(os.path.relpath(path, Path.cwd()))]

    cases = []

    for p in path.rglob('*'):
        if isCase(p):
            if absolutePath:
                cases.append(p)
            else:
                cases.append(p.relative_to(path))

    cases.sort()

    return cases
