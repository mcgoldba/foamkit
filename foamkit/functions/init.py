from foamkit import getFoamKitConfig, setLoggerLevel
from foamkit.types import CaseParser
from pathlib import Path

import logging

logger = logging.getLogger('foamkit')

# from foamkit.config import DEBUG

def init(path=None):
    """
    Read an OpenFOAM case from file system and store as a Python dictionary.
    """
    # setLoggerLevel("DEBUG" if getFoamKitConfig('debug').lower() == 'true'
    #                 else "INFO")

    if path is None:
        path = Path.cwd()

    logger.debug("ofCase path: %s", path)

    return CaseParser(path=path).makeOFCase()
