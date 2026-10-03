from dataclasses import FrozenInstanceError
#from types import NoneType
from foamkit import getFoamKitConfig, setLoggerLevel, userMsg
from foamkit.types import CaseParser, FolderParser, _ofCaseBase, ofDictFile
from dataclasses import field
from pathlib import Path
import json
from pydoc import locate #ref: https://stackoverflow.com/a/29831586/10592330
import sys
from foamkit.functions import isCase
import pandas as pd

import logging

logger = logging.getLogger('foamkit')

# from foamkit.config import DEBUG

def load(path=Path.cwd() / '.params' / '_case.json', _backup=False):
    """
    Read in an OpenFOAM case saved as a JSON object

    Parameters:
        path [str or Path]:  Either filepath or the OpenFOAM case path from
            which data is to read.
    """

    if not isinstance(path, Path):
        path = Path(path)

    if not _backup:
        if isCase(path):
            logger.debug("Specified load path is an OpenFOAM case.")
            path = path / '.params' / '_case.json'
        elif str(path)[-5:] != '.json':
            path = Path(str(path)+'.json')
        # if str(path)[-5:] == '.json':
        #    path = Path(str(path)[:-5])


    # def toOfType(dict_):
    #     if '_type' in dict_:
    #         logger.debug(f"_type: {dict_['_type']}")
    #         if dict_['_type'] == 'ofFolder':
    #             #TODO:  THis reads folder from existingpath rathr than copying
    #             # obj = FolderParser(path=dict_['_path']).makeOFFolder()
    #             obj = FolderParser(path=dict_['_path']).initOFFolder()
    #         elif dict_['_type'] =='ofCase':
    #             obj = CaseParser().initOFCase()
    #         else:
    #             type_ = locate('foamkit.types.'+dict_['_type'])
    #             try:
    #                 obj = type_()
    #             except TypeError:
    #                 logger.error(f"Could not find suitable type: {dict_['_type']}.")
    #                 raise Exception
    #             for key, value in dict_.items():
    #                 if key != '_type': # type property is set automatically
    #                     logger.debug(f"Setting attribute {key}")
    #                     obj.__setattr__(key, value)
    #             return obj
    #     else:
    #         return dict_)

    setLoggerLevel("DEBUG" if getFoamKitConfig('debug')
                    else "INFO")

    if not path.is_file():
        userMsg("No cached case data found.  Run 'pf init'"\
            " before 'pf edit'.", "WARNING")
        return None

    with open(path, 'r') as fp:
        # caseDict = json.load(fp, object_hook=toOfType)
        caseDict = json.load(fp)

    logger.debug(f"caseDict: {caseDict}")



    def _parseCaseDict(obj, case=None, tabStr=None):
        """
        Recursrively parse a JSON dictionary representation of an ofCase

        Parameters:
            obj [any] : The current object being parsed.  Initial object should 
                be the caseDict.

            obj_ is the ofCase representation of the caseDict.

            tabStr is for debugging purposes only.
        """
        if tabStr is None:
            tabStr = ''
        else:
            tabStr += '    '
        logger.debug(f"{tabStr}Starting 'parseCaseDict' iteration")
        logger.debug(f"{tabStr}obj: {obj}")
        logger.debug(f"{tabStr}Parsing type {type(obj)}.")
        if isinstance(obj, dict):
            if '_type' in obj.keys():
                logger.debug(f"{tabStr}Parsing {obj['_type']}.")
                # if obj['_type'] == 'ofFolder':
                #     #TODO:  This reads folder from existing path rather than 
                #     # copying 
                #     # obj = FolderParser(path=dict_['_path']).makeOFFolder()

                #     attrList = []

                #     for key, value in obj.items():
                #         value_ = _parseCaseDict(value)
                #         type_ = type(value_)
                #         # attrList.append((key, type_, field(default=value_)))
                #         if isinstance(value_, ofDictFile): 
                #             attrList.append((key, type_, 
                #                         field(default_factory=type_)))
                #         else:
                #             attrList.append((key, type_, value_))

                #     # attrList = [(key, _parseCaseDict(value, tabStr)) 
                #     #                 for key, value in obj.items()]

                #     # #- Sort list so default underscore arguments are at end:
                #     # attrList = []
                #     # for key, value in reversed(attrList_):
                #     #     if key.startswith('_'):
                #     #         attrList.append((key, value))
                #     #     else:
                #     #         attrList.insert(0, (key, value))  

                #     obj_ = FolderParser(path=obj['_path']).loadOFFolder(
                #                 attrList)
                #     return obj_

                parseValue = True

                if obj['_type'] == 'ofFolder':
                    if case is None:
                        userMsg("Top level object is not ofCase in JSON cache.",
                         "ERROR")
                        sys.exit()
                    obj_ = FolderParser(case, path=obj['_path']).initOFFolder()
                    logger.debug(f"{tabStr}Defined obj_: {obj_}")
                elif obj['_type'] =='ofCase':
                    obj_ = CaseParser(path=obj['_path']).initOFCase()
                    case = obj['_name']
                    logger.debug(f"{tabStr}Defined obj_: {obj_}")
                elif obj['_type'] == 'ofDictFile':
                    #TODO: simplify initialization
                    # obj_ = ofDictFile(_name= obj['_name'], 
                    #             _location=obj['_location'])
                    obj_ = ofDictFile(_name= obj['_name']) 
                    logger.debug(f"{tabStr}Defined obj_: {obj_}")
                elif (obj['_type'] == 'ofList' 
                or obj['_type'] == 'ofSplitList'
                or obj['_type'] == 'ofMultilineStatement'):
                    type_ = locate('foamkit.types.'+obj['_type'])
                    obj_ = type_(
                        value = [_parseCaseDict(v, case) for v in obj['_value']]
                        )
                    parseValue = False
                elif (obj['_type'] == 'ofTable'):
                    type_ = locate('foamkit.types.'+obj['_type'])
                    obj_ = type_(value=pd.DataFrame.from_dict(obj['_value']))
                    parseValue = False
                else:
                    type_ = locate('foamkit.types.'+obj['_type'])
                    try:
                        obj_ = type_()
                    except Exception as e:
                        logger.error(f"Could not find suitable type: {obj['_type']}.")
                        raise e
                for key, value in obj.items():
                    logger.debug(f"{tabStr}Parsing key {key}.")
                    if (key != '_type' 
                        and not (not parseValue and key == '_value')):
                        logger.debug(f"{tabStr}Setting key {key}.")
                        value_ = _parseCaseDict(value, case, tabStr)
                        logger.debug(f"{tabStr}value_: {value_}")
                        logger.debug(f"{tabStr}obj_: {obj_}")
                        try:
                            setattr(obj_, key, value_)
                        except FrozenInstanceError:
                            logger.warning(f"{tabStr}Could not set frozen "\
                                f"instance key: {key}: {value}.")
                logger.debug(f"{tabStr}Returning {obj_}.")
                return obj_
            else:
                return obj
        else:
            logger.debug(f"{tabStr}Returning {obj}.")
            return obj
            
    case_ = _parseCaseDict(caseDict)


    if isinstance(case_, _ofCaseBase):
        return case_
