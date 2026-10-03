import os
from pathlib import Path
from foamkit.functions.isCase import isCase

import logging

# def getLatestTime(directory=Path.cwd()):

#     #- Get the latest time directory
#     directories = [f.name for f in Path(directory).iterdir()]
#     latestTime = '0'
#     for directory in directories:
#         name = directory.replace('/', '')
#         if name.isdigit() is True:
#             if int(name) > int(latestTime):
#                 latestTime = name

#     return latestTime

def getLatestTime(searchDir=Path.cwd()):
    """
    Returns the latest time directory of an OpenFOAM case or directory.  If
    directory is an OpenFOAM, this function searches reconstructed and decomposed directories.

    Parameters:
        searchDir [pathlib.Path]:  The location of the OpenFoam case or directory
            to search

    Returns:
        latestTime [float]: The latest time directory
        
        caseType [str]: The type of case containing the `latestTime`.  Either 
            'decomposed' or 'reconstructed'.
    """

    logger = logging.getLogger('foamkit')
    

    caseType = None

    #- Get the latest time directory for reconstructed case
    directories = [f.name for f in os.scandir(Path(searchDir).resolve()) if f.is_dir()]
    latestTime = '0'
    for directory in directories:
        name = directory.replace('/', '')
        if name.isdigit() is True:
            if float(name) > float(latestTime):
                latestTime = name

    if  isCase(searchDir):

        #- Get the latest time for the decomposed case
        p0 = Path(searchDir) / 'processor0'
        platestTime = '0'
        if (p0).is_dir():
            directories = [f.name for f in os.scandir(p0) if f.is_dir()]
            for directory in directories:
                name = directory.replace('/', '')
                # if name.isdigit() is True:
                try:
                    float(name)
                    if float(name) > float(platestTime):
                        platestTime = name
                except (ValueError, TypeError):
                    pass

        if float(platestTime) > float(latestTime):
            latestTime = platestTime
            caseType = 'decomposed'
        else: 
            caseType = 'reconstructed'
    
    logger.debug(f"latestTime: {latestTime}")

    return latestTime, caseType