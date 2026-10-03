import json
import pandas as pd
from copy import deepcopy
from foamkit.types import TAB_SIZE, _ofTypeBase, ofDict, _ofCaseBase, \
    _ofFolderBase
from pathlib import Path
import os
from collections.abc import Iterable

import logging

logger = logging.getLogger("foamkit")

#from: https://stackoverflow.com/a/33062932

class JSONFoamKitEncoder(json.JSONEncoder):
    def default(self, obj):
        logger.debug(f"JSON Parsing object: {type(obj)}")
        logger.debug(f"JSON Parsing obj.__dict__: {obj.__dict__}")
        if isinstance(obj, pd.DataFrame):
            return obj.reset_index().to_dict(orient='records')
        elif isinstance(obj, ofDict):
            logger.debug(f"JSON Parsing ofDict type: {type(obj)}")
            return obj.__dict__
        # elif (isinstance(obj, _ofTypeBase) or isinstance(obj, _ofFolderBase)):
        elif isinstance(obj, _ofCaseBase):
            return obj.__dict__
        elif isinstance(obj, _ofFolderBase):
            logger.debug(f"JSON Parsing ofTypeBase type: {type(obj)}")
            logger.debug(f"JSON Parsing ofTypeBase obj.__dict__: {obj.__dict__}")
            return obj.__dict__
        # elif isinstance(obj, _ofCaseBase):
        #     return obj.__dict__
        # elif isinstance(obj, _ofFolderBase):
        #     return obj.__dict__
        # # # elif isinstance(obj, ofDict):
        # #     logger.debug(f"Found _ofTypeBase: {obj}")
        # #     return dict(obj)
        # elif isinstance(obj, _ofTypeBase):
        #     logger.debug(f"Found _ofTypeBase: {obj}")
        #     # return dict(obj)
        #     return obj.__dict__
        elif isinstance(obj, Path):
            return str(obj)
        else:
            # return json.JSONEncoder.default(self,obj)
            return str(obj)

def writeCase(case, filepath=Path('.params') / '_case.json'):

    if str(filepath)[-5:] != '.json':
        filepath = Path(str(filepath)+'.json')

    # logger.setLevel(logging.DEBUG)

    logger.debug(f"case: {case}")

    #- Recursively convert an ofCase object (or any type) to a dictionary.
    def toDict(obj):

        logger.debug(f"Parsing obj: {obj}")

        if isinstance(obj, str):
            return obj
        if isinstance(obj, type):
            return str(obj)
        elif isinstance(obj, ofDict):
            return dict((key, toDict(val)) for 
                            key, val in obj.attrDict().items())
        elif isinstance(obj, _ofTypeBase):
            logger.debug(f"attrDict: {obj.attrDict()}")
            return toDict(obj.attrDict())
        elif isinstance(obj, dict):
            return dict((key, toDict(val)) for key, val in obj.items())
        # elif isinstance(obj, _ofTypeBase):
        #     return toDict(dict(obj))
        # elif isinstance(obj, _ofFolderBase):
        #     return toDict(dict(obj))
        # elif isinstance(obj, Iterable):
        #     return [toDict(val) for val in obj]
        elif hasattr(obj, '__dict__'):
            return toDict(vars(obj))
        elif hasattr(obj, '__slots__'):
            return toDict(dict((name, getattr(obj, name)) for 
            name in getattr(obj, '__slots__')))
        return obj

    case_ = toDict(case)

    logger.debug(f"case_: {case_}")

    if not Path(filepath).parent.is_dir():
        os.mkdir(Path(filepath).parent)

    with open(filepath, 'w')  as fp:
        json.dump(case_, fp, skipkeys=False, indent=TAB_SIZE, sort_keys=False,
                  cls=JSONFoamKitEncoder)

    # del params_
