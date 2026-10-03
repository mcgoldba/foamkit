import os
from pathlib import Path

def _isCase(path=os.getcwd()):
    isCase = False

    caseFiles = [os.path.join(path, 'system', 'controlDict')]

    if (os.path.isfile(os.path.join(path, 'system', 'controlDict'))):
        if (os.path.isdir(os.path.join(path, '0')) or
             os.path.isdir(os.path.join(path, '0.orig'))):
            isCase = True

    return isCase
