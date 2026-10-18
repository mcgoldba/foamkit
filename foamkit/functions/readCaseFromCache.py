from foamkit.functions import readConfig
import json
from pathlib import Path
from foamkit.functions._paths import withJsonSuffix

def readCaseFromCache(name='_case.json'):
    """
    Reads in a case from the cached data (stored as `.params/_case.json`).
    """

    filepath = withJsonSuffix(Path('.params') / name)

    with open(filepath) as f:
        return json.load(f)