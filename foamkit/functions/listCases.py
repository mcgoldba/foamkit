from pathlib import Path
import sys
import re

from .isCase import isCase


def listCases(path=Path.cwd(), absolutePath=False):
    #convert string inputs to Path()
    if isinstance(path, str):
        path = Path(path)

    if isCase(path): #is the root directory an OpenFOAM case?
        if absolutePath:
            return [path]
        else:
            return [path.relative_to(Path.cwd())]

    cases = []

    for p in path.rglob('*'):
        if isCase(p):
            if absolutePath:
                cases.append(p)
            else:
                cases.append(p.relative_to(path))

    cases.sort()

    return cases
