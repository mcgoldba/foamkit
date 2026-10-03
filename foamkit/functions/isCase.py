import os

import logging

log = logging.getLogger('foamkit')

def isCase(path=os.getcwd()):
    isCase = False

    caseFiles = [os.path.join(path, 'system', 'controlDict')]

    if (os.path.isfile(os.path.join(path, 'system', 'controlDict'))):
        #log.debug("Found 'controlDict'.")
        if (os.path.isdir(os.path.join(path, '0')) or
             os.path.isdir(os.path.join(path, '0.orig'))):
            #log.debug("Found '0' directory")
            isCase = True

    return isCase
