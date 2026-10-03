import sys
from pathlib import Path

from foamkit.types import _parseNameTag

import logging
logger = logging.getLogger('foamkit')



def parseNameTag(name):
    """
    Replace any special characters not allowed in python attribute names with a 
    suitable replacement, as specified in the `SPECIAL_CHARS` variable.
    """
    return _parseNameTag(name)