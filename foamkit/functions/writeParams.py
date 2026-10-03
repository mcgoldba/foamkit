import json
import pandas as pd
from copy import deepcopy
from foamkit.types import TAB_SIZE, _ofTypeBase, ofDict, _ofCaseBase, \
    _ofFolderBase
from pathlib import Path
import os

import logging

logger = logging.getLogger("foamkit")

#from: https://stackoverflow.com/a/33062932

class JSONFoamKitEncoder(json.JSONEncoder):
    def default(self, obj):
        logger.debug(f"JSON Parsing object: {type(obj)}")
        logger.debug(f"JSON Parsing obj.__dict__: {obj.__dict__}")
        if isinstance(obj, pd.DataFrame):
            return obj.reset_index().to_dict(orient='records')
        # elif isinstance(obj, ofDict):
        #     logger.debug(f"JSON Parsing ofDict type: {type(obj)}")
        #     return obj.toDict()
        # # elif (isinstance(obj, _ofTypeBase) or isinstance(obj, _ofFolderBase)):
        # elif isinstance(obj, _ofCaseBase):
        #     return obj.__dict__
        # elif isinstance(obj, _ofFolderBase):
        #     logger.debug(f"JSON Parsing ofTypeBase type: {type(obj)}")
        #     logger.debug(f"JSON Parsing ofTypeBase obj.__dict__: {obj.__dict__}")
        #     return obj.__dict__
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
        # elif isinstance(obj, Path):
        #     return str(obj)
        else:
            return json.JSONEncoder.default(self,obj)
            # return str(obj)

def writeParams(params, filepath='inputParameters', sort=True):

    # logger.setLevel(logging.DEBUG)

    logger.debug(f"params: {params}")

    #Create temporary object
    params_ = deepcopy(params)

    logger.debug(f"params_: {params_}")

    if not Path(filepath).parent.is_dir():
        os.mkdir(Path(filepath).parent)

    with open(filepath, 'w')  as fp:
        json.dump(params_, fp, skipkeys=False, indent=TAB_SIZE, sort_keys=sort,
                  cls=JSONFoamKitEncoder, 
                  default=lambda o: getattr(o, '__dict__', str(o)))

    del params_
