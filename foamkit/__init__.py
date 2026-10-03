import os
from configparser import ConfigParser
from pathlib import Path
import sys

import logging


from rich import print

logger = logging.getLogger('foamkit')
# Library convention: stay silent unless the application configures logging.
logger.addHandler(logging.NullHandler())

FOAM_VERSION = os.environ.get('WM_PROJECT_VERSION', "")
if not FOAM_VERSION:
    # Not an error: reading, editing and writing cases does not need OpenFOAM.
    logger.debug("OpenFOAM environment not found (WM_PROJECT_VERSION is unset).")

def enableRichTracebacks():
    """
    Opt in to rich-formatted tracebacks.

    This replaces `sys.excepthook` for the whole process, so it is never done
    on import.  The command line interface calls it; scripts may call it too.
    """
    from rich.traceback import install
    install()

def getFoamKitConfig(param):
    def getParam(param, configPath):
        parser = ConfigParser()
        parser.read(configPath)

        if parser.has_section('user'): 
            param_ = parser.get('user', param.lower(), fallback=None)
            if param_ is None:
                param_ = parser.get('default', param.lower(), fallback=None)
        else:
            param_ = parser.get('default', param.lower(), fallback=None)
        return param_       

    param_ = None
    if (Path('.params') / 'config.ini').is_file():
        # print(f"FoamKit config file: {Path('.params') / 'config.ini'}")
        param_ = getParam(param, Path('.params') / 'config.ini')
    #- User config.  `~/.pyfoamd` is the legacy location (before the rename
    #- from PyFoamd) and is still read if `~/.foamkit` has no match.
    for userDir in ('.foamkit', '.pyfoamd'):
        userConfig = Path.home() / userDir / 'config.ini'
        if param_ is None and userConfig.is_file():
            param_ = getParam(param, userConfig)
    # print(f"Looking for FoamKit config file: {Path(__file__) / 'config.ini'}...")
    if os.name == 'nt':
        if param_ is None and (Path(__file__) / 'config.ini').is_file():
            # print(f"FoamKit config file: {Path(__file__) / 'config.ini'}")
            param_ = getParam(param, Path(__file__) / 'config.ini')
    else:
        if param_ is None and (Path(__file__).parent / 'config.ini').is_file():
            # print(f"FoamKit config file: {Path(__file__).parent / 'config.ini'}")
            param_ = getParam(param, Path(__file__).parent / 'config.ini')
    if param_ is None:
        # print(f"Warning: Using system default for FoamKit config.  Could not find config file")
        if param.lower() == 'debug':
            param_ = False
        if param.lower() == 'dict_filesize_limit':
            param_ = 10000000

    if param_ is None:
        Exception(f"Could not locate parameter '{param}' in config.ini and no default is provided.")

    # print(f"PyFoam config: {param} = {param_}")

    return param_

def userMsg(msg, level = "INFO"):
    """
    Write message to console or stdout for the user (i.e. without code details)
    
    Parameters:
        msg [str]:  The message to print
        
        level [str]: Either "INFO", "WARNING" or "ERROR".  If "ERROR", script is
        terminated.
    """

    printStyle = {
        "INFO": 'blue',
        "WARNING": "bold orange",
        "ERROR": "bold red"
    }

    if logger.level == logging.DEBUG:
        logger.debug(f'User Msg:{level}: {msg}')
        #raise Exception
    else:
        print(f'[{printStyle[level]}]{level}:[/{printStyle[level]}]'\
            f' {msg}')
    
    if level == 'ERROR':
        sys.exit()

def setLoggerLevel(level):
    """Set the message level of the Python logger."""

    levels = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET
    }

    logging.getLogger('foamkit').setLevel(levels[level])
