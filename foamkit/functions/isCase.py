from foamkit.types._isCase import _isCase

def isCase(path=None):
    """
    Return True if `path` (default: the current directory) looks like an
    OpenFOAM case: it has a 'system/controlDict' file and a '0' or '0.orig'
    directory.
    """
    return _isCase(path)
