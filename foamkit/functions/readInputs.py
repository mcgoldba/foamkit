import os
import json
import pandas as pd

from._unitDecoder import _unitDecoder

import logging

log = logging.getLogger("foamkit")

def readInputs(filepath=os.path.join(os.getcwd(), 'inputParameters')):
    """
    Reads a JSON formatted parameters file, while interpreting units and converting values to standard OpenFOAM units (i.e. SI).

    Parameters
    ----------

    filepath: str
            The path of the JSON file location

    Returns: dict
            A Python dictionary of parameters

    """

    with open(filepath, "r") as paramsFile:
        params = json.load(paramsFile, object_hook=_unitDecoder)

    #- Convert (dict or list) of dicts to Pandas dataframe
    for param in params.keys():
        if any(isinstance(params[param], type_) for type_ in [dict, list]):
            items = list(params[param])
            if len(items) > 0 and all([isinstance(item, dict) for item in params[param]]):
                df = pd.DataFrame(params[param])
                df = df.set_index(df.columns[0])

                #for column in params[param].keys():

                #    indicesCheck = params[params.columns[0]].keys()
                #    indices = params[param][column].keys()
                #    logger.debug(indices)
                #    if indices != indicesCheck:
                #        log.error("Inputs file has invalid format. Dataframe indices are not consistent for column'"+param+"'.")

                #    columnList = []
                #    for index in list(indices):
                #        columnList.append(params[param][index])
                #        logger.debug(columnList)
                #
                #    df = df.append(pd.DataFrame(columnList, index=list(indices), columns=[param]))
                #logger.debug(df)
                params[param] = df


    return params
