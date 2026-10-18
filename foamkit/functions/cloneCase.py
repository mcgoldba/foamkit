from foamkit.functions import isCase
from foamkit import userMsg, getFoamKitConfig
from pathlib import Path
import shutil
import logging
import tempfile
import subprocess


logger = logging.getLogger('foamkit')


def cloneCase(srcPath, destPath, sshSrc=None, sshDest=None, includeTriSurface=False):
    """
    Clone the setup files of an OpenFOAM case to a new directory.

    The cloned case excludes any files and directories that include large
    amounts of data.

    The excluded directories are:
        - time directories other than '0/'
        - processor directories
        - postProcessing directories
        - 'constant/polyMesh'
        - 'constant/extendedFeatureEdgeMesh'
    In addition, any file with size greater than the foamkit file size limit is 
    ommitted.

    Parameters:
        src [str or Path]:  The location of the source case.
        dest [str or Path]:  The destination to copy case files to.
        sshSrc [str]:  If copying from a remote location, the string of login details  
                for the remote host in ssh format (e.g. 'marc@my.remote.com')
        sshDest [str]:  If copying to a remote location, the string of login details  
                for the remote host in ssh format (e.g. 'marc@my.remote.com')

    """
    #- The source files are filtered locally before copying, so a remote
    #  source cannot be supported this way.  Run `cloneCase` on the source
    #  host with `sshDest` instead.
    if sshSrc:
        userMsg("Cloning from a remote source ('sshSrc') is not supported.  "
            "Run cloneCase on the source host with 'sshDest' instead.", 'ERROR')

    if not isCase(srcPath):
        userMsg("Specified source is not a valid OpenFOAM case", 'ERROR')
    
    #-Copy all cloned files to temporary directory to allow for a single call to 
    # 'subprocess'


    srcPath = Path(srcPath)
    destPath=Path(destPath)

    tmpPath = Path(tempfile.mkdtemp())

    logger.debug("temp directory: %s", tmpPath)


    filesizeLimit = int(getFoamKitConfig('dict_filesize_limit'))

    def _copyObj(src, dest, top=False, tabStr=""):
        tabStr += "    "
        for obj in src.iterdir():
            logger.debug("%sParsing %s", tabStr, obj)
            if obj.is_dir():
                if top and obj.name.startswith('processor'):
                    continue
                if top and obj.name == 'postProcessing':
                    continue
                if top: # ignore time directories
                    try:
                        float(obj.name)
                        if obj.name != "0":
                            continue
                    except ValueError:
                        pass
                if top and obj.name == 'constant': #handle constant dir seperately
                    logger.debug("%sMaking directory: %s", tabStr, dest / 'constant')
                    (dest / 'constant').mkdir()
                    for obj_ in obj.iterdir(): #iterate items in 'constant' dir
                        if obj_.is_dir():
                            logger.debug("%sParsing object name %s", tabStr, obj_.name)
                            if (obj_.name == 'polyMesh' or
                            obj_.name == 'extendedFeatureEdgeMesh' 
                            ):
                                continue
                            if (obj_.name == 'triSurface' 
                                and includeTriSurface == False):
                                continue
                            logger.debug("%sMaking directory: %s", tabStr, dest / 'constant' / obj_.name)
                            (dest / 'constant' / obj_.name).mkdir()
                            _copyObj(obj_, (dest / 'constant' /obj_.name), tabStr=tabStr)
                        else:
                            logger.debug("%sCopying %s to %s", tabStr, obj_, dest / 'constant')
                            shutil.copy(obj_, (dest / 'constant'))
                if not (dest / obj.name).is_dir():
                    logger.debug("%sMaking directory: %s", tabStr, dest / obj.name)
                    (dest / obj.name).mkdir()
                    _copyObj(obj, (dest / obj.name), tabStr=tabStr)
            else:
                if obj.stat().st_size > filesizeLimit:
                    continue
                logger.debug("%sCopying %s to %s", tabStr, obj, dest)
                shutil.copy(obj, dest)
    
    try:
        _copyObj(srcPath, tmpPath, top=True)

        if sshDest:
            toStr = f'{sshDest}:{str(destPath)}'
            logger.info(f"Copying case from {srcPath} to {toStr}...")
            #- Argument lists (no shell): paths with spaces or shell
            #  metacharacters are passed through unchanged.
            subprocess.check_call(['ssh', sshDest, 'mkdir', '-p', str(destPath)])
            children = [str(p) for p in tmpPath.iterdir()]
            if children:
                subprocess.check_call(['scp', '-r', *children, toStr])
        else:
            logger.info(f"Copying case from {srcPath} to {destPath}...")
            shutil.copytree(tmpPath, destPath, dirs_exist_ok=True)
    finally:
        shutil.rmtree(tmpPath, ignore_errors=True)