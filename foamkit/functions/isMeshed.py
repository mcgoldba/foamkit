from pathlib import Path

#- Files that make up an OpenFOAM polyMesh (each may also be gzip compressed)
MESH_FILES = ('points', 'faces', 'owner', 'neighbour', 'boundary')

def isMeshed(directory=None):
    """
    Return True if a valid mesh is found in the speficied directory,
    else return False.

    Parameters
    ----------

    directory : str
        The case directory in which to search for a valid mesh.  Defaults to
        the current directory.

    """
    if directory is None:
        directory = Path.cwd()

    meshDir = Path(directory) / 'constant' / 'polyMesh'

    if not meshDir.is_dir():
        return False

    return all((meshDir / f).is_file() or (meshDir / (f+'.gz')).is_file()
               for f in MESH_FILES)
