import os
import sys
import re

def isMeshed(self, directory=None):
    """
    Return True if a valid mesh is found in the speficied directory,
    else return False.

    Parameters
    ----------

    directory : str
        The case directory in which to search for a valid mesh.

    """
    #- Set the default argument
    if not directory:
        directory = self.caseDir

    meshDir = os.path.join(directory, 'constant', 'polyMesh')

    #TODO: Gather mesh statstics and return with check.

    if (os.path.isdir(meshDir) and
        all([file in os.path.listdir(meshDir) for file in
             ['points', 'neighbors', 'boundary']])):
             return True

    else:
        return False
