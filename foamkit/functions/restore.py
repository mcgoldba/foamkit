from foamkit import userMsg
from foamkit.functions import load
from pathlib import Path
import os

import logging


logger = logging.getLogger('foamkit')

# from foamkit.config import DEBUG

def restore(path=Path.cwd() / '.params' / '_case'):
    """
    Restore a case from the most recent backup.  The `path` argument is the path
     of the case to be restored. 
    WARNING!:  This will perminantly delete the current case configuration!
    """

    logger.debug(f"Restore path: {path}")

    #- Get the lastest backup file
    i = 0
    while Path(str(path)+'.backup'+str(i)).is_file():
        path_ = Path(str(path)+'.backup'+str(i))
        i+=1


    if not path_.is_file():
        userMsg("No backup data found.  Cannot restore case.", "ERROR")
        return None

    case_ = load(path_, _backup=True)

    case_.save()

    os.remove(path_)

    return case_