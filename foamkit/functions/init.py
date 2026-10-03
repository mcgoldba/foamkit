from foamkit import getFoamKitConfig, setLoggerLevel
from foamkit.types import CaseParser
from pathlib import Path

import logging

logger = logging.getLogger('foamkit')

# from foamkit.config import DEBUG

def init(path=Path.cwd()):
    """
    Read an OpenFOAM case from file system and store as a Python dictionary.
    """
    # setLoggerLevel("DEBUG" if getFoamKitConfig('debug').lower() == 'true'
    #                 else "INFO")

    logger.debug(f"ofCase path: {path}")

    return CaseParser(path=path).makeOFCase()
