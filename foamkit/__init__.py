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

#- Config file shipped with the package (lowest precedence).
PACKAGE_CONFIG = Path(__file__).parent / 'config.ini'
#- Per-user config.  `~/.pyfoamd` is the legacy location (before the rename
#- from PyFoamd) and is still read if `~/.foamkit` has no match.
USER_CONFIG = Path.home() / '.foamkit' / 'config.ini'
LEGACY_USER_CONFIG = Path.home() / '.pyfoamd' / 'config.ini'

#- Built-in defaults, also used to coerce config values to the right type.
CONFIG_DEFAULTS = {
    'debug': False,
    'dict_filesize_limit': 10000000,
}


class FoamKitError(SystemExit):
    """
    Raised by `userMsg(..., "ERROR")`.

    Subclasses `SystemExit`, so an unhandled error still terminates a script
    (as it always has), but with exit status 1, and library callers can
    `except FoamKitError` to recover.
    """
    def __init__(self, msg=""):
        super().__init__(1)
        self.msg = msg

    def __str__(self):
        return self.msg


def enableRichTracebacks():
    """
    Opt in to rich-formatted tracebacks.

    This replaces `sys.excepthook` for the whole process, so it is never done
    on import.  The command line interface calls it; scripts may call it too.
    """
    from rich.traceback import install
    install()


#- Parsed config files, keyed by path and invalidated when the file changes.
_configCache = {}


def _readConfigFile(path):
    """Return a `ConfigParser` for `path`, or `None` if it is not a file."""
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
    cached = _configCache.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    parser = ConfigParser()
    parser.read(path)
    _configCache[path] = (mtime, parser)
    return parser


def _coerce(param, value):
    """Convert a raw config string to the type of its built-in default."""
    default = CONFIG_DEFAULTS.get(param)
    if not isinstance(value, str):
        return value
    if isinstance(default, bool):
        return value.strip().lower() in ('1', 'yes', 'true', 'on')
    if isinstance(default, int):
        return int(value)
    return value


def configSearchPaths():
    """Config files in order of precedence (highest first)."""
    return [Path('.params') / 'config.ini', USER_CONFIG, LEGACY_USER_CONFIG,
            PACKAGE_CONFIG]


def getFoamKitConfig(param):
    """
    Look up a FoamKit config value.

    Files are searched in the order given by `configSearchPaths()`; within a
    file the `[user]` section takes precedence over `[default]`.  Known
    parameters are returned with the type of their built-in default (e.g.
    `debug` is a `bool`, not the string "False"); unknown parameters are
    returned as strings, or `None` if not found.
    """
    key = param.lower()
    for path in configSearchPaths():
        parser = _readConfigFile(path)
        if parser is None:
            continue
        value = None
        if parser.has_section('user'):
            value = parser.get('user', key, fallback=None)
        if value is None:
            value = parser.get('default', key, fallback=None)
        if value is not None:
            return _coerce(key, value)

    return CONFIG_DEFAULTS.get(key)

def userMsg(msg, level = "INFO"):
    """
    Write message to console or stdout for the user (i.e. without code details)

    Parameters:
        msg [str]:  The message to print

        level [str]: Either "INFO", "WARNING" or "ERROR".  If "ERROR", a
        `FoamKitError` is raised, which terminates the script with exit
        status 1 unless caught.
    """

    printStyle = {
        "INFO": 'blue',
        "WARNING": "bold orange",
        "ERROR": "bold red"
    }

    if logger.level == logging.DEBUG:
        logger.debug('User Msg:%s: %s', level, msg)
    else:
        print(f'[{printStyle[level]}]{level}:[/{printStyle[level]}]'\
            f' {msg}')

    if level == 'ERROR':
        raise FoamKitError(msg)

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
