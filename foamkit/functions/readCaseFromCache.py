from foamkit.functions import readConfig
import json
from pathlib import Path

def readCaseFromCache(name='_case.json'):
    """
    Reads in a case from the cached data (stored as `.params/_case.json`).
    """

    if name[-5:] != '.json':
        name+='.json'

    filepath = Path('.params') / name

    return json.load(open(filepath))