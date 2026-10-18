from foamkit import userMsg
from foamkit.functions import load
from pathlib import Path
import os

import logging


logger = logging.getLogger('foamkit')

def restore(path=None):
    """
    Restore a case from the most recent backup.  The `path` argument is the
    path of the cached case (without the '.json' extension) whose backups
    ('<path>.backup<n>') are searched; default '.params/_case' in the current
    directory.
    WARNING!:  This will perminantly delete the current case configuration!
    """
    if path is None:
        path = Path.cwd() / '.params' / '_case'

    logger.debug("Restore path: %s", path)

    #- Get the lastest backup file
    path_ = None
    i = 0
    while Path(str(path)+'.backup'+str(i)).is_file():
        path_ = Path(str(path)+'.backup'+str(i))
        i+=1

    if path_ is None:
        userMsg("No backup data found.  Cannot restore case.", "ERROR")

    case_ = load(path_, _backup=True)

    case_.save()

    os.remove(path_)

    return case_
