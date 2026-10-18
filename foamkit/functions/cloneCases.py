from foamkit.functions import cloneCase, listCases, isCase
from foamkit import userMsg
import subprocess
import shutil
import sys
from pathlib import Path

import logging

logger = logging.getLogger('foamkit')

def cloneCases(srcPath, destPath, sshSrc=None, sshDest=None, includeTriSurface=False):
    """
    Clone all cases found in the srcPath to the destPath.

    Parameters:
    srcPath [str or Path]:  The location of the source case.
    destPath [str or Path]:  The destination to copy case files to.
    sshSrc [str]:  If copying from a remote location, the string of login details  
            for the remote host in sh format (e.g. 'marc@my.remote.com')
    sshDest [str]:  If copying to a remote location, the string of login details  
            for the remote host in sh format (e.g. 'marc@my.remote.com')
    """
        
    #- Note the sshSrc option currently isnt working because the src files need to
    # be accessed for more than just the subprocess command 

    #- TODO:  Also copy the studySamplePoints.txt file, and .params directory


    srcPath = Path(srcPath)
    destPath = Path(destPath)

    cases = listCases(srcPath)

    for casePath in cases:
        logger.debug("Cloning case directory: %s", casePath)

        if not sshDest:
            (destPath / casePath).mkdir(parents=True)

        logger.debug("clone src path: %s", srcPath / casePath)

        cloneCase(srcPath / casePath, 
            destPath / casePath,
            sshSrc=sshSrc,
            sshDest=sshDest,
            includeTriSurface=includeTriSurface)

    if sshDest:
        #- The '.params' and 'studySamplePoints.txt' files below are only
        #  copied for local destinations.
        return

    #- Copy the .params directory
    if (srcPath / '.params').is_dir():
        shutil.copytree(srcPath / '.params', destPath / '.params',
                        dirs_exist_ok=True)


    #- copy all 'studySamplePoint.txt' files
    def _parseObj(obj):
        for obj_ in Path(obj).iterdir():
            if isCase(obj_):
                continue
            if obj_.is_dir():
                _parseObj(obj_)
                continue
            if (obj_.is_file() and obj_.name == 'studySamplePoints.txt'
                and (Path(destPath) / obj_.relative_to(srcPath)).parent.is_dir()):
                shutil.copy(obj_, (Path(destPath) / obj_.relative_to(srcPath)))

    _parseObj(srcPath)