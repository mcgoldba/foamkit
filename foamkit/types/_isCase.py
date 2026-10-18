import os

def _isCase(path=None):
    """
    Return True if `path` (default: the current directory) looks like an
    OpenFOAM case: it has a 'system/controlDict' file and a '0' or '0.orig'
    directory.
    """
    if path is None:
        path = os.getcwd()

    return (os.path.isfile(os.path.join(path, 'system', 'controlDict'))
            and (os.path.isdir(os.path.join(path, '0'))
                 or os.path.isdir(os.path.join(path, '0.orig'))))
