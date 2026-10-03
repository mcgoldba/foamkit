import json
import os
import sys
from pathlib import Path

import logging

log = logging.getLogger("foamkit")

#TODO:  Should this replace the inputParameters file?
def readConfig(key=None, file="foamkit.json", caseDir=Path.cwd()):
    """
    Reads a value to the specified configuration file, or returns the 
    configuration file as a python dictionary.

    Parameters
    ----------

    key : str
        The dictionary entries to read from the config file

    file : str
        The json file (in the case's `.params` directory) to read.  For
        backward compatibility, `pyfoamd.json` is read if the default
        `foamkit.json` does not exist.

    """

    if file[-5:] != ".json":
        file = file+".json"

    # filepath = os.path.join(".params", file)
    filepath = str(Path(caseDir) / ".params" /file)

    #- Legacy name used before the rename from PyFoamd
    if (file == "foamkit.json" and not os.path.isfile(filepath)
            and (Path(caseDir) / ".params" / "pyfoamd.json").is_file()):
        filepath = str(Path(caseDir) / ".params" / "pyfoamd.json")

    config = {}

    #convert the entry to string
    #entry = {str(key): str(value) for key, value in entry.items()}

    if os.path.isfile(filepath) is False:
        log.warning("Config file not found!: "+filepath)
        return None
    else:
        config = json.load(open(filepath))
        if key:
            if key in config:
                return config[key]
            else:
                keyStr = ""
                for k in config.keys():
                    keyStr+= k+', '
                keyStr = keyStr[:-2]+"."
                log.warning("Key '"+str(key)+"' not found in file.  Found keys "
                "are: "+keyStr)
        else:
            return config
