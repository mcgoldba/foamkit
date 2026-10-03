from dataclasses import dataclass, field, make_dataclass
#from selectors import EpollSelector
from typing import List, Callable
import types
import copy
from pathlib import Path
import os
import sys
import string #- to check for whitespace
import re
import pandas as pd
import copyreg
import json
from pydoc import locate #ref: https://stackoverflow.com/a/29831586/10592330
import keyword # To check if ofDict, ofCase, or ofFolder attribute is reserved
import subprocess
import numpy as np
import shutil
from math import isclose

from inspect import signature #- just for debugging

from pyfoamd import setLoggerLevel, userMsg, getPyFoamdConfig, FOAM_VERSION
from ._isDictFile import _isDictFile
from ._isCase import _isCase

from rich.console import Console
console = Console()

import logging

# log = logging.getLogger('pyfoamd')

#from pyfoamd.richLogger import logger
logger = logging.getLogger('pf')

OF_BOOL_VALUES = {
    'on': True, 'off': False, 'true': True, 'false': False, 
    'yes': True, 'no':False
    }
TAB_SIZE = 4
OF_HEADER = ["/*--------------------------------*- C++ -*----------------------------------*\\",
"  =========                 |",
"  \\\\      /  F ield         |",
"   \\\\    /   O peration     |",
"    \\\\  /    A nd           |",
"     \\\\/     M anipulation  |",
"\\*---------------------------------------------------------------------------*/",
""]
#- Build the string to be used as a tab
TAB_STR = ""
TAB_STR_DEBUG = ""
for _ in range(TAB_SIZE): TAB_STR+= " "

BRACKET_CHARS = {
    'dict': ['{', '}'],
    'list': ['(', ')'],
    'verbatim': [
        ['"', '"'],
        ['{', '}'],
        ['#{', '#}']
    ]
}

COMMENT_TAG = "_comment_"
UNNAMED_TAG = "unnamed_"
TIME_PREFIX = "t_"
SPECIAL_CHARS = {'(': '_',  # Replacement of special chars attribute 
                 ')': '_',  # assignment of name.  Assume that key value 
                 ',': '_',  # doesnt start with '('
                 '*': '_',
                 ':': '_',
                 '.': '_',
                 '-': '_',
                 ' ': '_',
                 '"': '_',
                 '|': '_'}
def printNameStr(name) -> str:
    if (name is None 
    or re.match(UNNAMED_TAG+'[0-9]+$', name)):
        # name=''
        return ''
    if len(name) >= 12:
        return name+"\t"
    else:
        return "{: <12}".format(name)


def _interpretValue(value):
    if isinstance(value, float):
        return ofFloat(value)

TYPE_REGISTRY = []


def _populateRegistry(path):
    reg = []

    #return field(default_factory=lambda: copy.copy(reg))
    return reg

#TODO: Common functionality for all ofTypes (e.g. print str as OpenFOAM entry)
@dataclass
class _ofTypeBase:
    """
    Common base class to group all ofTypes
    """
    # _type: type = field(init=False, default=None)

    # def __post_init__(self):
    #     self._type = type(self)  # Store type to reconstruct class from json

    @property
    def _type(self):
        return str(self.__class__).split()[-1].strip("'<> ").split('.')[-1]
        #return type(self)

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            # if isinstance(v, _ofTypeBase) and hasattr(super(type(v), v), '__setattr__'):
            #     print(f"Found ofType with setattr: {type(v)}.")
            #     super(type(v), v).__setattr__(k, copy.deepcopy(v, memo))    
            # else:
            #     setattr(result, k, copy.deepcopy(v, memo))
            setattr(result, k, copy.deepcopy(v, memo))
        # if hasattr(result, '_name'):
        #     print(f"ofTypeBase updated {result._name}.")
        # else:
        #     print(f"ofTypeBase updated {type(result)}.")
        
        return result


    def attrDict(self):
        """
        Return the class __dict__ with the _type propeerty added.  Used for
        writing class to JSON to be loaded later.
        """
        return dict(vars(self), _type=self._type)

@dataclass
class _ofFolderItemBase(_ofTypeBase):
    """
    Common base class to store all types allowed in an ofFolder
    """
    pass

@dataclass 
class _ofUnnamedTypeBase(_ofTypeBase):
    """
    Base class for unnamed values.  'value' should be stored as a Python type.
    For derived classes where the conversion from python type back to the ofType
    is not intuitive, a secondary '_value' attribute should be defined that
    stores the appropriate string repesentation of the OpenFOAM value.
    
    Iterable derived types (e.g. ofList) should store ofTypes as values.

    """
    value : str = None
    _comment: str = None

    #TODO:  Make sure values print correctly for all types when accessing class 
    #       in console (currently doesn't work for ofDictFile)
    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return self.__str__()

@dataclass
class ofWord(_ofUnnamedTypeBase):
    """
    An OpenFOAM word is a specialization of a string with no whitespace,
    quotes, slashes, semicolons, or brace brackets
    """
    # TODO: Update to property with setter.  THis does not parse modifications
    #       of an existing ofWord object

    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, v):
        if v is not None:
            self._value = str(v).strip()
        else:
            self._value = None

    def __post_init__(self):
        FORBIDDEN_VALUES = ['"', "'", '\\', '/', ";", '{', '}']
        if (self.value is not None 
            and (any([fv in self.value for fv in FORBIDDEN_VALUES])
            or any([c in self.value for c in string.whitespace]))):
            raise ValueError("String cannot be converted to a word.")

    def toString(self, ofRep=False, indent=True) -> str:
        if indent:
            str_ =  printNameStr(self.value.strip())
        else:
            str_ = str(self.value.strip())

        if ofRep:
            str_ += "; "
        
        if self._comment is not None:
            str_ += " //"+str(self._comment)

        str_ += "\n"

        return str_

    

@dataclass 
class _ofNamedTypeBase(_ofUnnamedTypeBase):
    """
    Base class for named values.  'value' should be stored as a Python type.
    For derived classes where the conversion from python type back to the ofType
    is not intuitive, a secondary '_value' attribute should be defined that
    stores the appropriate string repesentation of the OpenFOAM value.

    Iterable derived types (e.g. ofList) should store ofTypes as values.

    call signatures:
        with single argument:   _ofNamedTypeBase(value)
        with two arguments:     _ofNamedTypeBase(name, value)

    """
    #TODO:  Can I get call signatures to show name as well?

    # name: str = None
    #_name: str = None
    # value : str = None

    # def __post_init__(self, *args, **kwargs):
        #     logger.debug(f"_ofNamedType len(args): {len(args)}")
        # if len(args) == 1:
        #     self.value = args[0]
        #     self.name = None
        # elif len(args) == 2:
        #     self.name = args[0]
        #     self.value = args[1]
        # else:
        #     logger.debug("Setting name to 'None'")
        #     self.name = kwargs.pop('name', None)
    # def __init__(self, arg1=None, arg2=None, **kwargs):
    def __init__(self, arg1=None, arg2=None, name=None, value=None, 
        _comment=None):
        # logger.debug(f"Initializing _ofNamedType.  arg1: {arg1}; arg2: {arg2}")
        if arg1 == None and arg2 == None:
            self.value : str = value
            # logger.debug("Setting ofNamedType .name")
            self.name : str = name
        elif arg2 == None:
            self.value : str = arg1
            # logger.debug("Setting ofNamedType .name")
            self.name : str = name
        else:
            # logger.debug("Setting ofNamedType .name")
            self.name : str = arg1
            self.value : str = arg2
        # if 'name' in kwargs.keys():
        #     self.name = kwargs.pop('name')
        # if 'value' in kwargs.keys():
        #     self.value = kwargs.pop('value')
        # if '_comment' in kwargs.keys():
        #     self._comment = kwargs.pop('_comment')
        if name is not None:
            self.name = name
        # super(_ofNamedTypeBase, self).__init__(value, _comment)

    # def __init__(self, name=None, value=None, _comment=None):
    #     self.name = name
    #     super(_ofNamedTypeBase, self).__init__(value, _comment)

    #- Alternative constructor
    # ref: https://realpython.com/python-multiple-constructors/#providing-multiple-constructors-with-classmethod-in-python
    # @classmethod
    # def unnamed(cls, value):
    #     return cls(value=value, name=None)

    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, n):
        # logger.debug(f"name: {n}")
        if n is not None:
            # logger.debug(f"n.split(): {n.split()}")
            if len(n.split()) != 1:
                raise ValueError("Name must be a single word.")
            #TODO: Keywords can accept optional values.
            #       e.g. "(U|p|epsilon|omega)" 
            # try:
            #     ofWord(n)
            # except ValueError:
            #     raise ValueError(f"The name '{n}' is not a valid key.")

            self._name = n
        else:
            self._name = n


    #- for dict() conversion; ref: https://stackoverflow.com/a/23252443/10592330
    def __iter__(self):
        for key, value in self.__dict__.items():
            yield (key, value)

    #TODO:  seprate the ofRep argument?  This may prevent all derived classes
    #       from having to implement this.
    def toString(self, ofRep=False, indent=True) -> str:
        if indent:
            str_ =  printNameStr(self.name)+str(self.value)
        else:
            if self.name is None:
                str_ = str(self.value)
            else:
                str_ = f"{self.name} {self.value}"


        if ofRep:
            str_ += "; "
        
        if self._comment is not None:
            str_ += " //"+str(self._comment)

        str_ += "\n"

        return str_

    def __str__(self):
        return self.toString().rstrip(';\n')



@dataclass
class ofTimeReg(_ofTypeBase):
    
    def __iter__(self):
        for key, value in self.__dict__.items():
            yield (key, value)

@dataclass
class ofHeader(_ofTypeBase):
    # _rawLineList : list = None
    # line1 : str = field(init=False, default="")
    # line2 : str = field(init=False, default="")
    # line3 : str = field(init=False, default="")
    # line4 : str = field(init=False, default="")
    # line5 : str = field(init=False, default="")


    def __init__(self, rawLineList=None):
        
        if rawLineList is None:
            rawLineList = OF_HEADER

        self.line1 = rawLineList[1][29:] or '\n'
        self.line2 = rawLineList[2][29:] or ' OpenFOAM: The Open Source CFD Toolbox'
        self.line3 = rawLineList[3][29:] or \
            (f' Version:  {FOAM_VERSION}\n' if FOAM_VERSION.startswith('v')
            else ' Website:  https://openfoam.org\n') 
        self.line4 = rawLineList[4][29:] or \
            (' Web:      www.OpenFOAM.com\n' if FOAM_VERSION.startswith('v')
            else f' Version:  {FOAM_VERSION}\n')
        self.line5 = rawLineList[5][29:] or '\n'


        for i, line in enumerate(
            [self.line1, self.line2, self.line3, self.line4]):
            # logger.debug(f"line: {line}")
            if len(line) > 51:
                userMsg(f"Header line length is too long.  Value will be \
                    truncated:\n {line[:51]}")
                self.__setattr__('line'+str(i), line[:51])

    def toString(self, ofRep=False):
        headerStr = OF_HEADER[0]+'\n'
        headerStr += OF_HEADER[1]+self.line1
        headerStr += OF_HEADER[2]+self.line2
        headerStr += OF_HEADER[3]+self.line3
        headerStr += OF_HEADER[4]+self.line4
        headerStr += OF_HEADER[5]+self.line5
        headerStr += OF_HEADER[6]+'\n'

        return headerStr




# @dataclass(frozen=True)
# class ofFolder:
#     _path: Path
#     #_path: Path = field(init=False)
#
#     def __post_init__(self):
#         #object.__setattr__(self, '_name',
#                            # Path(self._input).name or self.__input)
#         object.__setattr__(self, '_path', Path(self._path))
#         # self._name = Path(self._input).name or self.__input
#         # self._path = Path(self._input) or Path.cwd() / self.__input
#
#
#
#         addDirs = []
#         for obj in self._path.iterdir():
#             if obj.is_dir():
#                 fields = list(self.__dict__.keys())
#                 if any([obj.name == field_ for field_ in fields]):
#                     warnings.warn(f"'{obj.name}' is a reserved attribute.  "
#                                   "Skipping directory: {obj} ")
#                     continue
#                 addDirs.append((obj, ofFolder(obj)))
#
#         self.__class__ = make_dataclass('ofFolder',
#                                         addDirs,
#                                         bases=(ofFolder,), frozen=True)


def _checkReserved(name, reserved=[]):
    """
    Check if the dictionary key is a Python reserved value or member of 
    `reserved`.  If so, this causes issues with the dot access of variables in
    the Python console.
    Append an `_` to these keys and remove underscore when printing to string.
    """
    while name in keyword.kwlist or name in reserved:
        name += "_"
    
    return name

def _parseNameTag(itemName):
    """
    Replace any special characters not allowed in python attribute names with a 
    suitable replacement, as specified in the `SPECIAL_CHARS` variable.
    """
    name_ = ""

    #Assume numeric values are times, and replace with t_##
    try: 
        float(itemName.rstrip('.orig'))
        name_='t_'
    except:
        pass
    for c in itemName:
        found=False
        for special in SPECIAL_CHARS.keys():
            if c == special:
                name_+= SPECIAL_CHARS[special]
                found = True
                break
        if not found:
            name_ += c
    # if name_ != itemName:
        # logger.debug(f"Revised name string from '{itemName}' to "\
            # f"'{name_}'")
    return name_

# @dataclass(frozen=True)
@dataclass
class _ofFolderBase(_ofFolderItemBase):  
    # TODO:  Cannot add files or folders to an existing ofFolder instance
    _path: str = None
    _type: type = 'ofFolder'

    def __deepcopy__(self, memo=None):
        copy_ = FolderParser(self._path).initOFFolder()
        # copy_.__dict__ = copy.deepcopy(self.__dict__)

        # ref: https://stackoverflow.com/a/15774013/10592330 
        # memo[id(copy_)] = copy_
        for k,v in self.__dict__.items():
            print(f"{TAB_STR_DEBUG}start ofFolder deepcopy: {k}, {type(v)}")
            # try: 
            if isinstance(v, types.MappingProxyType):
                print(f"{TAB_STR_DEBUG}Found mappingproxy object {k}.")
                setattr(copy_, k, v)
            # elif isinstance(v, _ofTypeBase) and hasattr(super(type(v), v), '__setattr__'):
            #     print(f"Found ofType with setattr: {type(v)}.")
            #     super(type(v), v).__setattr__(k, copy.deepcopy(v, memo))  
            else:
                print(f"{TAB_STR_DEBUG}Setting {k} to {v} in deepcopy.")
                setattr(copy_, k, copy.deepcopy(v, memo))
            # except Exception as e:
            #     print(f"Error deep copying attribute {k}: {e}.\nFalling back to shallow copy.")
            #     setattr(copy_, k, v)  # Fallback to shallow copy
     
    # def __deepcopy__(self, memo=None):
    #     if memo is None:
    #         memo = {}

    #     copy_ = FolderParser(None, self._path).initOFFolder()
    #     memo[id(self)] = copy_

    #     for k, v in self.__dict__.items():
    #         try: 
    #             if isinstance(v, types.MappingProxyType):
    #                 # Handle mappingproxy objects separately
    #                 setattr(copy_, k, v)
    #             else:
    #                 setattr(copy_, k, copy.deepcopy(v, memo))
    #         except Exception as e:
    #             print(f"Error copying attribute {k}: {e}")
    #             setattr(copy_, k, v)  # Fallback to shallow copy
        

        return copy_

    def __iter__(self):
        # logger.debug(f"self: {self}")
        # logger.debug(f"vars(self).keys(): {vars(self).keys()}")
        for key in vars(self).keys(): 
            if isinstance(self.__getattribute__(key), ofDict):
                yield (key, dict(self.__getattribute__(key)))
            elif isinstance(self.__getattribute__(key), _ofFolderBase):
                yield (key, dict(self.__getattribute__(key)))
            elif isinstance(self.__getattribute__(key), _ofTypeBase):
                yield (key, self.__getattribute__(key).value)
            else:
                yield (key, self.__getattribute__(key))

    def __setattr__(self, key, value):
        if key == '_name':
            logger.debug(f"{TAB_STR_DEBUG}Setting ofFolder attribute: {key}: {type(value)}")
        if isinstance(value, _ofFolderItemBase):
            # print(f"value._type: {value._type}")
            if hasattr(value, "_name") and value._name is None:  # ofFolders do not have a "_name" attribute
                # print(f"value._name: {value._name}")
                value._name = key
                # value.update({'_name': value._name})
                # key_ = _parseNameTag(key_)
                # key_ = key
                # print(f"value._name: {value._name}")
            # logger.debug(f"ofFolder adding attribute {key_} as {value}")
            # super(_ofFolderBase, self).__setitem__(key_, value)
            super(_ofFolderBase, self).__setattr__(key, value)
            super(_ofFolderBase, self).__dict__[key] =  value

        elif key.startswith('_'):
            # logger.debug(f"ofFolder adding attribute {key} as {value}")
            # super(_ofFolderBase, self).__setitem__(key, value)
            # super(_ofFolderBase, self).__setattr__(key, value)
            # super(_ofFolderBase, self).__dict__[key] =  value
            self.__dict__[key] =  value
        else:
            # userMsg(f"Ignoring invalid type for ofFolder attribute: "\
            #     f"{type(value)}", "WARNING")
            raise Exception(f"Ignoring invalid type for ofFolder attribute: "\
                f"{type(value)}")


    def __getitem__(self, key):
        k = _parseNameTag(key)
        return self.__dict__[k]

    def __setitem__(self, key, value):
        self.__setattr__(key, value)

#    def attrDict(self):
#        """
#        Return the class __dict__ with the _type propeerty added.  Used for
#        writing class to JSON to be loaded later.
#        """
#        return dict(vars(self), _type=self._type)

#for deepcopy; ref: https://stackoverflow.com/a/34152960/10592330
def pickleOfFolder(f):
    return _ofFolderBase, (f._path, )

copyreg.pickle(_ofFolderBase, pickleOfFolder)

class FolderParser:  # Class is required because 'default_factory' argument 
                     # 'makeOFFolder' must be zero argument
    def __init__(self, casePath, path=Path.cwd()):
        self.casePath = casePath
        self.path = path

    def makeOFFolder(self):

        # logging.getLogger('pf').setLevel(logging.DEBUG)

        logger.debug(f"Parsing folder: {self.path}")

        # #- Path relative to the case directory
        # caseRelDir = self.path.relative_to(*self.path.parts[:2])

        attrList = [('_path', str, field(default=self.path))]
        
        for obj in (Path(self.casePath) / self.path).iterdir():
        # for obj in Path(self.path).iterdir():
            internalNames = {}
            #- Ignore polyMesh:
            # logger.debug(f"path.name: {Path(self.path).name}")
            # if Path(self.path).name == 'constant' and obj.name == 'polyMesh':
            if obj.name == 'polyMesh' and obj.is_dir():
                continue

            #- Ignore .eMesh files
            if obj.name.endswith('.eMesh'):
                continue
            #- Ignore .extendedFeatureEdgeMesh files
            if obj.name.endswith('.extendedFeatureEdgeMesh'):
                continue
            #- Prevent invalid ofFolder attribute names:
            name_ = _checkReserved(obj.name, ['_path', '_type'])
            name_ = _parseNameTag(name_)
            if name_.split('_')[0].isdigit():
                #- Add time prefix to time directories
                name_ = TIME_PREFIX+name_
            if obj.is_dir():
                # if obj.name == '_path':
                #     warnings.warn(f"'{obj.name}' is a reserved attribute.  "
                #                 "Skipping directory: {obj} ")
                #     continue
                # print(f"Check that {name_} == {obj.name}")
                if name_ != obj.name:
                    internalNames.update({name_:obj.name})
                
                objPath = obj.relative_to(self.casePath)

                attrList.append((name_, _ofFolderBase,
                    field(default_factory=FolderParser(
                        self.casePath, objPath).makeOFFolder)))
            # - Check for OpenFOAM dictionary files
            if obj.is_file() and _isDictFile(obj):
                # print(f"Check that {name_} == {obj.name}")
                if name_ != obj.name:
                    internalNames.update({name_:obj.name})
               
                attrList.append( (name_, ofDictFile,
                                #field(default=DictFileParser(obj).readDictFile()) )
                                field(default_factory=
                                    DictFileParser(obj).readDictFile) )
                )

        # print(f"attribute list: {attrList}")
        
        dc = make_dataclass('ofFolder', 
                            attrList, bases=(_ofFolderBase, )) #, frozen=True)

        dc_ = dc()

        #- Reset the ofFolder item _name attribute to be the true name with special characters.
        # TODO: Not sure why the revised name is stored as the _name attribute here.
        # logger.debug(f"dc_ dict: {dc_.__dict__}")
        for key, value in internalNames.items():
            # print(f"Reseting name to {value}...")
            # logger.debug(f"Modifying key: {key}")
            dc_.__dict__[key]._name = value
            # print(f"dc_[{key}]._name: {dc_[key]._name}")

        return dc_

    # def loadOFFolder(self, attrList):
    #     """
    #     Create an ofFolder instance from a list of attributes with a "_type"
    #     specification.  (e.g. a dict as loaded from a JSON serialization).   
    #     """

    #     # logger.debug(f"attrList.items(): {list(attrDict.items())}")

    #     # # attrList = list(attrDict.items())

    #     # # for i, item in enumerate(attrList):
    #     # #     attrList[i] = (item[0], type(item[0]), item[1])

    #     # attrList = []
        
    #     # for key, value in attrDict.items():
    #     #     logger.debug(f"attrDict value: {value}")
    #     #     # type_ = locate('pyfoamd.types.'+value['_type'])
    #     #     attrList.append((key, type(value), value))

    #     logger.debug(f"attrList: {attrList}")

    #     dc_ = make_dataclass('ofFolder', 
    #                     attrList, bases=(_ofFolderBase, ), 
    #                     frozen=True)
        
    #     return dc_(self.path)

    def initOFFolder(self):
        """
        Initialize an ofFolder instance. without parsing the directory.   
        """
        # dc_ = make_dataclass('ofFolder', 
        #                 [], bases=(_ofFolderBase, ))
        
        # return dc_(self.path)
        return make_dataclass('ofFolder', 
                         [], bases=(_ofFolderBase, ))(_path=self.path)


@dataclass
class _ofCaseBase(_ofTypeBase):
    _path : Path = field(default=Path.cwd().resolve())
    # _path : Path
    # _location : str = field(default=Path.cwd().parent)
    # _name : str = field(default=Path.cwd().name)
    # _times : ofTimeReg = field(init=False, default=ofTimeReg())
    # _registry : list = _populateRegistry(path)
    constant : _ofFolderBase = field(init=False)
    system : _ofFolderBase = field(init=False)

    def __post_init__(self):
        #self._path = Path(self._location) / self._name
        # logger.debug(f"ofCase post init path: {self._path}")
        if not isinstance(self._path, Path):
            self._path = Path(self._path).resolve()
        if not _isCase(self._path):
            userMsg(f"Specified path is not an OpenFOAM case:\n{self._path}")
        #self._location = str(self._path.parent.resolve())
        self._name = str(self._path.name)
        self.constant = FolderParser(self._path, 'constant').makeOFFolder()
        self.system = FolderParser(self._path, 'system').makeOFFolder()


    @property
    def _path(self):
        # return Path(self._location) / self._name
        return self._path_

    @_path.setter
    def _path(self, pathi):
        # self._location = str(Path(p).parent)
        # self._name = str(Path(p).name)
        self._path_ = Path(pathi).resolve()


    # TODO:  This... print out a tree representation of the case up to 
    #        any ofDictFiles
    # def __str__(self):
    #     return str(self._path)

    def __deepcopy__(self, memo):
        global TAB_STR_DEBUG
        copy_ = CaseParser(self._path).initOFCase()

        # ref: https://stackoverflow.com/a/15774013/10592330 
        # memo[id(copy_)] = copy_
        for k,v in self.__dict__.items():
            # try: 
            if isinstance(v, types.MappingProxyType):
                # Handle mappingproxy objects separately
                setattr(copy_, k, v)
            elif isinstance(v, (_ofTypeBase, _ofFolderBase)):
                setattr(copy_, k, copy.deepcopy(v, memo))
            else:
                setattr(copy_, k, copy.deepcopy(v, memo))
        # except Exception as e:
            #     log.warning(f"Error deep copying attribute {k}: {e}.\nFalling back to shallow copy.")
            #     setattr(copy_, k, v)  # Fallback to shallow copy
 
        # logger.debug(f"dictCopy:\n{dictCopy}")

        # copy_.__dict__.update(dictCopy)
        # copy_.__dict__ = self.__dict__

        return copy_

    # def __deepcopy__(self, memo):
    #     return type(self)(
    #         _times=self._times,
    #         constant = self.constant,
    #         system = self.system
    #         )

    def __iter__(self):
        # logger.debug(f"vars(self).keys(): {vars(self).keys()}")
        for key in vars(self).keys(): 
            if isinstance(self.__getattribute__(key), _ofCaseBase):
                logger.warning("Found ofCase "\
                    f"{self.__getattribute__(key)._name} within ofCase")
                continue
            if isinstance(self.__getattribute__(key), ofDict):
                yield (key, dict(self.__getattribute__(key)))
            elif isinstance(self.__getattribute__(key), _ofFolderBase):
                yield (key, dict(self.__getattribute__(key)))
            elif isinstance(self.__getattribute__(key), ofTimeReg):
                yield (key, dict(self.__getattribute__(key)))
            elif isinstance(self.__getattribute__(key), _ofTypeBase):
                yield (key, self.__getattribute__(key).value)
            else:
                yield (key, self.__getattribute__(key))

    #- make class subscriptable (i.e. case['attr'] access)
    def __getitem__(self, item):
         return getattr(self, item)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def name(self):
        return Path(self._path).name

    def setName(self, name):
        self._path = Path(self._path).parent / name
        self._name = name


    #- Recursively convert an ofCase object (or any type) to a dictionary.
    def toDict(self, obj=None):
        """
        Convert an ofCase to it's python dictionary representation.
        """

        # logger.debug(self)

        if obj is None:
            obj = self

        # Define inner loop to distinush between the user command case.toDict(),
        # and the recursive function returning a `None` object.
        def _toDict(obj):
            logger.debug(f"Parsing obj: {type(obj)}")
            if hasattr(obj, '__dict__'):
                logger.debug(obj.__dict__)

            if isinstance(obj, str):
                return obj
            elif isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, type):
                return str(obj)
            # elif isinstance(obj, ofDictFile):
            #     logger.debug(f"attrDict: {obj.attrDict()}")
            #     # return _toDict(obj.attrDict())
            #     return dict((key, _toDict(val)) for 
            #                     key, val in obj.attrDict().items())            
            # elif isinstance(obj, ofDict):
            #     return dict((key, _toDict(val)) for 
            #                     key, val in obj.attrDict().items())
            elif isinstance(obj, _ofTypeBase):
                logger.debug(f"attrDict: {obj.attrDict()}")
                return dict((key, _toDict(val)) for 
                                key, val in obj.attrDict().items())
                # return _toDict(obj.attrDict())
            elif isinstance(obj, _ofFolderBase):
                logger.debug("Parsing ofFolder")
                return dict((key, _toDict(val)) for 
                            key, val in obj.attrDict().items())
            elif isinstance(obj, pd.DataFrame):
                return obj.to_dict()
            elif isinstance(obj, dict):
                return dict((key, _toDict(val)) for key, val in obj.items())
            elif isinstance(obj, list):
                return [_toDict(val) for val in obj]
            # elif isinstance(obj, _ofTypeBase):
            #     return toDict(dict(obj))
            # elif isinstance(obj, _ofFolderBase):
            #     return toDict(dict(obj))
            # elif isinstance(obj, Iterable):
            #     return [toDict(val) for val in obj]
            elif hasattr(obj, '__dict__'):
                return _toDict(vars(obj))
            elif hasattr(obj, '__slots__'):
                return _toDict(dict((name, getattr(obj, name)) for 
                name in getattr(obj, '__slots__')))
            return obj

        #- Return dictionary with _path property added 
        # (properties are not stored in __dict__)
        return dict(_toDict(obj), _path=str(self._path))

    def save(self, path=Path('.params') / '_case.json'):
        """
        Save the case to a JSON file.

        Parameters:
            path [Path or str]: The path of the case or file to save the JSON 
                data
        """

        #TODO: Path is saved relative to directory originally called and results
        #       in error if loaded from a different directory

        # logger.debug(f"path: {path}")

        if _isCase(path):
            # logger.debug("save: Found case as path!")
            filepath = Path(path) / '.params' / '_case.json'
        else:
            # logger.debug("save: Did not find case as path!")
            filepath = path
         
        if str(filepath)[-5:] != '.json':
            filepath = Path(str(filepath)+'.json')

        # logger.debug(f"case: {self}")

        case_ = self.toDict(self)

        # logger.debug(f"case_: {case_}")

       
        if not Path(filepath).parent.is_dir():
            os.mkdir(Path(filepath).parent)
        
        with open(filepath, 'w')  as fp:
            json.dump(case_, fp, skipkeys=False, indent=TAB_SIZE, 
                        sort_keys=False)

    
    def toJSON(self):
        """
        Convert the case to a JSON object and return as a string.
        """

        case_ = self.toDict(self)

        return json.dumps(case_)

    def write(self):
        """
        Save the case, and overwrite the existing OpenFOAM dictionary case with 
        values in the `ofCase`.  Saves existing case structure in cache for 
        backup.
        """


        # logger.debug(f'self._path: {self._path}')

        #caseFromFile = CaseParser(self._path).makeOFCase()

        #- Save the existing case to file as backup
        self.save(path=self._path)
        n=0
        backupPath = Path(self._path) / '.params' / f'_case.backup{n}'
        while backupPath.is_file():
            n+=1
            backupPath = Path(self._path) / '.params' / f'_case.backup{n}'

        # TODO: Write JSON data as binary to save disk space.
        #- Read in the file that was just saved as binary:
        if (Path(self._path) / '.params' / '_case.json').is_file():
            with open(Path(self._path) / '.params' / '_case.json', 'r') as f_:
                savedCase = f_.read()
                with open(backupPath, 'w') as f:
                    f.write(savedCase)

        def _writeCaseObj(obj, loc=None):
            if loc is None:
                loc = Path(self._path).parent
            # logger.debug(f"_writeCaseObj: parsing obj: {obj}")
            if any([isinstance(obj, t) for t in [_ofCaseBase, _ofFolderBase]]):
                if isinstance(obj, _ofCaseBase):
                    loc_ = Path(loc) / obj._name
                else:
                    loc_ = obj._path
                for key, item in obj.attrDict().items():
                    if not key.startswith('_'):
                        # loc_ = Path(loc) / name_ 
                        _writeCaseObj(item, loc_)
            elif isinstance(obj, ofDictFile):
                # logger.debug(f"ofDictFile obj: {obj}")
                loc_ = self._path / loc / obj._name
                userMsg(f"Writing dictionary {obj._name} to "\
                    f"{str(Path(self.name()) / loc)}.")
                loc_.parent.mkdir(exist_ok=True, parents=True)
                loc_.write_text(obj.toString())

        _writeCaseObj(self)


    def allRun(self, cmd='Allrun'):
        """
        Run the specified run script.
        
        Parameters:
            cmd [str]:  The script to run.  Default value is 'Allrun'.

        """
        script_ = str(Path(self._path)/ cmd)
        userMsg(f"Running Allrun script from {self._path}.")
        try:
            subprocess.check_call(script_, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed with return code: {e.returncode}")
            if e.output:
                logger.error(f"Output: {e.output.decode()}")  # stdout, if captured
            if e.stderr:
                logger.error(f"Error output: {e.stderr.decode()}")  # stderr, if captured

#for deepcopy; ref: https://stackoverflow.com/a/34152960/10592330
def pickleOfCase(f):
    return _ofCaseBase, (f._path, )

copyreg.pickle(_ofCaseBase, pickleOfCase)

class CaseParser:
    def __init__(self, path=Path.cwd()):
        if not isinstance(path, Path):
            self.path = Path(path)
        else:
            self.path = path
  
    def makeOFCase(self):

        debug = True if getPyFoamdConfig('debug') == 'True' else False

        setLoggerLevel("DEBUG" if debug else "INFO")

        # logging.getLogger('pf').setLevel(logging.DEBUG)

        attrList = []
        # attrList = [
        #     # ('_path', Path, field(default=path)),
        #     ('_location', str, field(default=str(path.parent))),
        #     ('_name', str, field(default=path.name)),
        #     ('_times', ofTimeReg,  field(default=ofTimeReg())),
        #     ('constant', _ofFolderBase, 
        #         field(default=FolderParser('constant').makeOFFolder())),
        #     ('system', _ofFolderBase, 
        #         field(default=FolderParser('system').makeOFFolder()))
        #     # ('_registry', list, field(default=_populateRegistry(path)))
        # ]
        for obj in self.path.iterdir():
            
            if (obj.is_dir() and all(obj.name != default for default in
                                    ['constant', 'system'])):
                # fields = [attr[0] for attr in attrList]
                # logger.debug(f"_ofCaseBase: \
                    # {_ofCaseBase}")
                # logger.debug(f"obj: {obj}")
                if obj.name.startswith('.'):
                    #- ignore hidden directories.
                    continue
                #- ignore large directories
                if (obj.name.startswith('processor')
                 or obj.name.startswith('postProcessing')):
                    continue
                fields = [attr[0] for attr in vars(_ofFolderBase).keys()]
                # if any([obj.name == field for field in fields]):
                #     warnings.warn(f"'{obj.name}' is a reserved attribute.  "
                #                 "Skipping directory: {obj} ")
                #     continue
                name_ = _checkReserved(obj.name.replace('.', '_'), fields)
                
                # logger.debug(f"digit test value: {name_.split('_')[0]}")

                if name_.split('_')[0].isdigit():
                    #- rename time directories to t_<tiime>
                    name_ = TIME_PREFIX+name_

                # folderPath_ = self.path / obj.name
                folderPath_ = obj.name
                # attrList.append((name_, _ofFolderBase, 
                #     field(default=FolderParser(
                #         self.path, folderPath_).makeOFFolder())))
                # Ensure attrList uses default_factory for mutable defaults
                # attrList.append((name_, _ofFolderBase, 
                #                 field(default_factory=lambda: copy.deepcopy(FolderParser(self.path, folderPath_).makeOFFolder()))))
                attrList.append((name_, _ofFolderBase, 
                        field(default_factory=lambda path=folderPath_, casePath=self.path: FolderParser(casePath, path=path).makeOFFolder())))

        # dc_ =   make_dataclass('ofCase', attrList, 
        #                         bases=(_ofCaseBase, ))(
        #     str(path.parent), path.name,  
        #     ofTimeReg(),
        #     FolderParser('constant').makeOFFolder(),
        #     FolderParser('system').makeOFFolder()
        # )

        dc_ =   make_dataclass('ofCase', attrList, 
                                bases=(_ofCaseBase, ))
        #- Prevvent error relating to mutable default values:
        # dc_ = make_dataclass('ofCase', attrList, bases=(_ofCaseBase, ))(
        #     _path=self.path,
        #     t_0_orig=field(default_factory=lambda: FolderParser(self.path, folderPath_).makeOFFolder())
        # )


        return dc_(_path=self.path)

    def initOFCase(self):

        return make_dataclass('ofCase', [], 
                                bases=(_ofCaseBase, ))(_path=self.path)

# @dataclass
# class _ofDictFileBase:
#     #store: dict()
#     #update: dict(*args, **kwargs)
#     #value: dict = field(default_factory=lambda:{})
#     pass

    # def __getitem__(self, key):
    #     return self.store[self._keytransform(key)]
    #
    # def __setitem__(self, key, value):
    #     self.store[self._keytransform(key)] = value
    #
    # def __delitem__(self, key):
        #     del self.store[self._keytransform(key)]
    #
    # def __iter__(self):
    #     return iter(self.store)
    #
    # def __len__(self):
    #     return len(self.store)
    #
    # def _keytransform(self, key):
    #     return key


#TODO: Eliminate this class
# @dataclass
# class _ofDictFileDefaultsBase:
#     _name: str = None


# @dataclass
# class _ofDictBase(dict):
#     #_name: str = None
#     # _value: ofIntBase = None #TODO:  Add value that accepts any type
#     # _nUnnamed: int = field(init=False, default=0)
#     # _entryTypes: Dict = field(init=False, default_factory=lambda:{})

#     # def __post_init__(self, *args, **kwargs):
#     #     #- Store '_name' as an attribute rather than a dict key
#     #     logger.debug(f"_name: {self['_name']}")
#     #     self.__dict__['_name'] = self['_name']
#     #     del self['_name']

#     #- ref: https://stackoverflow.com/a/27472354/10592330
#     def __init__(self, *args, **kwargs):
#         self._name = kwargs.pop('_name', None)
#         self._entryTypes = {}
#         self._nUnnamed = 0

#         super().__init__(*args, **kwargs)


#     # ref: https://stackoverflow.com/questions/2352181/how-to-use-a-dot-to-access-members-of-dictionary
#     def __getattr__(*args):
#         val = dict.get(*args)
#         return ofDict(val) if type(val) is dict else val
#     def __setitem__(self, item, value=None):
#         nameTag = None
#         logger.debug(f'__setitem__.item: {item}')
#         if isinstance(item, _ofIntBase):  # _ofIntBase is base type for all other ofTypes
#             nameTag = 'name'
#         elif isinstance(item, _ofDictBase):
#             nameTag = '_name'

#         logger.debug(f"nameTag: {nameTag}")
        
#         if nameTag is not None:
#             itemName = item.__getattr__[nameTag]
#             if itemName is None:
#                 self._nUnnamed += 1
#                 name_ = '_unnamed'+str(self._nUnnamed)
#             if '_unnamed' in itemName or itemName == '_name':
#                 userMsg("Found reserved name in dictionary key.", 'WARNING')
#             else:
#                 name_ = item.name
#             return dict.__setitem__(name_, item.value)
#         else:
#             return dict.__setitem__(item, value)

#     __setattr__ = dict.__setitem__
#     __delattr__ = dict.__delitem__

#     _update = dict.update

    
#     def update(self, iterable):
#         if iterable is None:
#             return
#         if isinstance(iterable, _ofIntBase):
#             self._update({iterable.name: iterable.value})
#             # self._entryTypes[iterable.name] = type(iterable)
#         elif isinstance(iterable, _ofDictBase):
#             logger.debug(f"ofDict._name: {iterable._name}")
#             self._update({iterable._name: iterable.__dict__})
#             # self._entryTypes[iterable.name] = type(iterable)
#         else:
#             self._update(iterable)
        

# @dataclass
# class _ofListBase(_ofNamedTypeBase):
#     value: list

#     @property
#     def valueStr(self):
#         str_ = '('
#         for v in self.value:
#             str_+= str(v)+" "
#         return str_.rstrip()+')'

#     def __str__(self):
#         return self.toString().rstrip(';\n')

#     def __list__(self):
#         _list = []
#         return [v.value if isinstance(v, _ofIntBase) else v for v in self.value]

# @dataclass
# class _ofListBase(_ofListBase):
#     name: str = None
#     value: List = field(default_factory=lambda:[])


@dataclass
class _ofIntBase(_ofNamedTypeBase):
    value: int = None

    @property
    def valueStr(self):
        return str(self.value)

@dataclass
class _ofFloatBase(_ofIntBase):
    name: str = None
    value: float = None

# @dataclass
# class _ofBoolBase(_ofIntBase):
#     name: str = None
#     value: None
#     #_valueStr: str = field(init=False)  #User cant pass a value

#     def __post_init__(self):
#         self._valueStr = self.value
#         self.value = OF_BOOL_VALUES[self._valueStr]

@dataclass
class _ofDimensionedScalarBase(_ofFloatBase):
    dimensions: List = field(default_factory=lambda:[])

# @dataclass
# class _ofVectorBase:
#     #name: field(init=False, repr=False)
#     value: List = field(default_factory=lambda:[])


#     #- Ensure the value is numeric list of length 3
#     @property
#     def value(self):
#         return self._value

#     @property
#     def valueStr(self):
#         return "("+str(self.value[0])+ \
#                 " "+str(self.value[1])+ \
#                 " "+str(self.value[2])+")"

#     def __str__(self):
#         return self.toString().rstrip(';\n')

#     @value.setter
#     def value(self, v):
#         if isinstance(v, list) is False:
#             raise TypeError("Value for 'ofVector' must be a list of length 3.  Got '"+str(v)+"'")
#         if (len(v) != 3 or any(isinstance(i, (int, float)) for i in v)
#                 is False):
#             raise Exception("'ofVector' values must be a numeric list of length 3.")
#         self._value = v


# @dataclass
# class _ofVectorDefaultsBase:
#     pass
#     # name: None=None


# @dataclass
# class _ofNamedVectorDefaultsBase(_ofFloatBase):
#     pass

# def ofDictFile(path):
#
#     attrList = [('_path', Path, field(default=path))]
#     valueList = _readOFDictValues(path)
#
#     for obj in valueList:
#         if obj.name == '_path':
#             warnings.warn(f"'{obj.name}' is a reserved attribute.  "
#                           "Skipping entry.")
#             continue
#         attrList.append(tuple(obj.name, type(obj)))
#
#     return make_dataclass('ofDictFile', attrList)

# @dataclass
# class ofDict(DotMap, _ofTypeBase):
#     pass

# class ofDictFile(DotMap):
#     # - TODO: Add ability to read in dictionary entries as python variables
#     #_location : str = field(default=str(Path.cwd()))

#     def __init__(self, *args, **kwargs):
#         self._location = Path(kwargs.pop('_location', Path.cwd()))

#         logger.debug(f"location: {self._location}")

#         super().__init__(*args, **kwargs)
#         self._CLASS_VARS.append('_location')

@dataclass
# class ofInt(_ofDictFileBase, _ofIntBase):
class ofInt(_ofNamedTypeBase):
    def __init__(self, *args, **kwargs):
        super(ofInt, self).__init__(*args, **kwargs)

    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, v):
        if v is not None:
            try: 
                self._value = int(v)
            except ValueError:
                raise ValueError("ofInt value must be an integer.")
        else:
            self._value = None

    # def toString(self) -> str:
    #     return printNameStr(self.name)+str(self.value)+";\n"

    # def __str__(self):
    #     return self.toString().rstrip(';\n')

TYPE_REGISTRY.append(ofInt)

@dataclass
class ofFloat(_ofNamedTypeBase):
    def __init__(self, arg1=None, arg2=None, name=None, value=None, 
        _comment=None):
        super(ofFloat, self).__init__(arg1, arg2, name=name, value=value, 
            _comment=_comment)
    
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        if v is not None:
            try: 
                self._value = float(v)
            except ValueError:
                raise ValueError("ofFloat value must be a numeric.")
        else:
            self._value = None


TYPE_REGISTRY.append(ofFloat)

@dataclass
class ofStr(_ofNamedTypeBase):
    #TODO:  Why do I need to call 'super' here?
    def __init__(self, *args, **kwargs):
        super(ofStr, self).__init__(*args, **kwargs)

TYPE_REGISTRY.append(ofStr)

@dataclass
class ofBool(_ofNamedTypeBase):
    def __init__(self, arg1=None, arg2=None, name=None, value=None, 
    _comment=None):
        super(ofBool, self).__init__(arg1, arg2, name, value, _comment )
    # name: str = None
    # value: bool =  None
    # _valueStr: str = field(init=False, default="None")  #User cant pass a value

    # def __post_init__(self):
    #     if self.value is not None:
    #         self._valueStr = self.value
    #         self.value = OF_BOOL_VALUES[self._valueStr]

    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, v):
        if v is True or v is False:
            self._valueStr=str(v).lower()
            self._value=v
        elif v is not None:
            self._valueStr = v
            self._value = OF_BOOL_VALUES[v]
        else:
            self._valueStr = ""
            self._value = None


    def toString(self, ofRep=False) -> str:
        str_ = printNameStr(self.name)+self._valueStr
        if ofRep:
            str_ += ';\n'
        else:
            str_ += '\n'

        return str_

    def __str__(self):
        return self.toString().rstrip(';\n')

TYPE_REGISTRY.append(ofBool)

#TODO:  Add abilty to get value based on variable name
@dataclass
class ofVar(_ofNamedTypeBase):
    def __init__(self, *args, **kwargs):
        super(ofVar, self).__init__(*args, **kwargs)
    
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        v = str(v)
        if v is not None:
            if len(v.split()) != 1:
                raise ValueError("Name must be a single word.")
            if v.startswith('$'):
                v_ = v[1:]
            else:
                v_ = v
            try:
                ofWord(v_)
            except ValueError:
                raise ValueError(f"The value '{v_}' is not a valid key.")

            self._value = v_
        else:
            self._value = None

    def toString(self, ofRep=False, indent=True) -> str:
        if self.name is not None:
            if indent:
                str_ = printNameStr(self._name)
            else:
                str_ = str(self._name)
        else:
            str_ = ''
        str_ +=  f"${self.value}"
        if ofRep:
            str_+= ";\n"
        else:
            str_+= "\n"
        return str_


    def __str__(self):
        return self.toString().rstrip(';\n')

@dataclass
class ofComment(_ofUnnamedTypeBase):
    def __init__(self, value:str = None, block : bool = False):
        self.value = value 
        self.block = block

    def toString(self, ofRep=False, indent=False):
        if self.value is None:
            return ''
        if not self.block:
            return '//'+self.value+'\n'
        else:
            return '/*'+self.value+'*/'+'\n'


#TODO:   Merge this class with ofSplitList?
@dataclass
class ofList(_ofNamedTypeBase):
    def __init__(self, arg1=None, arg2=None, name=None, value=None, 
    _comment=None):
        super(ofList, self).__init__(
            arg1=arg1, arg2=arg2, name=name, value=value, _comment=_comment
            )
    
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        # logger.debug(f"ofList setter value: {v}")
        if v is not None:
            if isinstance(v, list):
                self._value = v
            else:
                raise ValueError("ofList value must be a list.")
        else:
            self._value = []
    
    def toString(self, ofRep=False, indent=True) -> str:
        if self.name:
            if indent:
                dStr = printNameStr(self.name)+"( "
            else:
                dStr = f"{self.name}("
        else:
            dStr = "("
        if self.value is not None:
            indentStr = TAB_STR if indent else ''
            for v in self.value:
                if isinstance(v, ofDict):
                    dStr2 = v.toString(indent=False).split(" ")
                    for i in range(len(dStr2)):
                        if len(indentStr+dStr2[i]+" ") > 79:
                            dStr2[i] = "\n"+indentStr+dStr2[i]+" "
                        else:
                            dStr2[i] = indentStr+dStr2[i]+" "
                        dStr += dStr2[i]
                elif isinstance(v, list):
                    dStr += indentStr+ofList(value=v).toString(indent=False).strip()
                elif isinstance(v, ofStr):
                    # dStr += f'"{v}"'
                    dStr+= v.toString(indent=False, ofRep=False).rstrip('\n')+" "
                elif hasattr(v, 'toString') and callable(getattr(v, 'toString')):
                    dStr += v.toString(ofRep=False, indent=False).strip()+" "
                else:
                    dStr += str(v).strip()+" "
        dStr = dStr.rstrip()
        if ofRep:
            dStr+= ");\n"
        else:
            dStr+= ")\n"
        return dStr


    def __str__(self):
        return self.toString()
    
    def __iter__(self):
        for item in self.value:
            yield item

TYPE_REGISTRY.append(ofList)

@dataclass
class ofSplitList(ofList):
    def __init__(self, arg1=None, arg2=None, name=None, value=None, _comment=None):
        super(ofSplitList, self).__init__(
            arg1=arg1, arg2=arg2, name=name, value=value, _comment=_comment)

    def toString(self, ofRep=False, indent=True) -> str:
        """ 
        Convert to a string representation.  If ofRep is `True` prints  a string
        conforming to an OpenFOAM dictionry. 
        """
        # logging.getLogger('pf').setLevel(logging.DEBUG)

        if self.name:
            dStr = self.name+"\n(\n"
        else:
            dStr = "(\n"
        if self.value is not None:
            for v in self.value:
                if isinstance(v, ofDict):
                    # logger.debug("Found ofDict.")
                    dStr2 = v.toString(ofRep=ofRep).split("\n")
                    for i in range(len(dStr2)):
                        dStr2[i] = TAB_STR+dStr2[i]+"\n"
                        dStr += dStr2[i]
                elif isinstance(v, list):
                    dStr += TAB_STR+ofList(value=v).toString()
                    # if any(isinstance(v_, t) for v_ in v for t in [list, dict]):
                    #     dStr += TAB_STR+ofSplitList(value=v).toString()
                    # else:
                    #     dStr += TAB_STR+ofList(value=v).toString()

                elif hasattr(v, 'toString') and callable(getattr(v, 'toString')):
                    # dStr :qa+= printNameStr(TAB_STR+k)+v.toString()
                    dStr += TAB_STR+v.toString(ofRep=False, indent=False)
                else:
                    dStr += TAB_STR+str(v)+'\n'
        dStr+= ");\n"
        if not ofRep:
            dStr = dStr.replace(';', '')
        return dStr

@dataclass
class ofTable(ofList):
    def __init__(self, arg1=None, arg2=None, name=None, value=None, _comment=None):
        super(ofTable, self).__init__(
            arg1=arg1, arg2=arg2, name=name, value=value, _comment=_comment)
    _value = None

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        """Convert varoius input types to pd.Dataframe"""

        if v is None:
            self._value = None
            return
        
        # logger.debug(f"value: {v}")

        if isinstance(v, dict):
            self._value = pd.DataFrame.from_dict(v)
            return

        if isinstance(v, pd.DataFrame):
            self._value = v
            return

        def _listParser(val):
            # if isinstance(val, str):
            #     logger.debug("Found string input.")
            #     list_ = DictFileParser()._parseListValues(v)
            if isinstance(val, ofList):
                val = val.value
            # if isinstance(val, ofList):
            #     listValue = []
            #     for val_ in val.value:
            #         logger.debug("Found ofList input.")
            #         # list_ = list(val)
            #         listValue.append(_listParser(val_))
            #         # list_ = [v.value if isinstance(v, _ofTypeBase) else v \
            #         #     for v in val.value]
            #     list_.append(listValue)
            if isinstance(val, list):
                if len(val) == 1:
                    return _listParser(val[0])
                else:
                    listValue = []
                    for val_ in val:
                        # logger.debug("Found list input.")
                        # list_ = [v.value if isinstance(v, _ofTypeBase) else v \
                        #     for v in val]
                        listValue.append(_listParser(val_))
                    return listValue
            elif isinstance(val, _ofTypeBase):
                if isinstance(val.value, list):
                    listValue = []
                    for val_ in val.value:
                        listValue.append(_listParser(val_))
                    return listValue

                else:        
                    return val.value
            else:
                return val
                # logger.error("Unhandled type provided for 'value'.")

        list_ = _listParser(v)

        # logger.debug(f"list_: {list_}")
        #- check that value is a list of lists of equal length
        if (all([isinstance(l, list) for l in list_])
            and all([len(list_[0]) == len(l) for l in list_[1:]])):
            
            table_ = pd.DataFrame()

            if len(list_) > 1:
                if isinstance(list_[0][1], list): # if '(0.0 (1 2 3))' format
                    for item in list_:
                        df_ = pd.DataFrame(item[1], index=[item[0]])
                        table_ = pd.concat([table_, df_])
                else:  # '(0.0 1 2 3)' format
                    for item in list_:
                        df_ = pd.DataFrame(item[1:], index=[item[0]])
                        table_ = pd.concat([table_, df_])
            
                self._value = table_

            else:
                raise Exception("Invalid list formatting for table.")                
        else:
            raise Exception("Invalid list formatting for table.")


    def toList(self):
        list_ = []

        if self.value is not None:
            #TODO:  Why is self.value stored as a dict when loaded from JSON?
            if isinstance(self.value, dict):
                value_ = pd.DataFrame.from_dict(self.value)
            else:
                value_ = self.value
            if isinstance(value_, pd.DataFrame):
                for row in value_.itertuples():
                        list_.append(list(row))
        
        return list_


    def toString(self, ofRep=False) -> str:
        str_ = printNameStr(self.name)+' table '+\
            ofSplitList(self.toList()).toString(ofRep=ofRep)
        return str_
        for v in self.value:
            if isinstance(v, ofDict):
                dStr2 = v.toString().split(" ")
                for i in range(len(dStr2)):
                    dStr2[i] = TAB_STR+dStr2[i]+" "
                    dStr += dStr2[i]
            elif hasattr(v, 'toString') and callable(getattr(v, 'toString')):
                dStr += v.toString()
            else:
                dStr += str(v)+" "
        dStr+= ");"

        if ofRep:
            dStr = dStr.rstrip(';')

        return dStr
    # def toString(self) -> str:
    #     return self.valueStr
    #def toString(self) -> str:
    #    valueStr = '('
    #    valueStr += str(self.value[0])
    #    for i in range(1,len(self.value)):
    #        valueStr += ' '+str(self.value[i])
    #    valueStr += ')'
    #    return printNameStr(self.name)+valueStr+";\n"

    def __str__(self):
        return self.toString().rstrip(';\n')

# @dataclass
# class ofNamedSplitList(ofList, _ofListBase):
#     #- Same as ofList except entries are split on multiple lines according the
#     #  OpenFoam Programmer's Style Guide

#     def toString(self) -> str:
#         printStr = self.name+'\n(\n'
#         for v in self.value:
#             printStr += TAB_STR+str(v)+'\n'
#         printStr += ');\n'
#         return printStr

#     def __str__(self):
#         return self.toString().rstrip(';\n')

@dataclass
class ofBoundBox(ofList):
    def __init__(self, arg1=None, arg2=None, name=None, value=None, _comment=None):
        super(ofBoundBox, self).__init__(
            arg1=arg1, arg2=arg2, name=name, value=value, _comment=_comment)
    _value = None

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        """
        Ensure value is the proper format (list of 2 lists with 3 float entries)
        e.g. [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]
        """

        if v is None:
            self._value = None
            return
        
        # logger.debug(f"value: {v}")

        valid = True

        try:
            assert hasattr(v, '__iter__') # check if iterable
            assert len(v) == 2
            for w in v:
                assert hasattr(w, '__iter__')
        except AssertionError:
            valid = False

        for w in v:
            for i in w:
                try:
                    float(i)
                except ValueError:
                    valid = False
             

        if not valid:
            userMsg("Invalid value.  Value must be nd.array like of size (2,3) \
            with numeric entries")            
        self._value = v


    def toString(self, ofRep=False) -> str:
        # dStr = printNameStr(self.name)+' '
        
        # for v in self.value:
        #     dStr+= ofList(v).toString(ofRep=False).strip()+' '
        # dStr+= ";"

        dStr = printNameStr(self.name)+" "

        if self.value is not None:
            dStr += ofList(self.value[0]).toString(ofRep=False).strip()+" "+\
                ofList(self.value[1]).toString(ofRep=False).strip()+";\n"
        else:
            dStr += ofList([0, 0, 0]).toString(ofRep=False).strip()+" "+\
                ofList([0, 0, 0]).toString(ofRep=False).strip()+";\n"


        if ofRep:
            dStr = dStr.rstrip(';')

        return dStr
    # def toString(self) -> str:
    #     return self.valueStr
    #def toString(self) -> str:
    #    valueStr = '('
    #    valueStr += str(self.value[0])
    #    for i in range(1,len(self.value)):
    #        valueStr += ' '+str(self.value[i])
    #    valueStr += ')'
    #    return printNameStr(self.name)+valueStr+";\n"

    def __str__(self):
        return self.toString().rstrip(';\n')

# @dataclass
# class ofNamedSplitList(ofList, _ofListBase):
#     #- Same as ofList except entries are split on multiple lines according the
#     #  OpenFoam Programmer's Style Guide

#     def toString(self) -> str:
#         printStr = self.name+'\n(\n'
#         for v in self.value:
#             printStr += TAB_STR+str(v)+'\n'
#         printStr += ');\n'
#         return printStr

#     def __str__(self):
#         return self.toString().rstrip(';\n')

@dataclass
class ofMultilineStatement(_ofNamedTypeBase):
    def __init__(self, *args, **kwargs):
        super(ofMultilineStatement, self).__init__(*args, **kwargs)
    
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        if v is not None:
            if isinstance(v, list) and all([isinstance(v_,_ofTypeBase) 
                                                for v_ in v]):
                self._value = v
            else:
                raise ValueError("ofList value must be a list of ofTypes.")
        else:
            self._value = []
    
    def toString(self, ofRep=False) -> str:
        if self.name:
            dStr = printNameStr(self.name)
        else:
            dStr = ""
        if self.value is not None:
            for v in self.value:
                if hasattr(v, 'toString') and callable(getattr(v, 'toString')):
                    dStr += printNameStr('') 
                    dStr += v.toString(ofRep=False).strip()+"\n"
                else:
                    logger.error("Could not find 'toString' method for type "\
                    f"{type(v)}")
                    sys.exit()
            dStr = dStr.rstrip('\n')
        if ofRep:
            dStr+= ";\n"
        else:
            dStr+= "\n"
        return dStr


@dataclass
class ofDict(dict, _ofTypeBase):

    #TODO: Add method or way to delete the entries (i.e. with `None``)
    #TODO: Allow initializtion with a "name" arg.  

   #- ref: https://stackoverflow.com/a/27472354/10592330
    def __init__(self, *args, **kwargs):
        self._name = kwargs.pop('_name', None)
        self._entryTypes = {}
        self._nUnnamed = 0
        #- Keep a list of class variables to filter printed dict items:
        self._CLASS_VARS = ['_CLASS_VARS', '_name', 
                            '_entryTypes', '_nUnnamed']


        if (len(args) == 1 and isinstance(args[0], list)
            and  all([isinstance(v, _ofTypeBase) for v in args[0]])):
            #- Parse list of ofTypes with ofDict().update function
            super(ofDict, self).__init__(**kwargs)
            self.update(args[0])
        else:
            super(ofDict, self).__init__(*args, **kwargs)



    # ref: https://stackoverflow.com/questions/2352181/how-to-use-a-dot-to-access-members-of-dictionary
    __getattr__ = dict.get
    __delattr__ = dict.__setitem__


    
    def __setitem__(self, item, value=None):
        nameTag = None

        if isinstance(item, ofDict):
            nameTag = '_name'
        # elif isinstance(item, ofComment):
        #     nameTag = None #ofComments havve no names
        elif isinstance(item, _ofNamedTypeBase):
            nameTag = 'name'
        
        if isinstance(value, _ofNamedTypeBase):
            #- item = key and value = ofType
            value._name = item

        if nameTag is not None:
            # logger.debug("****Processing ofDict entry name for specification as "\
                # "attribute.")
            # itemName = item.__getattr__[nameTag]

            # itemName = item.__dict__[nameTag]
            # itemName = item.__dict__['_name']
            itemName = item._name
            if itemName is None:
                self._nUnnamed += 1
                name_ = UNNAMED_TAG+str(self._nUnnamed)
            elif UNNAMED_TAG in itemName or itemName == '_name':
                userMsg("Found reserved name in dictionary key.", 'WARNING')
            elif (any([s in itemName for s in SPECIAL_CHARS.keys()])
                and itemName != '_name'):
                #- Replace special chars with attribute acceptable string
                name_ =_parseNameTag(itemName)

            else:
                # name_ = item.name
                name_ = itemName
            self.__setattr__(name_, item)

        else:
            #- convert the python type to an ofType
            # type_, value_ = DictFileParser._parseValue(item)
            # ofValue = type_(name=item, value=value_)
            # super(ofDict, self).__setattr__(ofValue.name, ofValue)
            if item is None:
                self._nUnnamed += 1
                item_ = UNNAMED_TAG+str(self._nUnnamed)
            else:
                item_ = _parseNameTag(item)

            self.__setattr__(item_, value)


    def __setattr__(self, key, value):


        key_ = _checkReserved(key)

        def _parseList(obj):
            if not isinstance(obj, list):
                logger.error("Recieved non list type as value.")
                sys.exit()
                # type_, value_ = DictFileParser._parseValue(v)
                # return type_(value)
            else:
                ofType_ = ofSplitList()
                #TODO: Parse lists of lists
                for v in obj:
                    if isinstance(v, list):
                        ofType_.value.append(_parseList(v))
                    else:
                        type_, value_ = DictFileParser._parseValue(v)
                        # logger.debug(f"type, value: {type_}, {value_}")
                        ofType_.value.append(type_(value=value_))
            return ofType_
        if not key.startswith('_'):  #TODO: filter based on self._CLASS_VARS
        # if key not in self._CLASS_VARS:
            if isinstance(value, list):
                ofType = _parseList(value)
                ofType._name = key 
            elif value is not None and not isinstance(value, _ofTypeBase):
                type_, value_ = DictFileParser._parseValue(value)
                ofType = type_(name=key_, value=value_)
            else:
                ofType = value
                if hasattr(ofType, '_name'):
                    if ofType._name is None:
                        ofType._name = key
            self.__dict__[key] = ofType
        else:
            self.__dict__[key] = value

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return self.__str__()

    # #- for dict() conversion; ref: https://stackoverflow.com/a/23252443/10592330
    # def __iter__(self):
    #     logger.debug(f"Inside {self} __iter__.")
    #     for item in vars(self).items():
    #         yield item


    def __deepcopy__(self, memo):
        cls = self.__class__
        # result = cls.__new__(cls)
        result = cls()
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if isinstance(v, (ofDict, ofDictFile)):
                result[k] = copy.deepcopy(v,memo)
                # result[k]["_name"] = v._name
            elif k == '_name':
                result._name = v
            elif k.startswith('_'):
                result[k] = v
            else:
                setattr(result, k, copy.deepcopy(v, memo))
        return result


    def _NoneKey(self):
        self._nUnnamed += 1
        return UNNAMED_TAG+str(self._nUnnamed)
    
    def update(self, iterable):
        #TODO:  Can this function be simplified since self.__setitem__ parses
        #          both ofTypes and built-in python types?
        # logger.debug(f"ofDict initalizer iterable type: {type(iterable)}")
        # logger.debug(f"ofDict initalizer iterable: {iterable}")
        if iterable is None:
            return
        # if (isinstance(iterable, _ofIntBase) 
        #    or isinstance(iterable, _ofNamedTypeBase)):
        if isinstance(iterable, _ofNamedTypeBase):
            # logger.debug(f"Setting item for _ofNamedType.")
            #self.__setitem__(iterable.name, iterable)
            self.__setitem__(iterable)
        elif isinstance(iterable, _ofUnnamedTypeBase):
            self.__setitem__(self._NoneKey(), iterable)
        elif isinstance(iterable, list):
            # listTypes = set([type(item) for item in iterable])
            if all([isinstance(v, _ofTypeBase) for v in iterable]):
                # dict_ = {item.name: item for item in iterable}
                for item in iterable:
                    #self.update(item)
                    try:
                        name = item.name
                    except AttributeError:
                        name = item._name
                    self.__setitem__(name, item)
        elif isinstance(iterable, ofDict):
            # super(ofDict, self).update({iterable._name: iterable.__dict__})
            # self._entryTypes[iterable.name] = type(iterable)
            # #- Append to current ofDict if it exists
            # if (hasattr(self, iterable._name) 
            # and isinstance(getattr(self, iterable._name), ofDict)):
            #     iterable_ = getattr()
            # else:
            #     iterable_ = iterable
            self.__setitem__(iterable._name, iterable)
        elif isinstance(iterable, dict):
            for key, value in iterable.items():
                # if isinstance(value, _ofNamedTypeBase):
                #     self.__setitem__(value)
                # else:
                #     self.__setitem__(key, value)
                self.__setitem__(key, value)
        else:
            self.__setitem__(iterable)

    def toOFString(self) -> str:
        """ 
        Convert to a string representation conforming to an OpenFOAM dictionary 
        entry.
        """
        return self.toString(ofRep=True)
        # if self._name:
        #     dStr = self._name+"\n{\n"
        # else:
        #     dStr = "{\n"
        # for k, v in zip(self.keys(), self.values()):
        #     logger.debug(f"dict entry: {k}: {v}")
        #     if k is None:
        #         k=''
        #     if k not in self._CLASS_VARS:
        #         if isinstance(v, ofDict):
        #             logger.debug("Found ofDict.")
        #             dStr2 = v.toString().split("\n")
        #             for i in range(len(dStr2)):
        #                 dStr2[i] = TAB_STR+dStr2[i]+"\n"
        #                 dStr += dStr2[i]
        #         elif hasattr(v, 'toString') and callable(getattr(v, 'toString')):
        #             # dStr += printNameStr(TAB_STR+k)+v.toString()
        #             dStr += v.toString()
        #             logger.debug("Found 'toString()' method.")
        #         else:
        #             logger.debug("Could not find 'toString()' method.")
        #             dStr += printNameStr(TAB_STR+k)+str(v)+"\n"
        #     logger.debug(f"dict string: {dStr}")
        # dStr+= "}\n"
        # return dStr
    
    def toString(self, ofRep=False) -> str:
        """ 
        Convert to a string representation.  If ofRep is `True` prints  a string
        conforming to an OpenFOAM dictionry. 
        """
        # logging.getLogger('pf').setLevel(logging.DEBUG)

        if self._name:
            dStr = self._name+"\n{\n"
        else:
            dStr = "{\n"
        # for k, v in zip(self.keys(), self.values()):
        for k, v in zip(self.__dict__.keys(), self.__dict__.values()):
            k = k.rstrip('_') # remove possible "_" added in _checkReserved
            # logger.debug(f"dict entry: {k}: {v}")
            if k is None or re.match(UNNAMED_TAG+'_[0-9]+$', k):
                k=''
            if k not in self._CLASS_VARS:
                if isinstance(v, ofDict):
                    # logger.debug("Found ofDict.")
                    dStr2 = v.toString(ofRep=ofRep).split("\n")
                    for i in range(len(dStr2)):
                        dStr2[i] = TAB_STR+dStr2[i]+"\n"
                        dStr += dStr2[i]
                elif isinstance(v, ofList):
                    vList = v.toString(ofRep=ofRep).split('\n')
                    for v_ in vList:
                        dStr+= TAB_STR+v_+'\n'
                    # dStr = dStr.rstrip()
                    # dStr+=';'
                    dStr += '\n'
                elif hasattr(v, 'toString') and callable(getattr(v, 'toString')):
                    # dStr += printNameStr(TAB_STR+k)+v.toString()
                    dStr += TAB_STR+v.toString(ofRep=ofRep)
                    # logger.debug("Found 'toString()' method.")
                else:
                    # logger.debug("Could not find 'toString()' method.")
                    dStr += printNameStr(TAB_STR+k)+str(v)+';\n'

            # logger.debug(f"dict string: {dStr}")
        dStr+= "}\n\n"
        # if not ofRep:
        #     dStr = dStr.replace(';', '')
        return dStr

    #TODO:  can this class be replaced with a dict() conversion?
    def toDict(self):
        """
        Convert value to a dictionary including PyFoamd hidden attributes.
        """  
        return {k: v for k, v in self.__iter__() }

@dataclass
class ofFoamFile(ofDict):

    def __post_init__(self, *args, **kwargs):
        super(ofFoamFile, self).__init__(*args, **kwargs)
        self._name = 'FoamFile'
        



    # def __setitem__(self, key, value=None):

    def toString(self, ofRep=False) -> str:
            """ 
            Convert to a string representation.  If ofRep is `True` prints  a string
            conforming to an OpenFOAM dictionry. 
            """
            # logging.getLogger('pf').setLevel(logging.DEBUG)

            if self._name:
                dStr = self._name+"\n{\n"
            else:
                dStr = "{\n"
            for k, v in zip(self.keys(), self.values()):
                # logger.debug(f"dict entry: {k}: {v}")
                if k is None:
                    k=''
                if k not in self._CLASS_VARS:
                    # if isinstance(v, ofDict):
                    #     logger.debug("Found ofDict.")
                    #     dStr2 = v.toString().split("\n")
                    #     for i in range(len(dStr2)):
                    #         dStr2[i] = TAB_STR+dStr2[i]+"\n"
                    #         dStr += dStr2[i]
                    if (hasattr(v, 'toString') 
                        and callable(getattr(v, 'toString'))):
                        # dStr += printNameStr(TAB_STR+k)+v.toString()
                        # logger.debug(f"FoamFile entry string: "\
                        #     f"{v.toString(ofRep=ofRep)}")
                        dStr += TAB_STR+v.toString(ofRep=ofRep)
                        # logger.debug("Found 'toString()' method.")
                    else:
                        # logger.debug("Could not find 'toString()' method.")
                        dStr += printNameStr(TAB_STR+k)+str(v)+';\n'

                # logger.debug(f"dict string: {dStr}")
            dStr+= "}\n"
            # if not ofRep:
            #     dStr = dStr.replace(';', '')
            return dStr


    def update(self, iterable):

        if isinstance(iterable, _ofTypeBase):        

        # if isinstance(value, _ofTypeBase):
        #     value_ = value
        # else:
        #     value_ = key

            value_ = iterable

            if any([isinstance(value_, t) for t in [ofFloat, ofInt]]):
                if value_.name != "version":
                    userMsg(f"Invalid value '{value_.name}' for {value_._type}.  Only \
                        'version' is allowed.")
                else:
                    super(ofFoamFile, self).update(iterable)
            elif isinstance(value_, ofStr):
                if value_.name in ['version', 'format', 'class', 'object']:
                    super(ofFoamFile, self).update(iterable)
                else:
                    userMsg(f"Invalid value '{value_.name}' for {value_._type}.  Only \
                        'version', 'format', 'class', and 'object' are allowed.")

        

@dataclass
class ofDictFile(ofDict, _ofFolderItemBase):
    
    #TODO:  Define setters to extract name and location from path when defined
    #       Currently need to initialize as ofDictFile(_name=..., _location=...)
    def __init__(self, *args, **kwargs):
        super(ofDictFile, self).__init__(*args, **kwargs)
        # self._location : str = kwargs.pop('_location', 
        #                         str(Path.cwd() / self._name)) \
        #                             if self._name is not None else ""
        self._header : ofHeader = ofHeader()
        # self._foamFile: ofFoamFile = field(default_factory=ofFoamFile)
        self._foamFile: ofFoamFile = None  
        # self._foamFile: ofFoamFile = ofFoamFile() 
        # self._CLASS_VARS.append('_location')
        self._CLASS_VARS.append('_header')
        self._CLASS_VARS.append('_foamFile')

        # logger.debug(f"location: {self._location}")

    #- ref: https://stackoverflow.com/a/27472354/10592330
    # def __init__(self, *args, **kwargs):
    #     self._name = kwargs.pop('_name', None)
    #     self._entryTypes = {}
    #     self._nUnnamed = 0
    #     #- Keep a list of class variables to filter printed dict items:
    #     self._CLASS_VARS = ['_CLASS_VARS', '_name', 
    #                         '_entryTypes', '_nUnnamed']

    #     if (len(args) == 1 and isinstance(args[0], list)
    #         and  all([isinstance(v, _ofTypeBase) for v in args[0]])):
    #         #- Parse list of ofTypes with ofDict().update function
    #         super(ofDict, self).__init__(**kwargs)
    #         self.update(args[0])
    #     else:
    #         super(ofDict, self).__init__(*args, **kwargs)

    #TODO:  Why do I need to replicate this?  Should be inhereted from base
    #       class
    def __str__(self):
        return self.toString()

    #- Iterate only over dict file entries
    # def __iter__(self):


    def toString(self, ofRep=True):
        """
        Prints as an OpenFOAM dictionary representation.
        """
   
        str_ = self._header.toString() if \
            hasattr(self._header, 'toString') else ''
        str_ += self._foamFile.toString(ofRep=True) if \
            hasattr(self._foamFile, 'toString') else ''
        # str_ += super(ofDictFile, self).toString(ofRep=ofRep)
        for k, v in zip(self.__dict__.keys(), self.__dict__.values()):
            # logger.debug(f"dict entry: {k}: {v}")
            if k is None:
                k=''
            if k not in self._CLASS_VARS:
                # if isinstance(v, ofDict):
                #     logger.debug("Found ofDict.")
                #     tStr = v.toString().split("\n")
                #     for i in range(len(tStr)):
                #         tStr[i] = TAB_STR+tStr[i]+"\n"
                #         str_ += tStr[i]
                if hasattr(v, 'toString') and callable(getattr(v, 'toString')):
                    # dStr += printNameStr(TAB_STR+k)+v.toString()
                    str_ += v.toString(ofRep=ofRep)
                    # logger.debug("Found 'toString()' method.")
                else:
                    # logger.debug("Could not find 'toString()' method.")
                    str_ += printNameStr(k)+str(v)+'\n'
                str_ += '\n'
            # logger.debug(f"dict string: {str_}")
        
        if not ofRep:
            str_ = str_.replace(';', '')
        return str_
        # return self._header.toString() + self._foamFile.toString() + \
        #     super(ofDictFile, self).toString()

    # def __delattr__(self, name):
    #     # super(ofDictFile, self).__delitem__(self, name)
    #     # super(ofDictFile, self).__delattr__(self, name)
    #     del self.__dict__[name]

    def clear(self):
        """
        Removes all entries from dictionary file while retaining 
        header information. 
        """
        rmKeys = []

        for key, item in self.items():
            if isinstance(item, _ofTypeBase):
                if isinstance(item, ofComment):
                    if not item.value.startswith('// * * * *'):
                        rmKeys.append(key)
                    continue
                if not (isinstance(item, ofHeader) 
                    or item._name=='FoamFile'):
                    rmKeys.append(key)

        for key in rmKeys:
            del self[key]



@dataclass
class ofDimension(_ofTypeBase):
    dimensions: List = field(default_factory=lambda:[])

    #- Ensure dimensions are a list of length 7 per OpenFOAM convention
    @property
    def dimensions(self):
        return self._dimensions

    @dimensions.setter
    def dimensions(self, d):
        if not isinstance(d, list):
            d = [0, 0, 0, 0, 0, 0, 0]
        if (len(d) != 7 or any(isinstance(i, int) for i in d) is False):
            raise ValueError('Dimensions must be a list of 7 integer values, where each entry corresponds to a base unit type: \
    \n\t1:  Mass - kilogram (kg) \
    \n\t2:  Length - meter (m) \
    \n\t3:  Time - second (s) \
    \n\t4:  Temperature - Kelvin (K) \
    \n\t5:  Quantity - mole (mol) \
    \n\t6:  Current - ampere (A) \
    \n\t7:  Luminous intensity - candela (cd)')
        self._dimensions = d

    def toString(self) -> str:
        #- format the dimensions list properly
        dimStr = "["
        for i in range(6):
            dimStr+= str(self.dimensions[i])+' '
        dimStr+= str(self.dimensions[6])+']'

        return str(dimStr)

    def __str__(self):
        return self.toString().rstrip(';\n')

@dataclass
class ofNamedDimension(ofDimension):
    name : str = None
    def __init__(self, name=None, dimensions=None):
        self.name=name
        super(ofNamedDimension, self).__init__(dimensions=dimensions)

    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, n):
        # logger.debug(f"name: {n}")
        if n is not None:
            # logger.debug(f"n.split(): {n.split()}")
            if len(n.split()) != 1:
                raise ValueError("Name must be a single word.")
            #TODO: Keywords can accept optional values.
            #       e.g. "(U|p|epsilon|omega)" 
            # try:
            #     ofWord(n)
            # except ValueError:
            #     raise ValueError(f"The name '{n}' is not a valid key.")

            self._name = n
        else:
            self._name = n

    def toString(self, ofRep=False) -> str:
        #- format the dimensions list properly
        if self.name is not None:
            dimStr = printNameStr(self.name)
        else:
            dimStr = ""
        
        dimStr += super(ofNamedDimension, self).toString()
        dimStr += ';\n'

        return str(dimStr)

@dataclass
class ofDimensionedScalar(ofFloat):
    def __init__(self, arg1=None, arg2=None, name=None, value=None, 
        dimensions=None, _comment=None):
        # super(ofDimensionedScalar, self).__init__(arg1=arg1, arg2=arg2, name=name, 
        #     value=value, dimensions=dimensions, _comment=_comment )
        ofFloat.__init__(self, arg1=arg1, arg2=arg2, name=name, value=value, 
            _comment=None)
        self.dimension = ofDimension(dimensions)
     

    def toString(self, ofRep=False) -> str:
        # #- format the dimensions list properly
        # dimStr = "["
        # for i in range(6):
        #     dimStr+= str(self.dimensions[i])+' '
        # dimStr+= str(self.dimensions[6])+']'

        str_ = printNameStr(self.name)+str(self.dimension)+" "\
            +str(self.value)
            
        if ofRep:
            str_ += ";\n"

        return str_

    def __str__(self):
        return self.toString().rstrip(';\n')

@dataclass
# class ofVector(_ofUnnamedTypeBase):
class ofVector(_ofNamedTypeBase):
    def __init__(self, arg1=None, arg2=None, name=None, value=None, 
                _comment=None):
        super(ofVector, self).__init__(arg1, arg2, name, value, _comment)


    #- Ensure the value is numeric list of length 3
    @property
    def value(self):
        return self._value

    @property
    def valueStr(self):
        return "("+str(self.value[0])+ \
                " "+str(self.value[1])+ \
                " "+str(self.value[2])+")"

    def __str__(self):
        return self.toString().rstrip(';\n')

    @value.setter
    def value(self, v):
        if v is not None:
            if isinstance(v, list) is False:
                raise TypeError("Value for 'ofVector' must be a list of length 3.  Got '"+str(v)+"'")
            if (len(v) != 3 or any(isinstance(i, (int, float)) for i in v)
                    is False):
                raise Exception("'ofVector' values must be a numeric list of length 3.")
            self._value = v
        else:
            self._value = [0.0, 0.0, 0.0]

    def toString(self, ofRep=False) -> str:
        
        if self.name is not None:
            str_ = printNameStr(self.name)
        else:
            str_ = ''
        
        str_ +=  self.valueStr

        if ofRep:
            str_ += ';\n'
        
        return str_

#        return "("+str(self.value[0])+ \
#                " "+str(self.value[1])+ \
#                " "+str(self.value[2])+")"


@dataclass
class ofSphericalTensor(ofVector):
    
    #- Ensure the value is numeric list of length 3
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        if isinstance(v, list) is False:
            raise TypeError("Value for 'ofVector' must be a list of length 3.  Got '"+str(v)+"'")
        if (len(v) != 1 or any(isinstance(i, (int, float)) for i in v)
                is False):
            raise Exception("'ofSphericalTensor' values must be a numeric list of length 1.")
        self._value = v

@dataclass
class ofSymmTensor(ofVector):
    """
    A symmetric tensor, defined by components '(xx xy xz yy yz zz)'
    """
    
    #- Ensure the value is numeric list of length 3
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        if isinstance(v, list) is False:
            raise TypeError("Value for 'ofVector' must be a list of length 3.  Got '"+str(v)+"'")
        if (len(v) != 6 or any(isinstance(i, (int, float)) for i in v)
                is False):
            raise Exception("'ofSymmTensor' values must be a numeric list of length 6.")
        self._value = v

@dataclass
class ofTensor(ofVector):
    """
    A symmetric tensor, defined by components '(xx xy xz yy yz zz)'
    """
    
    #- Ensure the value is numeric list of length 3
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        if isinstance(v, list) is False:
            raise TypeError("Value for 'ofVector' must be a list of length 3.  Got '"+str(v)+"'")
        if (len(v) != 9 or any(isinstance(i, (int, float)) for i in v)
                is False):
            raise ValueError("'ofTensor' values must be a numeric list of length 9.")
        self._value = v

@dataclass
class ofUniformField(_ofNamedTypeBase):
    #name: str = None
    def __init__(self, arg1=None, arg2=None, name=None, value=None, 
        _comment=None):
        super(ofUniformField, self).__init__(arg1, arg2, name, value, _comment)

    @property
    def name(self):
        return self._name    

    @name.setter
    def name(self, n):
        if n is not None:
            # logger.debug(f"name: {n}")
            n=str(n)
            if len(n.split()) == 2 and n.split()[1] == 'uniform':
                n_ = n.split()[0]
            else:
                n_ = n

            if len(n_.split()) != 1:
                raise ValueError(f"Name must be a single word.  Got {n}")
            try:
                ofWord(n_)
            except ValueError:
                raise ValueError(f"The name '{n_}' is not a valid key.")

            self._name = n_
        else:
            self._name = None

    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, v):
        if v is not None:
            fieldList_ = [ofInt, ofFloat, ofVector, ofSphericalTensor, ofSymmTensor, 
            ofTensor,  ofDimensionedScalar, ofDimensionedVector, 
            ofDimensionedSphericalTensor, ofDimensionedSymmTensor, 
            ofDimensionedTensor, ofVar]
            if v is not None and not any([isinstance(v, t) for t in fieldList_]):
                raise ValueError("'value' attribute must be a valid OpenFOAM field "\
                    f"type. Got {type(v)}, need one of:\n{fieldList_}")
            self._value = v
        else:
            self._value = None

    def toString(self, ofRep=False) -> str:

        str_ = printNameStr(self.name)+"uniform "\
            +str(self.value).strip()
            
        if ofRep:
            str_ += ";\n"

        return str_



# @dataclass
# class _ofNamedVectorBase(_ofNamedTypeBase):
#     name: str = None

# @dataclass
# class ofNamedVector(ofVector, _ofNamedVectorBase):


#     def toString(self, ofRep = True) -> str:
#         str_ =  printNameStr(self.name)+self.valueStr
        
#         if ofRep:
#             str_ += ";\n"



@dataclass
class _ofDimensionedVectorBase(_ofDimensionedScalarBase):
    value: ofVector

@dataclass
class ofDimensionedSphericalTensor(ofSphericalTensor, ofDimension):
    name : str = None

    def toString(self, ofRep = False) -> str:
        str_ = printNameStr(self.name)+self.dimensions+\
            self.value.toString()
            
        if ofRep:
            str_ += ";\n"
        
        return str_

    def __str__(self):
        return self.toString().rstrip(';\n')

@dataclass
class ofDimensionedSymmTensor(ofSymmTensor, ofDimension):
    name : str = None

    def toString(self) -> str:
        return printNameStr(self.name)+self.dimensions+\
            self.value.toString()+";\n"

    def __str__(self):
        return self.toString().rstrip(';\n')

@dataclass
class ofDimensionedTensor(ofTensor, ofDimension):
    name : str = None

    def toString(self) -> str:
        return printNameStr(self.name)+self.dimensions+\
            self.value.toString()+";\n"

    def __str__(self):
        return self.toString().rstrip(';\n')

@dataclass
class ofDimensionedVector(ofDimensionedScalar, _ofDimensionedVectorBase):

    def toString(self, ofRep = False) -> str:
        str_ = printNameStr(self.name)+self.value.toString()
        if ofRep:
            str_ += ";\n"
        else:
            str_ += "\n"
        return str_

    def __str__(self):
        return self.toString().rstrip(';\n')


# def _parseProbeValues(logPath):
#     """
#     Parse the raw string from an OpenFOAM probe log, and 
#     convert to the appropriate components.

#     e.g
#     # Probe 0 (-1.2192 -1.28873 1.75054e-18)
#     # Probe 1 (-0.1905 -3.13339 0.6096)  # Not Found
#     # Probe 2 (0.762 -3.13339 0.6096)  # Not Found
#     # Probe 3 (1.7145 -3.13339 0.6096)  # Not Found
#     # Probe 4 (1 0 0)
#     #       Probe             0             1             2             3             4
#     #        Time
#             1             (-1.72271 -0.0195384 0.0334737)             (-1e+300 -1e+300 -1e+300)             (-1e+300 -1e+300 -1e+300)             (-1e+300 -1e+300 -1e+300)             (-1.58571 2.11359e-05 1.37121e-05)
    
#     is converted to:

#     Probe0_x Probe0_y Probe0_z Probe1_x ...
#     -1.72271 -0.0195384 0.0334737 -1e+300 ...
#     ...

#     Parameters:
#         logPath [str] : path of the log file data to read.

#     Returns:
#         data [nd.array] : a 2D numpy array of values.

#     """

#     v_ = DictFileParser._parseValue(value)

#     if isinstance(v_.value, list):
#          for v in v_.value:
#              logger.debug(f"_parseProbeValues value: {v}")
#              yield v
#     else:
#         logger.debug(f"_parseProbeValues value: {v_.value}")
#         return v_.value

#     # data = np.loadtxt(logPath, delimiter='\t')

#     # logger.debug(data)

#- Define functionEntries types

# @dataclass
# class _ofFunctionEntry(_ofNamedTypeBase)
    # def __init__(self, arg1=None, arg2=None, name=None, value=None, 
    #     _comment=None):
    #     super(_ofFunctionEntry, self).__init__(arg1, arg2, name, value, _comment)

@dataclass
class _ofFunctionEntry(_ofUnnamedTypeBase):
    _feType: str = None
    _vBracketType: int = 1

    @property
    def feType(self) -> str:
        return self._feType

    @feType.setter
    def feType(self, v: str) -> None:
        self._feType = v


    @property
    def vBracketType(self) -> int:
        return self._vBracketType

    @vBracketType.setter
    def vBracketType(self, v: int) -> None:
        self._feType = v

    def toString(self, ofRep=False) -> str:
        pStr = f'#{printNameStr(self.feType)}'
        pStr += BRACKET_CHARS['verbatim'][self.vBracketType][0]
        pStr+= self.value
        pStr += BRACKET_CHARS['verbatim'][self.vBracketType][1]


        if ofRep:
            pStr+=';'
        
        if self._comment is not None:
            pStr+= f" {str(self._comment)}"

        return pStr+'\n'

@dataclass
class ofInclude(_ofFunctionEntry):


    @_ofFunctionEntry.feType.getter
    def feType(self):
        return 'include'
    @_ofFunctionEntry.vBracketType.getter
    def vBracketType(self):
        return 0

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        if v is not None:
            if isinstance(v, str):
                self._value = v.strip('"')
            else:
                raise ValueError(f"The 'include' value must be a string.  Got "\
                    f"'{v}'.")
        else:
            self._value = v


    def toString(self, ofRep=False) -> str:
        return printNameStr(f"#{self.feType}")+'"'+str(self.value)+'"\n\n'

    def __str__(self):
        return self.toString().rstrip('\n')

@dataclass
class ofIncludeEtc(ofInclude):
    
    @_ofFunctionEntry.feType.getter
    def feType(self):
        return 'includeEtc'

@dataclass
class ofIncludeFunc(ofInclude):
    @_ofFunctionEntry.feType.getter
    def feType(self):
        return 'includeFunc'

@dataclass
class ofEval(_ofFunctionEntry, _ofNamedTypeBase):
    code: str = None

    def __init__(self, arg1=None, arg2=None, name=None, value=None, 
        _comment=None):
        # super(ofEval, self).__init__(arg1, arg2, name, value, _comment)
        _ofNamedTypeBase.__init__(self, arg1, arg2, name, value, _comment)

    @_ofFunctionEntry.feType.getter
    def feType(self):
        return 'eval'

    def toString(self, ofRep=False) -> str:
        pStr = f'{printNameStr(self.name)}' if self.name is not None else ''
        pStr += f'#{self.feType}'
        pStr += BRACKET_CHARS['verbatim'][self.vBracketType][0]+" "
        pStr+= self.value
        pStr += " "+BRACKET_CHARS['verbatim'][self.vBracketType][1]


        if ofRep:
            pStr+=';'
        
        if self._comment is not None:
            pStr+= f" {str(self._comment)}"

        return pStr+'\n'

@dataclass
class ofCalc(_ofFunctionEntry):
    code: str = None

    @_ofFunctionEntry.feType.getter
    def feType(self):
        return 'calc'
    
@dataclass #TODO:  toString argument needs modified to allow if else syntax
class ofIf(_ofFunctionEntry):
    code: str = None


    @_ofFunctionEntry.feType.getter
    def feType(self):
        return 'if'

@dataclass
class ofRemove(_ofFunctionEntry):
    code: str = None


    @_ofFunctionEntry.feType.getter
    def feType(self):
        return 'remove'


@dataclass  #TODO:  Should this be a named type
class ofCodeStream(ofEval):
    include: List = None
    options: List = None

    def __init__(self, arg1=None, arg2=None, name=None, value=None, 
        _comment=None):
        super(ofCodeStream, self).__init__(arg1, arg2, name, value, _comment)

    @_ofFunctionEntry.feType.getter
    def feType(self):
        return 'codeStream'

    # def toString(self, ofRep=False) -> str:
    #     """ 
    #     Convert to a string representation.  If ofRep is `True` prints  a string
    #     conforming to an OpenFOAM dictionry. 
    #     """
    #     # logging.getLogger('pf').setLevel(logging.DEBUG)

    #     if self._name:
    #         dStr = self._name+" #"+self.feType+"\n{\n"
    #     else:
    #         dStr = "#"+self.feType+"\n{\n"
    #     # for k, v in zip(self.keys(), self.values()):
    #     for k, v in zip(self.__dict__.keys(), self.__dict__.values()):
    #         k = k.rstrip('_') # remove possible "_" added in _checkReserved
    #         # logger.debug(f"dict entry: {k}: {v}")
    #         if k is None or re.match(UNNAMED_TAG+'_[0-9]+$', k):
    #             k=''
    #         if k not in self._CLASS_VARS:
    #             if isinstance(v, ofDict):
    #                 # logger.debug("Found ofDict.")
    #                 dStr2 = v.toString(ofRep=ofRep).split("\n")
    #                 for i in range(len(dStr2)):
    #                     dStr2[i] = TAB_STR+dStr2[i]+"\n"
    #                     dStr += dStr2[i]
    #             elif isinstance(v, ofList):
    #                 vList = v.toString(ofRep=ofRep).split('\n')
    #                 for v_ in vList:
    #                     dStr+= TAB_STR+v_+'\n'
    #                 # dStr = dStr.rstrip()
    #                 # dStr+=';'
    #                 dStr += '\n'
    #             elif hasattr(v, 'toString') and callable(getattr(v, 'toString')):
    #                 # dStr += printNameStr(TAB_STR+k)+v.toString()
    #                 dStr += TAB_STR+v.toString(ofRep=ofRep)
    #                 # logger.debug("Found 'toString()' method.")
    #             else:
    #                 # logger.debug("Could not find 'toString()' method.")
    #                 dStr += printNameStr(TAB_STR+k)+str(v)+';\n'

    #         # logger.debug(f"dict string: {dStr}")
    #     dStr+= "}\n\n"
    #     # if not ofRep:
    #     #     dStr = dStr.replace(';', '')
    #     return dStr

#- Create the list of OF_FUNCTION_OBJECTS
OF_FUNCTION_ENTRIES = {}
def createFunctionEntryRegistry(func):
    for dc in func.__subclasses__():
        OF_FUNCTION_ENTRIES.update({dc().feType: dc})
        createFunctionEntryRegistry(dc)
createFunctionEntryRegistry(_ofFunctionEntry)

@dataclass
class _ofVerbatimCode(_ofUnnamedTypeBase):
    _vcType: str = None
    _vBracketType: int = 2

    @property
    def vcType(self) -> str:
        return self._feType

    @vcType.setter
    def vcType(self, v: str) -> None:
        self._vcType = v


    @property
    def vBracketType(self) -> int:
        return self._vBracketType

    @vBracketType.setter
    def vBracketType(self, v: int) -> None:
        self._feType = 2
        userMsg("Bracket type cannot be changed for verbatim code.", "WARNING")

    def toString(self, ofRep=False) -> str:
        pStr = f'{printNameStr(self.vcType)}\n'
        pStr += printNameStr(BRACKET_CHARS['verbatim'][self.vBracketType][0])
        pStr += self.value
        pStr += printNameStr(TAB_STR+BRACKET_CHARS['verbatim'][self.vBracketType][1])


        if ofRep:
            pStr+=';'
        
        if self._comment is not None:
            pStr+= f" {str(self._comment)}"

        return pStr+'\n'


@dataclass
class ofCodeInclude(_ofVerbatimCode):
    include: List = None
    options: List = None

    @_ofVerbatimCode.vcType.getter
    def vcType(self):
        return 'codeInclude'

@dataclass
class ofCodeOptions(_ofVerbatimCode):
    include: List = None
    options: List = None

    @_ofVerbatimCode.vcType.getter
    def vcType(self):
        return 'codeOptions'

@dataclass
class ofCodeLibs(_ofVerbatimCode):
    include: List = None
    options: List = None

    @_ofVerbatimCode.vcType.getter
    def vcType(self):
        return 'codeLibs'

@dataclass
class ofCodeData(_ofVerbatimCode):
    include: List = None
    options: List = None

    @_ofVerbatimCode.vcType.getter
    def vcType(self):
        return 'codeData'

@dataclass
class oflocalCode(_ofVerbatimCode):
    include: List = None
    options: List = None

    @_ofVerbatimCode.vcType.getter
    def vcType(self):
        return 'localCode'

@dataclass
class ofCodeRead(_ofVerbatimCode):
    include: List = None
    options: List = None

    @_ofVerbatimCode.vcType.getter
    def vcType(self):
        return 'codeRead'

@dataclass 
class ofCodeExecute(_ofVerbatimCode):
    include: List = None
    options: List = None

    @_ofVerbatimCode.vcType.getter
    def vcType(self):
        return 'codeExecute'

@dataclass
class ofCodeWrite(_ofVerbatimCode):
    include: List = None
    options: List = None

    @_ofVerbatimCode.vcType.getter
    def vcType(self):
        return 'codeWrite'

@dataclass
class ofCodeEnd(_ofVerbatimCode):
    include: List = None
    options: List = None

    @_ofVerbatimCode.vcType.getter
    def vcType(self):
        return 'codeEnd'

@dataclass
class ofCodeContext(_ofVerbatimCode):
    include: List = None
    options: List = None

    @_ofVerbatimCode.vcType.getter
    def vcType(self):
        return 'codeContext'

#- Create the list of OF_VERBATIM_CODE_ENTRIES
OF_VERBATIM_CODE_ENTRIES = {}
def createVerbatimCodeRegistry(func):
    for dc in func.__subclasses__():
        OF_VERBATIM_CODE_ENTRIES.update({dc().vcType: dc})
        createVerbatimCodeRegistry(dc)
createVerbatimCodeRegistry(_ofVerbatimCode)

@dataclass
class _ofMonitorBase:
    _dataPath: Path
    _columns: List = None
    _index: int = field(init=False, default=0)
    _startTime : str = field(init=False, default=0)
    _name : str = None
    
    @property
    def data(self):
        return self._data

    @property
    def nSamples(self):
        return self._nSamples

    @property
    def dataPath(self):
        return self._dataPath

    # @dataPath.setter
    # def dataPath(self, path):
    def __post_init__(self):

        # logging.getLogger('pf').setLevel(logging.DEBUG)

        path = self._dataPath

        # logger.debug(f"datapath: {path}")

        if Path(path).is_file():
            self._dataPath = Path(path)
        else:
            userMsg(f"Invalid probe file specified:\n{path}", "ERROR")
        #- TODO:  Check that the field is actually in the object registry
        self._name = Path(path).parent.parent.name

        time_ = Path(path).parent.name

        try:
            int(time_)
            self.startTime = time_
        except ValueError:
            pass
        else:
            try:
                float(time_)
                self.startTime= time_
            except ValueError:
                userMsg(f"Invalid startTime found for monitor: " \
                +{self._dataPath}, "WARNING")

        if not hasattr(self, "_data") or self.data is None:
            with open(self.dataPath) as file:
                i = 0
                self._locations = []
                if self._columns is None:
                    #- Parse commented lines
                    while True:
                        line = file.readline()
                        if not line.startswith("#"):
                            break
                        prevLine = line
                    self._columns = prevLine.lstrip('#').split('\t')
                    self._columns = [v.strip() for v in self._columns]
                
                # logger.debug(f"columns: {self._columns}")
                self._readData(file)
        else:
            with open(self.dataPath) as file:
                self._readData(file)
    
    def _readData(self, file):
        """Read data after header"""
        parsedColumnLabels = False
        parsedLabels = [self._columns[0]]
        linei = 0
        data_ = None
        while True:
            linei+=1
            line = file.readline()
            if not line:
                break
            if line.startswith('#'):
                continue
    
            # logger.debug(f"parsedColumnLabels: {parsedColumnLabels}")            

            data_, parsedColumnLabels, columns = \
                self._parseLine(line, linei, data_, 
                    parsedColumnLabels, parsedLabels)

        self._storeData(data_, columns)
        # self._data = pd.DataFrame(data=data_[:,1:], index=data_[:,0],
        #                             columns=columns[1:])
        # self._data = self._data.convert_dtypes()
        # self._data.index.name = columns[0]                         
        # # logger.debug(f"probes: {columns}")
        # # self._data.columns = probes
        # self._nSamples = self._data.shape[0]

    def _parseLine(self, line, linei, data_, parsedColumnLabels=True, 
    parsedLabels=None):

        # logging.getLogger('pf').setLevel(logging.DEBUG)

        if parsedLabels is None:
            parsedLabels = self._columns

        # logger.debug(f"parsedLabels: {parsedLabels}")

        values = re.split(r'\s{2,}|\t', line.strip())
        values = [v.strip() for v in values]

        parsedValues = [float(values[0])]  #Time index
        ofValues = [float(values[0])]
        ofTypes = [float]

        for i, value in enumerate(values[1:]):
            ofType, ofValue = DictFileParser._parseValue(value)
                        
            ofValues.append(ofValue)
            ofTypes.append(ofType)
        
        # logger.debug(f"ofValues:\n{ofValues}")

        def countValues(list_, n=0):
            for value in list_:
                if isinstance(value, list):
                    n+= countValues(value)
                else:
                    n+= 1
            # logger.debug(f"returning {n}...")
            return n
        nValues = countValues(ofValues)
        # values_ = np.array(ofValues, dtype=object).flatten()
        # logger.debug(f"values_: {values_}")
        # nValues = values_.shape[0]

        # if found additional data values in middle of file, parse
        # header again
        if data_ is not None:
            # logger.debug(f"nValues > data_.shape[1]: {nValues} > {data_.shape[1]}")
            # logger.debug(f"parsedLabels: {parsedLabels}")
            if nValues > data_.shape[1]:
                parsedLabels = [self._columns[0]]
                parsedColumnLabels = False
                # logger.debug(f'parsedColumnLabels set to {parsedColumnLabels}')


        for i, (ofValue, ofType) in enumerate(zip(ofValues[1:], ofTypes[1:])):

            if isinstance(ofValue, list):
                for v in ofValue:
                    parsedValues.append(v)

                if not parsedColumnLabels:
                    # logger.debug(f"ofType: {ofType}")
                    if ofType == ofVector:
                        # logger.debug("Found ofVector...")
                        #- Found vector
                        parsedLabels.append(self._columns[i+1]+" X")
                        parsedLabels.append(self._columns[i+1]+" Y")
                        parsedLabels.append(self._columns[i+1]+" Z")
                    elif ofType == ofSymmTensor:
                        parsedLabels.append(self._columns[i+1]+" XX")
                        parsedLabels.append(self._columns[i+1]+" XY")
                        parsedLabels.append(self._columns[i+1]+" XZ")
                        parsedLabels.append(self._columns[i+1]+" YY")
                        parsedLabels.append(self._columns[i+1]+" YZ")
                        parsedLabels.append(self._columns[i+1]+" ZZ")
                    elif ofType == ofTensor:
                        parsedLabels.append(self._columns[i+1]+" XX")
                        parsedLabels.append(self._columns[i+1]+" XY")
                        parsedLabels.append(self._columns[i+1]+" XZ")
                        parsedLabels.append(self._columns[i+1]+" YX")
                        parsedLabels.append(self._columns[i+1]+" YY")
                        parsedLabels.append(self._columns[i+1]+" YZ")
                        parsedLabels.append(self._columns[i+1]+" ZX")
                        parsedLabels.append(self._columns[i+1]+" ZY")
                        parsedLabels.append(self._columns[i+1]+" ZZ")
                    elif ofType == ofSphericalTensor:
                        parsedLabels.append(self._columns[i+1])
                    else:
                        logger.warning("Could not locate appropriate ofType")
                        parsedLabels.append(self._columns[i+1])
                    #TODO: Check that the appropriate ofType was found
            else:
                parsedValues.append(ofValue)
                if not parsedColumnLabels:
                    parsedLabels.append(self._columns[i+1])
        
        # logger.debug("len(parsedValues) == len(parsedLabels): "
            # f"{len(parsedValues)} == {len(parsedLabels)}")
        if len(parsedValues) == len(parsedLabels):
            if not parsedColumnLabels:
                columns = parsedLabels
                parsedColumnLabels = True
                # logger.debug(f'parsedColumnLabels set to {parsedColumnLabels}')
            else:
                columns = parsedLabels
        elif len(parsedLabels) < len(parsedValues):
            columns = self._columns
        else:
            logger.warning(f"Skipping row {linei} with missing data.")
            return data_, parsedColumnLabels, parsedLabels# skip rows with missing values
            
        # If data_ exists make sure it is the correct shape (in the case of 
        # missing data for the first data points)
        if data_ is not None:
            if len(parsedValues) > data_.shape[1]:
                # found additional data values in middle of file
                #If data exists, pad existing values
                # logger.debug(f"data_ size: {data_.shape}")
                #TODO:  Doesnt handle case of missing value only in middle 
                # columns
                data_ = np.array([np.pad(v, (0, len(parsedValues)-
                                    data_.shape[1])) for v in data_])
                # logger.debug(f"data_ size after pad: {data_.shape}")


        if data_ is None:
            data_ = np.array([parsedValues])
        else:
            # logger.debug(f"data_ shape: {data_.shape}")
            # logger.debug(f"parsedValues shape: {np.array([parsedValues]).shape}")
            # logger.debug(f"parsedValues: {[parsedValues]}")
            data_ = np.append(data_, [parsedValues], axis=0)

        # parsedColumnLabels = True
        # logger.debug(f'parsedColumnLabels set to {parsedColumnLabels}')

        return data_, parsedColumnLabels, columns

    
    def update(self):
        """
        Append only the unread lines to the existing data
        """

        #TODO:  Accomodate list values for ofVector, ofTensor, etc.

        #TODO:  How do you check for new columns in case of vector or other list 
        # values?  Always read the entire file until this can be fixed.

        index_ = self.data.index.to_numpy(dtype=float).reshape( (-1,1) )

        data_ = np.hstack((index_, self.data.to_numpy()))

        i = self.nSamples - 1
        with open(self.dataPath) as file:
            parsedColumnLabels = True
            columns = [self.data.index.name]
            for v in self.data.columns:
                columns.append(v)
            # logger.debug(f"columns: {columns}")
            lines = file.readlines()
            while True:
                if i >= len(lines):
                    break # Found end of file
                line = lines[i]
                if not line:
                    break
                if line.startswith('#'):
                    continue
                data_, parsedColumnLabels, columns = \
                        self._parseLine(line, i, data_, parsedColumnLabels, 
                        columns)
                # lineDf = pd.DataFrame(data_, index=i, 
                #     columns=columns)
                i+=1
            # self._data = pd.DataFrame(data=data_[:,1:], index=data_[:,0],
            #                         columns=columns[1:])
            # self._data.convert_dtypes()
            # self._data.index.name = columns[0]                         
            # self._nSamples = self._data.shape[0]
        self._storeData(data_, columns)

    def _storeData(self, data_, columns):
        self._data = pd.DataFrame(data=data_[:,1:], index=data_[:,0],
                                    columns=columns[1:])
        # self._data = self._data.convert_dtypes()
        self._data.index.name = columns[0]                         
        self._nSamples = self._data.shape[0]

class MonitorParser:
    def __init__(self, path=Path.cwd()):
        if not isinstance(path, Path):
            self.path = Path(path)
        else:
            self.path = path

    def makeOFMonitor(self):

        # logging.getLogger('pf').setLevel(logging.DEBUG)

        attrList = []

        # read in the header comments to store as ofMonitor attributes
        with open(self.path) as f:
            for line in f:
                if line.startswith('#') == False:
                    break
                if ':' in line:
                    lineList = line.lstrip('#').split(':')
                    lineList = [v.strip() for v in lineList]
                    key = _parseNameTag(lineList[0].strip())
                    value = ':'.join(lineList[1:])
                    # logger.debug(f"monitor file key: {key}")
                    #TODO:  What types should be acceptable here?
                    type_ = str
                    try:
                        int(value)
                        type_ = int
                    except ValueError:
                        pass
                    else:
                        try:
                            float(value)
                            type_ = float
                        except ValueError:
                            pass

                    attrList.append((key, type_, field(default=value)))
                else: # store values as column labels
                    header = line.lstrip('#').split('\t')
                    header = [v.strip() for v in header]
                    
                
        dc_ = make_dataclass('ofMonitor', attrList, 
                    bases=(_ofMonitorBase, ))(_dataPath=self.path, 
                                        _columns=header)
                
        return dc_

            


        # Pass headers to _ofMonitorBase and create a new ofMonitor using 
        # 'make_dataclass'

#TODO:  Create an ofMonitorCollection class that stores multiple start time 
# values for a single probe.  Use MonitorParser to create a list of 
# ofMonitorCollections, but do not store in an ofCase, because this would be too 
# cumbersome for saving data. 

class MonitorCollectionParser:
    def __init__(self, path=Path.cwd()):
        if not isinstance(path, Path):
            self.path = Path(path)
        else:
            self.path = path

    def parse(self):
        """
        Parse the top level folder containing all monitors (i.e. 
        'postProcessing'), and return a list of ofMonitor objects.
        """
        for obj in self.path.iterdir():
            if obj.is_dir() and obj.name.startswith('.') == False:
                pass

    def makeOFMonitor(self):
        attrList = []
        for obj in self.path.iterdir():
            if obj.is_dir() and obj.name.startswith('.') == False:
                pass


@dataclass
class ofProbe(_ofMonitorBase):
    # def __init__(self, dataPath, columns=None, name=None):
    #     super(ofProbe, self).__init__(_dataPath=dataPath, _columns=columns, 
    #                                     _name=name)
    # dataPath: Path
    # _index: int = field(init=False, default=0)

    
    # @property
    # def data(self):
    #     return self._data

    @property
    def field(self):
        return self._field

    @property
    def locations(self):
        """Coordinate locations of the sampled data"""
        return self._locations

    # @property
    # def nSamples(self):
    #     return self._nSamples

    # @property
    # def dataPath(self):
    #     return self._dataPath

    # @dataPath.setter
    # def dataPath(self, path):
    #TODO:  Call baseclass __post_init__ function instead of copying code
    def __post_init__(self): 

        # logging.getLogger('pf').setLevel(logging.DEBUG)

        path = self._dataPath

        # logger.debug(f"datapath: {path}")

        if Path(path).is_file():
            self._dataPath = Path(path)
        else:
            userMsg(f"Invalid probe file specified:\n{path}", "ERROR")
        #- TODO:  Check that the field is actually in the object registry
        self._field = Path(path).name

        if not hasattr(self, "_data") or self.data is None:
            #- Parse commented lines
            with open(self.dataPath) as file:
                i = 0
                self._locations = []
                self._columns = ['Time']
                while True:
                    line = file.readline()
                    # logger.debug(f"line: {line}")
                    if not line.startswith("# Probe"):
                        break
                    self._columns.append(f"Probe {i}")
                    self._locations.append(
                        ofVector([float(v) for v in 
                            line.split('(')[1].split(')')[0].split()]))
                    i+=1
                # logger.debug(f"columns: {self._columns}")
                #- read data after header
                self._readData(file)

        else:
            #self._appendData()
            with open(self.dataPath) as file:
                self._readData(file)

        #         parsedColumnLabels = False
        #         parsedLabels = [self._columns[0]]
        #         while True:
        #             line = file.readline()
        #             if not line:
        #                 break
        #             if line.startswith('#'):
        #                 continue
        #             values = re.split(r'\s{2,}|\t', line.strip())
        #             values = [v.strip() for v in values]
        #             #TODO:  How should non-numeric values be handled?
        #             # if len(values) < len(self._columns):  # Skip line with missing data
        #             #     logger.debug(f"len(values), len(self._columns): "
        #             #         f"{len(values)}, {len(self._columns)}")
        #             #     logger.debug("Skipping line...") 
        #             #     continue

        #             parsedValues = [float(values[0])]  #Time index
        #             for i, value in enumerate(values[1:]):
        #                 ofType, ofValue = DictFileParser._parseValue(value)
        #                 logger.debug(f"ofType, ofValue: {ofType}, {ofValue}")
        #                 if isinstance(ofValue, list):
        #                     for v in ofValue:
        #                         parsedValues.append(v)
        #                         #parsedLabels.append(self._columns[i+1])
        #                     if not parsedColumnLabels:
        #                         # if isinstance(ofType, ofVector):
        #                         if ofType == ofVector:
        #                             #- Found vector
        #                             parsedLabels.append(f"{self._columns[i+1]} X")
        #                             parsedLabels.append(f"{self._columns[i+1]} Y")
        #                             parsedLabels.append(f"{self._columns[i+1]} Z")
        #                         elif ofType == ofSymmTensor:
        #                             parsedLabels.append(f"{self._columns[i+1]} XX")
        #                             parsedLabels.append(f"{self._columns[i+1]} XY")
        #                             parsedLabels.append(f"{self._columns[i+1]} XZ")
        #                             parsedLabels.append(f"{self._columns[i+1]} YY")
        #                             parsedLabels.append(f"{self._columns[i+1]} YZ")
        #                             parsedLabels.append(f"{self._columns[i+1]} ZZ")
        #                         elif ofType == ofTensor:
        #                             parsedLabels.append(f"{self._columns[i+1]} XX")
        #                             parsedLabels.append(f"{self._columns[i+1]} XY")
        #                             parsedLabels.append(f"{self._columns[i+1]} XZ")
        #                             parsedLabels.append(f"{self._columns[i+1]} YZ")
        #                             parsedLabels.append(f"{self._columns[i+1]} YY")
        #                             parsedLabels.append(f"{self._columns[i+1]} YZ")
        #                             parsedLabels.append(f"{self._columns[i+1]} ZX")
        #                             parsedLabels.append(f"{self._columns[i+1]} ZY")
        #                             parsedLabels.append(f"{self._columns[i+1]} ZZ")
        #                         else:
        #                             parsedLabels.append(self._columns[i+1])
        #                         #TODO: Check that the appropriate ofType was found
        #                 else:
        #                     parsedValues.append(ofValue)
        #                     parsedLabels.append(self._columns[i+1])
        #             logger.debug("len(parsedValues) == len(parsedLabels): "
        #                 f"{len(parsedValues)} == {len(parsedLabels)}")
        #             if len(parsedValues) == len(parsedLabels):
        #                 logger.debug(f"parsedLabels: {parsedLabels}")
        #                 self._columns = parsedLabels
        #             else:
        #                 raise Exception("Could not parse log file data type.")

        #             # logger.info(f"Parsed values: {parsedValues}")

        #             try:
        #                 data_
        #             except NameError:
        #                 data_ = np.array([parsedValues])
        #             else:
        #                 data_ = np.append(data_, [parsedValues], axis=0)
        #             # data_ = np.reshape(data_, (len(data_), -1)) # Convert to 2D array

        #             parsedColumnLabels = True

        #     # converters = {}
        #     # for i in range(1,len(columns)):
        #     #     converters.update({i: _parseProbeValues})
        #     # self._data = pd.read_csv(path, sep="\s+\s+",comment='#', 
        #     #     engine='python', converters=converters)   
        #     # data_ = _parseProbeValues(path)

        #     logger.debug(f"data shape: {data_.shape}")

        #     self._data = pd.DataFrame(data=data_[:,1:], index=data_[:,0],
        #                              columns=self._columns[1:])
        #     logger.debug(f"probes: {self._columns}")
        #     # self._data.columns = probes
        #     self._nSamples = self._data.shape[0]
        # else: #- Append only the unread lines to the existing data
    
        #     i = self.nSamples - 1
        #     with open(self.dataPath) as file:
        #         while True:
        #             line = file.readline(i)
        #             if line == "": # Found end of file
        #                 break
        #             lineDf = pd.DataFrame(line.split(), index=i, 
        #                 header=self._data.columns)
        #             self._data = pd.concat(self._data, lineDf)

    # TODO:  Dataclasses cannot be iterable??
    # def __iter__(self):
    #     return self
    
    # def __next__(self):
    #     if self._index < len(self.locations):
    #         time = self.data.iloc[:,0]
    #         return (time, self.data.iloc[:,i+1]), self.data.columns[i+1], self.locations[i]
    #     else:
    #         raise StopIteration

    # def monitor(values=['U', 'p'], time=None, supplement=None, 
    #     workingDir=Path.cwd(), ylabel = None, title=None,
    #     legendName = None):

    #     if title is None:
    #         title = Path(workingDir).name

    #     pauseTime = 0.2

    #     def updatePlot(x, y, plotData, identifier='', pauseTime=0.2):
    #         if plotData==[]:
    #             plt.ion()
    #             fig = plt.figure(figsize=(6,3))
    #             ax = fig.add_subplot(1, 1, 1)
    #             plotData, = ax.plot(x, y, label = legendName)
    #             plt.ylabel(ylabel)
    #             plt.xlabel("Time")
    #             plt.title(title)
    #             plt.legend()
    #             plt.show()
            
    #         plotData.set_data(x, y)
    #         plt.xlim(np.min(x), np.max(x))

    #         if (np.min(y) <= plotData.axes.get_ylim()[0]
    #         or np.max(y) >= plotData.axes.get_ylim()[1]):
    #             ystd = np.std(y)
    #             plt.ylim([np.min(y)-ystd, np.max(y)+ystd])

    #         # plt.pause(pause_time)

    #         return plotData

    #     plotData = [[] for value in values for probe in value]

    #     while True:
    #         for probe in probes:

    #             for (x, y), name, loc in probe:
    #                 legendName = f"{name}: ({loc[0]}, {loc[1]}, {loc[2]})"
    #                 plotData = updatePlot(x, y, plotData, ylabel=probe.field,
    #                 legend= legendName)

    #         plt.pause(pauseTime)


@dataclass
class ofStudy:
    templatePath : Path
    parameterNames : list   # Note: this argument must be parsed before 'samples' 
                            # for DataFrame conversion
    samples : np.ndarray
    updateFunction : Callable
    path: Path = Path.cwd()
    runCommand : str = './Allrun'

    def __post_init__(self):
        self.templateCase = CaseParser(self.templatePath).makeOFCase()
        logger.info(f"Using template case: {self.templateCase._path}")
        #self.templateCase._name = self.templateCase._name.rstrip('.template')
        #self.samples = pd.DataFrame(self._samples, columns=self.parameterNames)
        self.nSamples = len(self.samples)

    @property
    def samples(self):
        return self._samples
    
    @samples.setter
    def samples(self, s):
        if isinstance(s, pd.DataFrame):
            self._samples = s
            return
        elif not isinstance(s, np.ndarray):
            try:
                s = np.asarray(s)
            except ValueError:
                userMsg("'samples' entry must be numpy array_like.  "\
                    "Found {s}.", "ERROR")
        if any([len(self.parameterNames) != len(s_) for s_ in s]):
            userMsg("'parameterNames' argument must have length equal to"
                f" the length of columns in 'samples'.  "
                f"{len(self.parameterNames)} != {len(s[0])}", "ERROR")
        if s.ndim != 2:
            dimText = 'dimension' if s.ndim == 1 else 'dimensions'
            userMsg("'samples' entry must be a 2D array_like.  "\
                    f"Found {s.ndim} {dimText}.", "ERROR")
        self._samples = pd.DataFrame(s, columns = self.parameterNames)
            
    @property
    def parameterNames(self):
        return self._parameterNames

    @parameterNames.setter
    def parameterNames(self, n):
        if n is None:
            pass
        elif not isinstance(n, list):
            userMsg("'parameterNames' argument must be list type."\
                f"  Found {type(n)}", "ERROR")
        self._parameterNames = n

    @property
    def updateFunction(self):
        return self._updateFunction

    @updateFunction.setter
    def updateFunction(self, f):
        if not callable(f):
            userMsg("'updateFunction' argument must be callable.", "ERROR")
        self._updateFunction = f

    def run(self, runSequence=None, ignoreIndices = [], dryRun = False, 
        sort=None, ascending=False, restart=False):
        """
        Run an OpenFOAM study.

        Parameters:
            runSequence [list(int)]:  List of indices specifying the order in
                which to run the samples.  If specified, the `sort`, 
                `ignoreIndices`, and `ascending` arguments are ignored.  Samples
                not included in the list are ignored.
            dryRun [bool]: If True, write case directories, but does not run the
                simulations.
            sort [list(int or str)]:  Index or column names on which to sort 
                the run order.
            ascending [list(bool)]: If `True`, sorting of column is in
                ascending order [default], else sorts in descending order.  
                List length must equal length of `sort` argument.
            restart [bool]: If `True`, simulations for which directories already 
                exist will be restarted from the lastest time.
        """
        #- Save the sample points to file
        self.samples.to_csv('studySamplePoints.txt', sep='\t')

        print(f"samples keys: {self.samples.columns}")

        if runSequence is not None:
            samples_ = self.samples.iloc[runSequence]
        #TODO:  The call to `sort_values` raises a KeyError
        elif sort is not None:
            sortNames = [self.samples.columns[s] if isinstance(s, int) \
                else str(s) for s in sort]
            samples_ = self.samples.sort_values(by=sortNames, axis=0, 
                                                ascending=ascending)
        else:
            samples_ = self.samples

        nPad = len(str(self.nSamples))

        for idx, row in samples_.iterrows():
            if idx not in ignoreIndices:
                print(f"Running sample {idx}")
                name = ".".join(self.templateCase.name().split('.')[:-1])+\
                    '.'+str(idx).zfill(nPad)
                newPath = Path(self.templateCase._path.parent) / name
                    
                #- Copy the template case path to ensure all files are copied:
                if (restart and newPath.is_dir()):
                    pass
                else:
                    shutil.copytree(self.templateCase._path, newPath)
       
                case_ = copy.deepcopy(self.templateCase)
         
                case_.setName(name)
                case_ = self.updateFunction(case_, row.values.flatten().tolist())
                if restart:
                    case_.system.controlDict.startFrom = 'latestTime'
                    runLogPath = case_._path / \
                        ('log.' + case_.system.controlDict.application.value)
                    if runLogPath.is_file():
                        i = 0
                        while Path(str(runLogPath) + f'.{i}').is_file():
                            i+= 1
                        shutil.move(runLogPath, str(runLogPath)+f'.{i}')            

                print(f"Case path: {case_._path}")

                case_.write()
                if not dryRun:
                    case_.allRun(cmd=self.runCommand)      

    def diff(self):
        """
        Print the difference between cases for all operating scenarios 
        of the study.
        """      
        #TODO:  Implement this...
        pass

class DictFileParser:
    def __init__(self, filepath):
        self.filepath = filepath
        with open(filepath, 'r') as f:
            self.lines = f.readlines()
        self.status = None
        # logger.debug(f"Setting dictFile name to {Path(filepath).name}...")
        self.dictFile = ofDictFile(_name=Path(filepath).name) 
                            #_location=Path(filepath).parent)
        self.i=0
        self.extraLine = []
        self.comment = []
        self.nComments = 0
        self.nFeTypes = {t: 0 for t in OF_FUNCTION_ENTRIES.keys()}
        self.needSemicolon = True


    def _addExtraLine(self, line):
        # if self.extraLine is not None:
        #     logger.error("Unhandled sequence.  Found multiple extra lines")
        #     raise Exception
        # else:
        if line != "":
            # logger.debug(f"Adding extra text:  {line}")
            self.extraLine.append(line)
    

    def _getLinesList(self, line):
        """
        Convert a line string to the appropriate lines list without comments and
        extra whitespace

        Parameters:
            lines [list(str)]:  List of lines of the dictionary file as text
                obtained from the `open()` command.
            i [int]: index of the line currently being parsed

        Returns:
            linesList [list(str)]:  List of individuals entries (space delimited)
                for the current C++ statement.
            i [int]: index of the current line after parsing the statement 

        """
        return line.strip().split('//')[0].split()

    def _getComment(self):
        """
        Get the comment for the currently parsed line, and remove comment from
        `self.comments` list.
        """

        if len(self.comment) > 0:
            comment_ = self.comment.pop(-1)
        else:
            comment_ = None
        
        return comment_

    def readDictFile(self):

        status = 'start'
        ofType = None
        prevLine = None
        lineStatus = 'read'
        level = 0

        self.i = self._findEndOfHeader()

        # logger.debug(f"End of header at line {self.i+1}.")

        self.dictFile._header = ofHeader(self.lines[:self.i])

        # logger.debug(f"ofDictFile: {self.dictFile}")

        while self.lines[self.i].strip() == "":
            self.i+=1

        #- Manually parse the FoamFile (assumes FoamFile is located immediately
        #   after header):
        #TODO:  Implement the FoamFile class?  Currently doesnt store dictionary
        #       values properly.
        if self.lines[self.i].strip() == 'FoamFile':
            self.i+=1
            self.dictFile._foamFile = self._parseListOrDict('FoamFile')

        attempts = 0
        while True:
            attempts += 1
            if attempts > 5000:
                logger.error("Error reading dictionary file.  Maximum "\
                    "number of lines exceeded:\n"+str(self.filepath))
                sys.exit()
            if self.i >= len(self.lines):
                break
            
            # logger.debug(f"Parsing line {self.i+1} of file {self.filepath}")
            
            value = self._parseLine()

            # logger.debug(f"** FINAL VALUE: {value}")

            # logger.debug(f"dictFile name = {self.dictFile._name} ")

            if value is not None:
                logger.debug(f"adding value: {value}")
            #     self.entryList.append(value)
                if (isinstance(value, _ofTypeBase) 
                    and not isinstance(value, ofComment)
                    and not isinstance(value, _ofFunctionEntry)):
                    #- rename key if already in dict:
                    if value._name in self.dictFile.keys():
                        # logger.debug("Renaming duplicate key.")
                        key = value._name+'_1'
                    else:
                        key = value._name
                    if hasattr(value, '_name'):
                        # logger.debug(f"_parseLine: setting {key}: {value}")
                        self.dictFile.update({key: value})
                    elif hasattr(value, 'name'):
                        self.dictFile.update({key: value})
                elif isinstance(value, ofComment):
                    name_ = COMMENT_TAG+str(self.nComments)
                    self.dictFile.update({name_: value})
                    self.nComments += 1
                elif isinstance(value, _ofFunctionEntry):
                    name_ = value.feType+str(self.nFeTypes[value.feType])
                    self.dictFile.update({name_: value})
                    self.nFeTypes[value.feType]+= 1
                else:
                    logger.error(f"Invalid value type: {type(value)}.")
                    sys.exit()

            # [status, lineStatus] = _readDictEntry(status, ofType, lines, i)

        # return ofDictFile(self.entryList
        #                 #location=Path(file).parent, 
        #                 #filename=Path(file).name
        #                 )
        
        # logger.debug(f"dictFile name = {self.dictFile._name} ")

        return self.dictFile

    def _parseLine(self):
    
        logger.debug(f"Parsing line {self.i+1}.")
        # logger.debug(f"\tself.extraLine: {self.extraLine}")

        # logger.debug(f"\tline[{self.i+1}]: {self.lines[self.i].rstrip()}")

        parsingExtraLine = False

        if len(self.extraLine) == 0:
            #- Ignore inline comments and split line into list.  Comments are
            #   parsed using self.lines[self.i] in _parseComments() below.
            #lineList = self.lines[self.i].strip().split('//')[0].split()
            lineList = self._getLinesList(self.lines[self.i])
        else:
            #lineList = self.extraLine[0].strip().split('//')[0].split()
            lineList = self._getLinesList(self.extraLine[0])
            parsingExtraLine = True

        logger.debug(f"filepath: {self.filepath}; lineList: {lineList}")

        try:
            parsedComment = self._parseComments()
            if parsedComment is not None:
                return parsedComment
            elif len(lineList) == 0:
                # Line is blank
                return None
            elif lineList[0][0] == '#':
                if len(lineList) == 2 and 'include' in lineList[0]:
                    value = self._parseIncludes(lineList[0], lineList[1])
                    logger.debug(f"includeValue: {value}")
                else:
                    value = self._parseVerbatimEntry(lineList=lineList)
                return value
            # elif len(lineList) >= 2:
            #     if lineList[1][0] == '#':
            #         value = self._parseVerbatimEntry(lineList=lineList[1:],name=lineList[0])
            #         return value
            elif len(lineList) == 1:
                if lineList[0].strip() == '};' or lineList[0] == ');':
                    #- ending list or dict
                    return None
                match = re.match(r'\$(.*);', lineList[0].strip())
                if match is not None:
                    # Found variable reference
                    name_ = match.group(1)
                    # logger.debug(f"Found variable: {name_}.")
                    return ofVar(name_)
                if lineList[0].strip()[-1] == ';':
                    #- found non-keyword value
                    return ofWord(lineList[0].strip().rstrip(';'))
                if lineList[0] == '}':
                    return None # Found beggining or end of dictionary
                #TODO:  Implement in way that ofVars can be captured:
                # if ((all(c in lineList[0].strip() for c in ['(', ')'])
                # or all(c in lineList[0].strip() for c in ['{', '}']))
                # and not any([lineList[0].startswith(c) for c in ['"', "'"]])):
                #     #found list on sinlge line. e.g '0()'
                #     line = lineList[0].strip()
                #     listOrDictName = line.split('(')[0]
                #     strippedLine = '('+'('.join(line.split('(')[1:])
                #     value = self._parseListOrDict(listOrDictName, 
                #                                   line=strippedLine)
                #     logger.debug(f"_parseLine list or dict:\n{value}")
                #     return value
                listOrDictName = self.lines[self.i].lstrip().rstrip()
                # logger.debug(f"listOrDictName: {listOrDictName}")                
                if any([listOrDictName is char for char in ['(', '{']]):
                    # logger.debug("Parsing unnamed list or dictionary.")
                    value = self._parseListOrDict(None)

                    # logger.debug(f"_parseLine list or dict:\n{value}")

                    return value
                
                else:
                    self.i += 1
                    value = self._parseListOrDict(listOrDictName)

                    # logger.debug(f"_parseLine list or dict:\n{value}")

                    return value
            elif len(lineList) == 2:
                if lineList[1][0] == '#':
                    value = self._parseVerbatimEntry(lineList=lineList[1:],name=lineList[0])
                    return value
                else:
                    return self._parseLineLenTwo() 
            else:  # Multiple value entry
                if lineList[1][0] == '#':
                    value = self._parseVerbatimEntry(lineList=lineList[1:],name=lineList[0])
                    return value
                else:
                    return self._parseLineLenGreaterThanTwo()
        except Exception as e:
            raise e
        finally:
            if parsingExtraLine:
                self.extraLine =  self.extraLine[1:] #- remove the line that was 
                                                     #  just parsed.
            else:
                self.i += 1

    def _parseLineLenTwo(self):
        # logger.debug("Parsing line of length 2.")

        # lineList = self.lines[self.i].strip().split()
        lineList = self._getLinesList(self.lines[self.i])
        
        #logger.debug(f"lineList: {lineList}")
        
        # if lineList[0].startswith('#include'):
        #     # Found include statement 
        #     return self._parseIncludes(lineList[0], lineList[1].rstrip(';'))
        if lineList[1][-1] == ';':
            # Found single line entry
            return self._parseSingleLineEntry(lineList[0], 
                lineList[1].rstrip(';'))
        elif lineList[1] == 'table':
            # Found a table entry
            return self._parseTable(lineList[0])
        elif lineList[1] == '(' or lineList[1] == '{':
            # Found list or dict
            return self._parseListOrDict(lineList[0], line=lineList[1])
        else:
            logger.error(f"Cannot handle single line entry '{lineList}' on line "\
                f"{self.i+1} of {self.filepath}.")
            sys.exit()


    def _parseSingleLineEntry(self, key, value):
        """
        Extract the value as the approriate ofTypes

        Search order:
            - ofFloat, ofInt, ofBool, ofStr
        """

        # logger.debug("Parsing a single line entry")

        # logger.debug(f"key: {key}, value: {value}")

        type_, value_ = self._parseValue(value)

        # logger.debug(f"{type_} signature: {signature(type_)}")

        if hasattr(type_, 'name'):
            return type_(key, value_, _comment=self._getComment())
        elif hasattr(type_, '_name'):
            return type_(key, value_, _comment=self._getComment())
        else:
            userMsg(f"Could not set name for type {type_}.  Returning "\
                "value only!", "WARNING")
            return type_(value_, _comment=self._getComment())

    def _parseListOrDict(self, name, line : str = None):
        """
        Parse a list or dictionary with name `name`, starting from the opening 
        parenthesis `(` in the case of a list or opening bracket '{' in the case of 
        a dict.  Also can return a ofFunctionEntry if name is an feType and the opening 
        bracket is a function entry bracket type.

        Parameters:
            name [str or None]:  The name of the list or dict;  None if an unnamed 
            value.

            line (str):  If specified, parse this line rather than 
            self.lines[self.i].

        Returns:
            value [ofList or ofDict]:  The value of the list or dict items to 
            be added.  

        """

        #linesList = self._getLinesList(self.lines[self.i])

        logger.debug(f"Parsing list {name}.")

        if name is not None:
            name = name.strip()

        if line is not None:
            # lineList = line.strip().split()
            lineList = self._getLinesList(line)
        else:
            # lineList = self.lines[self.i].strip().split()
            lineList = self._getLinesList(self.lines[self.i])

        logger.debug(f"name: {name}")
        logger.debug(f"lineList: {lineList}")

        if (name in list(OF_FUNCTION_ENTRIES.keys())+list(OF_VERBATIM_CODE_ENTRIES.keys()) 
            and lineList[0] in [c[0] for c in BRACKET_CHARS['verbatim']]):
            lineList.insert(0,name)
            return self._parseVerbatimEntry(lineList=lineList)

        # logger.debug(f"parseListOrDict name: {name}")

        # logger.debug(f"line[{self.i+1}]: {line or self.lines[self.i]}")
        # logger.debug(f"lineList[{self.i+1}]: {lineList}")

        openingChar = None
        listLen = None
        if (len(lineList) > 0 
        and any([lineList[0].startswith(c) for c in ['(', '{']])):
            openingChar = lineList[0][0]
        elif (lineList[0] == name and
            any([lineList[1].startswith(c) for c in ['(', '{']])):
            openingChar = lineList[1][0]
        
        #Capture lists with specified length.  e.g. '2((0 0) (500 1))'
        try:
            int(lineList[0])
            openingChar = '('
            listLen = int(lineList[0])
            self.i+=1
            lineList = self._getLinesList(self.lines[self.i])
        except (TypeError, ValueError):
            pass

        # logger.debug(f'openingChar: {openingChar}')

        if openingChar is None:
            userMsg(f"Invalid syntax on line {self.i+1} of dictionary "
            f"file '{self.filepath}'.", level='ERROR')
                 
        # logger.debug(f"Opening char: {openingChar}")

        if openingChar == '(':
            self.needSemicolon = False
            list_ = self._parseList(name, split=True)
            self.needSemicolon = True
            return list_
            # if len(lineList) > 1:
            #     #list is on a single line
            #     if lineList[-1][-1] != ';':
            #         return self._parseList(name)
            #         #lineList = self._getLinesList(self.i)
            #     else:
            #         logger.ebug(f"lineList: {lineList}")
            #         #TODO: Handle lists of lists on a single line
            #         list_ = ofSplitList(name=name)
            #         for v in lineList[1:]:
            #             if v != "" and v is not None:
            #                 list_.value.append(self._parseValue(v))
            #         return list_
            # else:
            #     # - Parse the list recursively to capture list of lists
            #     return self._parseList(name, split=True)



            # if line is not None and ');' not in lineList[-1]:
            #     logger.error("Cannot parse line argument of an incomplete "\
            #         "list.")
            #     sys.exit()
            # # collect lines till end of list statement
            # startI = self.i
            # while ');' not in lineList[-1]:
            #     self.i+=1
            #     if self.i >= len(self.lines):
            #         userMsg("Could not find end of list starting at line "\
            #             f"{startI+1}.")
            #     lineList_ = self.lines[self.i].strip().split()
            #     for value in lineList_:
            #         lineList.append(value)
            # #parse a complete list statement
            # #TODO: Handle lists of lists on a single line
            # list_ = ofSplitList(name=name)
            # for v in lineList[1:]:
            #     if v != "" and v is not None:
            #         #TODO:  Should I pass the raw value or ofType here?
            #         #       Do I need to parse lists separately
            #         list_.value.append(v)
            # return list_

        elif openingChar == '{':
            #value = { name: None }
            # - Parse the dictionary recursively to capture dict of dicts
            # self.i += 1
            # if name == 'FoamFile':
            #     dict_ = self._parseFoamFile()
            # else:
            # logger.debug(f"Parsing {name} dictionary.")
            # return ofDict(self._parseDict(name))
            dict_ = self._parseDict(name)

            # logger.debug(f"dict_: {dict_}")

            return dict_
        else:
            #- Assume value is a single value list or dict entry:
            return ofWord(name)
            # userMsg(f"Invalid syntax on line {self.i+1} of dictionary "
            # f"file '{self.filepath}'.", level='ERROR')
            # logger.error(f"Invalid syntax on line {self.i+1} of dictionary "
            # f"file '{self.filepath}'.")
            # sys.exit()

        #self.i += 1

    def _parseList(self, name, split=False):
        """
        Parse a list storing values as ofList.  
        
        Only parse recursively if dictionaries are found within list, otherwise
        keywords are not included
        """
        
        i_start = self.i
        # - Find the end of dictionary        
        i_end = self._findDictOrListEndLine('list')

        # logger.debug(f"i_end: {i_end}")

        # logger.debug(f"name: {name}")


        if split:
            list_ = ofSplitList(name=name)
        else:
            list_ = ofList(name=name)

        #- check to see if list contains dictionaries:
        contentStr = ' '.join(self.lines[self.i:i_end+1])
        # logger.debug(f"content string:\n{contentStr}")

        if '{' in contentStr and '}' in contentStr:
            #- found dictionary, parse recursively
            # logger.debug("Found dictionaries within list, parsing recursively...")
            
            #- Skip current line (with '('), and store any additional text as 
            #  extra line.
            extraLine = ''.join(self.lines[self.i].strip().split('(')[1:])
            if extraLine != '':
                # logger.debug(f"extraLine: {extraLine}")
                self._addExtraLine(extraLine)

            self.i+=1

            while self.i < i_end:
                value_ = self._parseLine()
                if value_ is not None:
                    list_.value.append(value_)

            # logger.debug(f"list_:\n{list_}")

            return list_

        # logger.debug("Parsing list without dictionary values...")

        entryList = []

        while self.i <= i_end:
            line = self.lines[self.i]
            if self.i == i_start:
                #remove potential keyword:
                line = line.strip().lstrip(name).strip()
                #- Ignore first '('
                #- If line contains key value, ignore as already saved as name.
                # e.g.  fields      ( U p );
                if line.strip() != "" and line.strip()[0] != '(':
                    if '(' in line:
                        #- Remove everything before '(' Assumed to be key 
                        line = '('+'('.join(line.split('(')[1:])
                    else:
                        userMsg("Invalid syntax.  List value does not "\
                            "begin with '('.", 'ERROR')
                #- Ignore first '('
                line=line.strip()[1:]
            if ';' in line:
                if self.i != i_end:
                    logger.error("Unhandled pattern found!")
                    sys.exit()
                #- store extra characters as a new line to be parsed later
                self._addExtraLine(''.join(line.split(';')[1:]))
                #- ignore last );
                if line.endswith(');'):
                    line = line[:-2] 

            # logger.debug(f"line[{self.i+1}]: {line}")

            # #- Parse comment
            # comment = self._parseComments()
            # if comment is not None:
            #     entryList.append(comment)
            #     self.i += 1
            #     continue

            # if line.strip().strip('(') == '':
            #     # Do not parse unhandled case of only opening chars '('
            #     i_end2 = self._findDictOrListEndLine('list')
            #     if i_end2 > i_end:
            #         logger.error(f"Unhandled syntax found on line {self.i-1} "\
            #             f"of file {self.filepath}.")
            #     while self.i <= i_end2:
            #         line+= 


            #- Try to parse whole line as single value:
            entry_ = self._parseListValues(line)
            # entry_._comment = comment

            for v in entry_:
                entryList.append(v)

            # #- Parse each value
            # lineList = self._getLinesList(line)
            # for i, entry in enumerate(lineList):
            #     #- Store as ofType
            #     type_, value_ = self._parseValue(entry)
            #     entry_ = type_(value=value_)
            #     if i == len(lineList)-1:
            #         entry_._comment = comment
            #     entryList.append(entry_)

            # logger.debug(f"self.i: {self.i}")
            self.i += 1

        self.i -= 1 #Reset line after while loop; while increment in _parseLine 

        # strValue = " ".join(entryList)

        # logger.debug(f"*********************strValue: {strValue}")

        # if strValue.strip() != "":
        #     #TODO:  Can this be simplified to just call _parseLine()
        #     value_ = self._parseListValues(strValue)
        #     if value_ is None:
        #         list_.value.append(self._parseLine())
        #     else:
        #         # list_.value.append(value_)
        #         list_.value = value_
        # for entry in entryList:
        #     if entry != "":
        #         list_.value = self._parseListValues(" ".join(entry))

        list_.value = entryList

        list_._comment = self._getComment()

        return list_

    def _parseListValues(self, values : str):
        """
        convert a string value from file into the appropriate ofType.
        """
        # logger.debug(f"list values: {values}")
        # logger.debug(f"len list values: {len(values)}")

        #- Get expressions between parenthesis as list:
        #valuesList = [p.split(')')[0] for p in values.split('(') if ')' in p]

        #logger.debug(f"valuesList: {valuesList}")

        # #- remove any leading or trailing parentheses if they cover whole line
        # if values[0] == '(' and values[-1] == ')':
        #     if len(values) > 2
        #     nopen = 0
        #     nclosed = 0
        #     for char in values[1:-1]:
        #         if char = '('
        #     else:
        #         return None


        foundComment = False

        #- Parse comment 
        comment = self._parseComments(values)
        if comment is not None:
            return [comment]

        if '//' in values:
            foundComment = True
            values = values.split('//')[0]

        listValues = []

        #- Divide value string into entities with list of lists if parentheses
        i=0
        delimiters = BRACKET_CHARS['list']
        delimiters.append(" ")

        while i < len(values):
            if values[i] == '(':
                #- add value as list
                #- find end of list:
                # logger.debug(f"line list searchStr: {values[i:]}")
                j=self._findDictOrListEndIndex(values[i:])
                if j is None:
                    # logger.error("Could not find end of list on a single "\
                    #     "line")
                    # sys.exit()
                    # return None
                    
                    #- Add an extra line to 'values':

                    self.i+=1
                    return self._parseListValues(values+" "+self.lines[self.i])
                subStr = values[i+1:i+j]
                # logger.debug(f"subStr: {subStr}")
                # if j != len(values)-1:
                #     #- Add extra text to self.extraLine
                #     self.extraLine.append(values[j:])
                if not any([char in subStr for char in BRACKET_CHARS['list']]):
                    #if not list of lists, append values
                    for value in subStr.split():
                        listValues.append(value)
                else:
                    #TODO: Store as ofList or list. An ofLIst is required here to 
                    # store line comments
                    listValue_ = ofList(value=self._parseListValues(subStr))
                    # listValues.append(self._parseListValues(subStr))
                    if foundComment:
                        listValue_._comment = self._getComment()
                    listValues.append(listValue_)

                i=j+i
                # logger.debug(f"i: {i}")
                # logger.debug(f"j: {j}")
            else:
                value_ = ''
                while not any([values[i] == char for char in delimiters]):
                    value_+=values[i]
                    if i == len(values)-1:
                        break
                    # logger.debug(f"value_: {value_}")
                    i+=1
                if value_ != '':
                    type_, v = self._parseValue(value_)
                    if type_ is not None:
                        listValues.append(type_(value=v)) # TODO: save as ofType?
                    # listValues.append(v)
            # logger.debug("list values during parsing: "\
                # f"{listValues}")
            i+=1
            # logger.debug(f"i: {i}")

        # logger.debug(f"listValues: {listValues}")

        # #- add comment to last list value
        # if len(listValues) != 0:
        #     commentedValue = listValues[-1]
        #     commentedValue._comment = self._getComment()                    
        #     listValues[-1] = commentedValue

        return listValues


    def _findDictOrListEndIndex(self, string, type='list'):
        """
        Find the index that terminates the list or dictionary that begins at the
        start of string.  Any text before the first opening bracket is ignored.

        Parameters:
            string [str]:  The string to be parsed.
            type [str]:  The type of object to parse (either 'dict' or 'list')

        Returns:
            i [int]:  The index on of the string where the highet level list
                        or dictionary ends.
        """

        openingChar = BRACKET_CHARS[type][0]
        closingChar = BRACKET_CHARS[type][1]

        # logger.debug(f"Search for close str: {string}")

        #- Check that the appropraite BRACKET_CHAR is actually in string
        if openingChar not in string:
            logger.error(f"String does not contain {type} opening char "\
                f"'{openingChar}.")
            sys.exit()

        # #- Remove first opening char and any preceding text
        # string = openingChar.join(string.split(openingChar)[1:])

        i = 0
        #-Increment to the first opening char:
        while string[i] != openingChar:
            i+=1
        i+=1

        # logger.debug(f"Search for close str: {string[i:]}")

        level = 1
        while True: # Find matching parenthesis
            if i >= len(string):
                userMsg("Unhandled expression.  Could not find "\
                    f"end of list on line {self.i+1} of {self.filepath}.",
                    'WARNING')
                return None
            if string[i] == openingChar:
                level+=1
            if string[i] == closingChar:
                level-=1
            if level == 0:
                found = True
                break 
            i+=1


        # logger.debug(f"list ended at index {i} at char '{string[i]}'.")

        return i
            
    def _parseDict(self, name):
        """
        Recursively parse a dictionary storing values as ofDict 
        """

        i_start = self.i
        # - Find the end of dictionary        
        i_end = self._findDictOrListEndLine('dict')

        # logger.debug(f"Parsing dictionary '{name}'.")
        # logger.debug(f"line[{self.i+1}] '{self.lines[self.i].strip()}'.")

        #TODO:  Store FoamFile as ofFoamFile type rather than dict 
        # if name == 'FoamFile':
        #     dict_ = ofFoamFile()
        # else:
        #     dict_ = ofDict(_name=name)

        dict_ = ofDict(_name=name)


        # self.i -= 1 #- reset index because will increment automatically in
                    #  _parseLine

        #- skip the opening '{'
        if '{' in self.lines[self.i]:
            line_ = self.lines[self.i].strip()
            extraLine = '{'.join(line_.split('{')[1:])
            if extraLine != "":
                self._addExtraLine(extraLine) 
        self.i += 1

        while self.i <= i_end:
            value_ = self._parseLine()
            if value_ is not None:
                if isinstance(value_, ofDict):
                    dict_.update({value_._name: value_})
                elif hasattr(value_, 'name'):
                    dict_.update({value_.__getattribute__('name'): value_})    
                else:
                    # logger.debug(f"{type(value_)} attributes: {vars(value_).keys()}")
                    # logger.error("Invalid type returned to dictionary")
                    # sys.exit()
                    dict_.update({None: value_})
                # logger.debug(f"{type(value_)} attributes: {vars(value_).keys()}")
                # dict_.update({value_.__getattribute__(name_): value_})

        # logger.debug(f"dict_:\n{dict_}")

        self.i-=1 # Reset line index since it will increment in _parseLine

        # logger.debug(f"Finished parsing dict {name} on line {self.i+1}")


        return dict_

    def _findDictOrListEndLine(self, type, string=None):
        """
        Find the line that terminates the dictionary starting on the currently
        parsed line (i.e. the `self.i'th line)

        Parameters:
            type [str]:  The type of object to parse (either 'dict' or 'list')

        Returns:
            i [int]:  The line on which the current list or dictionary ends.
        """

        def searchLine(level, i):
            line = self.lines[i]
            for char in line:
                if char == BRACKET_CHARS[type][0]:
                    level += 1
                    # logger.debug(f'found char: {BRACKET_CHARS[type][0]}')
                    # logger.debug(f"level: {level}")
                    # logger.debug(f"line: {i}")
                if char == BRACKET_CHARS[type][1]:
                    level -= 1 
                    # logger.debug(f'found char: {BRACKET_CHARS[type][1]}')
                    # logger.debug(f"level: {level}")
                    # logger.debug(f"line: {i}")
            return level

        # check if list begins and ends on single line
        if self.lines[self.i].count(BRACKET_CHARS[type][0]) \
        == self.lines[self.i].count(BRACKET_CHARS[type][1]):
            return self.i

        level = 0

        i_ = self.i


        #- Parse to the first opening bracket to initialize second while loop
        while level == 0:
            if i_ >= len(self.lines):
                userMsg(f'Invalid syntax.  Could not locate start of '\
                    f'{type} from line {self.i+1} in file {self.filepath}.',
                    'ERROR')

            level = searchLine(level, i_)
            i_+=1

        # logger.debug("End of initialization loop.")

        while level > 0:
            if i_ >= len(self.lines):
                userMsg(f'Invalid syntax.  Could not locate end of '\
                    f'{type} starting on line {self.i+1}.', 'ERROR')
            line = self.lines[i_]
            # logger.debug(f"i: {i_}")
            # logger.debug(f"line: {line}")
            for char in line:
                if char == BRACKET_CHARS[type][0]:
                    level += 1
                    # logger.debug(f'found char: {BRACKET_CHARS[type][0]}')
                    # logger.debug(f"level: {level}")
                    # logger.debug(f"line: {i_+1}")
                if char == BRACKET_CHARS[type][1]:
                    level -= 1 
                    # logger.debug(f'found char: {BRACKET_CHARS[type][1]}')
                    # logger.debug(f"level: {level}")
                    # logger.debug(f"line: {i_+1}")
            i_+=1

        # logger.debug(f"Found {type} entry from lines {self.i+1} to {i_}.")

        return i_-1
            

    def _parseFoamFile(self):
        foamFile = ofFoamFile()
        while self.lines[self.i].strip() != '}':
            # logger.debug(f"Parsing FoamFile line {self.i+1}")
            if self.i == len(self.lines):
                userMsg("Could not find end of 'FoamFile'.", "ERROR")
            # value_ = self._parseLine()
            # foamFile.update({value_.name: value_})
            foamFile.update(self._parseLine())
            # logger.debug(f"FoamFile dict keys: {foamFile.keys()}")
        
        return foamFile


    def _parseIncludes(self, key, value):
        """
        Extract value as the appropriate include type
        """
        logger.debug(f"parsing key '{key}', and value '{value}'.")

        if key == '#includeEtc':
            return ofIncludeEtc(value)
        elif key == '#includeFunc':
            return ofIncludeFunc(value)
        else:
            return ofInclude(value)

    def _parseTable(self, name, string = None):
        """
        Parse a table entry specified as 

        <name>   table
        (
            (0.0 (1 2 3))
            (1.0 (4 5 6))
        );

        If string is 'None', parses lines starting with '('.  else parses a 
        string starting at '('

        """

        if string is not None: # parse string 
            line = string.strip(';')
            # logger.debug(f"parseTable string: {string}")
            if line.split()[1] == 'table': # whole line is passed as input
                # lineList = line.split()[2:] # Remove the 'table' designation
                lineList = self._getLinesList(line)[2:] # Remove the 'table' designation
            elif line.strip().startswith('(('):  # only list value is passed as input
                # lineList = line.split()
                lineList = self._getLinesList(line)
            else:
                userMsg(f"Unhandled syntax for table found on line "\
                    f"{self.i+1} of {self.filepath}.", "ERROR")
            list_ = self._parseListValues(" ".join(lineList))
            return ofTable(name=name, value = list_) 
        else: # parse lines
            line = self.lines[self.i]
            list_ = self._parseList(name)
            return ofTable(name=name, value = list_.value)

    def _parseUniformField(self, name, string = None):
        """
        Parse a uniform field entry specified as 

        <name>   uniform <value>

        where value is either a scalar, vector, spherical tensor, symmetric
        tensor or tensor.

        if `string` is not `None` parses `string` rather than 
        `self.lines[self.i]`.

        """

        if string is not None: # parse string 
            line = string.strip(';')
        else:
            line = self.lines[self.i].strip(';')
        # logger.debug(f"parseUniformField string: {line}")
        if line == "":
            return None
        if line.split()[1] == 'uniform': # whole line is passed as input
            # lineList = line.split()[2:] # Remove the 'table' designation
            lineList = self._getLinesList(line)[2:] # Remove the 'table' designation
        else:
            return None
            # userMsg(f"Unhandled syntax for ofUniformField found on line "\
            #     f"{self.i+1} of {self.filepath}.", "ERROR")
        valueStr_ = line.split('uniform')[-1].strip()
        # logger.debug(f"valueStr: {valueStr_}")
        # logger.debug(f"name: {name}")
        type_, value_ = self._parseValue(valueStr_)
        # logger.debug(f"type: {type_}")
        # logger.debug(f"value: {type_(value=value_)}")
        value__ = type_(value=value_)
        return ofUniformField(name=name, value=value__) 
        # else: # parse lines
        #     line = self.lines[self.i]
        #     type_, value_ = self._parseValue(line)
        #     return ofUniformField(name=name, value = type_(value=value_))

    @staticmethod
    def _parseValue(value):
        """
        Parse a single value to get the appropraite ofType.
        """
        # TODO: Should I assume list values of certain length are tensors?
        # TODO:  Add ofScalar?

        if value is True or value is False:
            return ofBool, value
        # elif isinstance(value, int):
        #     return ofInt, value
        try:
            int(value)
            #check that fractional value was not truncated
            if isclose(int(value), float(value)):
                return ofInt, int(value)
        except (ValueError, TypeError):
            pass
        try:
            float(value)
            return ofFloat, float(value)
        except (ValueError, TypeError):
            pass

        if value is None:
            return None, None

        #Check for list with specified number of entries.  e.g. 
        #2((0 0) (500 1))
        if re.match(r'[0-9]+\(.+', value):
            return ofSplitList,
        if isinstance(value, _ofTypeBase):
            return type(value), value

        if not isinstance(value, str):
            raise TypeError(f"Invalid type '{type(value)}' found for 'value'")

        value = value.strip()

        #- Ignore empty string        
        if value == '':
            return None, None

        #try to convert to numeric
        try:
            v_ = int(value)
            return ofInt, v_
        except ValueError:
            pass
        try:
            v_ = float(value)
            return ofFloat, v_
        except:
            pass

        #- Check for ofVar
        if len(value.split()) == 1 and value[0] == '$':
            v_ = ofVar(value=value)
            return ofVar, v_

        # logger.debug(f"value: '{value}'")

        # check for a list field type.  e.g. a spherical tensor '(0)' 
        if value[0] == '(' and value[-1] == ')':
            #- Value is a list
            try:
                value_ = []
                for v in value.strip('()').split():
                    value_.append(float(v))
                # logger.debug(f"value_: {value_}")
            except ValueError:
                pass
            else:
                # logger.debug("finding list field type...")
                try:
                    ofSphericalTensor(value=value_)
                    return ofSphericalTensor, value_
                except:
                    pass

                try:
                    ofVector(value=value_)
                    # logger.debug("found ofVector.")
                    return ofVector, value_
                except:
                    pass

                try:
                    ofSymmTensor(value=value_)
                    return ofSymmTensor, value_
                except:
                    pass

                try:
                    ofTensor(value=value_)
                    return ofTensor, value_
                except:
                    pass

            #- Check if the str value can be conveted into a list
            list_ = value.strip('()').split()
            # if len(list_) > 1:
            #     value_ = []
            #     valid = True
            #     for v in list_:
            #         # TODO:  Need to return non-numeric values too
            #         try:
            #             v_ = float(value.strip('()'))
            #             value_.append(v_)
            #         except:
            #             valid = False
            #     if valid:
            #         return ofList, value_                

            return ofList, list_

        #- check if value is ofDimension
        if all(v in value for v in ['[', ']']):
            dimList = []
            for value_ in value.split():
                dimList.append(value_.strip('[];'))
            try: 
                dimValue = ofDimension(value=dimList)
            except:
                pass

        try:
            value_ = float(value)
            if '.' in value:
                return ofFloat, value_
            else:
                return ofInt, int(value_)
        except ValueError:
            pass
        # try:
        #     value_ = int(value)
        #     return ofInt, value_
        # except ValueError:
        #     pass
        if any([value == b for b in OF_BOOL_VALUES.keys()]):
            return ofBool, value

        if value != ';' or value != '':

            return ofStr, value.strip(';')
        else:
            return None, None

    def _parseLineLenGreaterThanTwo(self):
        """
        Parse a line that has more than two words.
        """

        # logger.debug("Parsing line of length greater than two...")

        #TODO:  Does this need to check self.extraLine as well?
        line = self.lines[self.i]
        entryName = None

        #- Check if commented line
        comment = self._parseComments()
        if comment:
            logger.debug(f"Found comment on line {self.i}")
            return None

        #- Check if the line contains a dimensioned type
        dimType = self._parseDimensionedType()
        # logger.debug(f"dimType: {dimType}")
        if dimType is not None:
            logger.debug(f"Found dimension on line {self.i}")
            return dimType
        
        #- Check if value is a dimension
        #   (e.g. dimension     [0 2 -2 0 0 0 0];)
        dimValue = self._parseDimensionValue()
        # logger.debug(f"dimValue: {dimValue}")
        if dimValue is not None:
            logger.debug(f"Found dimensioned vlaue on line {self.i}")
            return dimValue

        #- Check if value is a bounging box
        #   (e.g. box     (0.0 0.0 0.0) (1.0 1.0 1.0);
        boxValue = self._parseBoundBoxValue()
        # logger.debug(f"dimValue: {dimValue}")
        if boxValue is not None:
            logger.debug(f"Found bound box on line {self.i}")
            return boxValue

        #- check if the line value terminates in an open list or dict
        logger.debug("Checking for open list or dict")
        line_ = copy.deepcopy(line)

        while True:
            nl = 0
            nd = 0
            # Extract key values, note that key may contain parenthises, 
            # e.g. as in the fvSchemes dictionary
            lineList = self._getLinesList(line_)
            entryName = lineList[0]

            valueStr = " ".join(lineList[1:])
            # logger.debug(f"valueStr: {valueStr}")
            for char in valueStr:
                if char == '(':
                    nl+=1
                if char == ')':
                    nl-=1
                if char == '{':
                    nd+=1
                if char == '}':
                    nd-=1

            # logger.debug(f"nl / nd: {nl} / {nd}")
            
            if nl <= 0 and nd <= 0:
                break

            if nl > 0:
                # logger.debug("Found open list..")
                self.i += 1
                line_ += self.lines[self.i]
            if nd > 0:
                # logger.debug("Found open dictionary...")
                self.i += 1
                line_ += self.lines[self.i]

            # self.i+=1
            #line+=self.lines[self.i]
            
        line = line_

        #Parse the line to extract the entry name
        lineList = self._getLinesList(line_)
        if lineList[1] == 'table':
            entryName = " ".join(lineList[:2])
            valueStr = " ".join(lineList[2:]).strip()
            # logger.debug(f"entryName: {entryName}")
            # logger.debug(f"valueStr: {valueStr}")
        else:
            entryName = lineList[0]
            valueStr = " ".join(lineList[1:]).strip()

        if ';' in line:
            #- add extra text after ';' as a new line to be parsed later
            #- Remove ';'.  Assuming within list or dict.  Other possibilities 
            # (e.g dimensioned types) should be handled prior to this point in 
            # the method.
            # logger.debug(f"line[{self.i+1}]: {line}")
            extraText = ''.join(line.split(';')[1:]).replace('\n', '')
            self._addExtraLine(extraText)
            #line = line.split(';')[0][:-1] 
            line = line.split(';')[0]+';' # do not remove last ')' or '}'
            # logger.debug(f"line[{self.i+1}]: {line}")


        # logger.debug(f"valueStr: {valueStr}")

        # if '(' in valueStr or '{' in valueStr:
        if valueStr.startswith('(') or valueStr.startswith('{'):
            #- Found list or dict
            # - find the entry type
            # logger.debug(f"valueStr: {valueStr}")
            for i, char in enumerate(valueStr):
                # logger.debug(f"i: {i}")
                if char == '{' or char == '(':
                    # reevaluate entry name to be everything before opening list
                    line_ = entryName+" "+valueStr
                    # logger.debug(f"line_: {line_}")
                    entryName = line_[:len(entryName)+i].lstrip().rstrip()

                    # valueList = line[i:].split(" ").rstrip(char+';')
                    break

            # logger.debug(f"entryName: {entryName}")

            if entryName:
                entryNameList = entryName.split()
                #- check for table type
                if len(entryNameList) == 2 and entryNameList[1] == 'table':
                    list_ = line.strip()[len(entryName):]
                    # self._parseTable(entryNameList[0], list_)
                    return self._parseTable(entryNameList[0], line)
                #- check for uniform field
                if len(entryNameList) == 2 and entryNameList[1] == 'uniform':
                    list_ = line.strip()[len(entryName):]
                    return self._parseUniformField(entryNameList[0], line)
                #- check for named list as value
                elif len(entryNameList) == 2:
                    list_ = line.strip()[len(entryName):]
                    listStr = " ".join([entryNameList[1], list_])
                    value_ = ofList(self._parseListValues(listStr),
                                            entryNameList[1])
                    return ofList(value_,  entryNameList[0])
                else:
                    #- remove entry name from line string
                    line_ = line.strip()[len(entryName):].strip()
                    # logger.debug(f"line_: {line_}")
                    value = self._parseListOrDict(entryName, line=line_)
                    return value
            else:
                value = self._parseListOrDict(None, line=line)
                return value
                # userMsg(f"Invalid syntax found on line {self.i+1} of file "
                # f"{self.filepath}", 'ERROR')
                # sys.exit()
        else:
            #- Check for uniform scalarField
            lineList_ = self._getLinesList(line)
            value = self._parseUniformField(lineList_[0], line)
            if value is not None:
                return value

            #- Assume entry is a key value pair with a muliple word value.
            #      (e.g. 'default       Gauss linear;')
            if line[-1] != ';' and self.needSemicolon:
                return self._parseMultilineStatement()
            else:
                lineList = self._getLinesList(line)
                return self._parseSingleLineEntry(key=lineList[0], 
                                       value=' '.join(lineList[1:]))

    def _parseMultilineStatement(self):
        """
        Parse a key value pair that has a multi-word value that spans multiple
        lines.  Assumes the first word on first line is the keyword.  Special
        cases (e.g. tables and uniform fields) should be handled prior to
        calling this method
        """

        # logger.debug("Parsing multiline statement.")

        def _parseVal(values):
            """
            Parse value storing comment in the ofType
            """
            foundComment = False

            # logger.debug(f"values line: {values}")

            #- Parse comment 
            comment = self._parseComments(values)
            if comment is not None:
                return comment


            if '//' in values:
                foundComment = True
                values = values.split('//')[0]
            type_, value_ = self._parseValue(values)

            # logger.debug(f"type values: {type_}: {value_}")
            # logger.debug(f"found comment: {foundComment}")
            # logger.debug(f"self.comment: {self.comment}")

            if type_ is not None:
                return type_(value_, 
                        _comment=self._getComment() if foundComment else None)
            else:
                return None

        #- Parse first line
        key = self.lines[self.i].split()[0]
        value_ = _parseVal(' '.join(self.lines[self.i].split()[1:]))
        if value_ is not None:
            value = [value_]
        else:
            value = []

        i_start = self.i

        while ';' not in self.lines[self.i]:
            self.i += 1
            if self.i >= len(self.lines):
                userMsg("Invalid Syntax.  Could not find end of statement "\
                    f"starting on line {i_start+1} in {self.filepath}.", "ERROR")
            value_ = _parseVal(self.lines[self.i])
            if value_ is not None:
                value.append(value_)

        if self.i == i_start:
            logger.warning("Parsing single line as 'ofMultilineStatement'.")

        return ofMultilineStatement(name=key, value=value)

    def _parseVerbatimEntry(self, lineList=None, name=None):
        """
        Parse entries that contain a (potentially) multiline verbatim string as 
        the value
        
        These include functionEntry types (e.g. evalEntry, codeStream, ifEntry, 
        etc.), and verbatimCode types used in the coded function object 
        (e.g. codeExecute, codeWrite, etc.)

        """
        if lineList is None:
            lineList = self._getLinesList(self.lines[self.i])

        logger.debug(f"lineList: {lineList}")

        if (lineList[0].strip()[0] != '#' 
            and lineList[0] not in OF_VERBATIM_CODE_ENTRIES.keys()):
            userMsg(f"Unhandled Pattern:  String found on line {self.i} of " \
                    f"file {self.filepath} cannot be parsed.", 'ERROR')

        vType = lineList[0].strip('#')

        #- Determine which type of bracket character is used ('{', '"' or '#{')
        bi = 0 if len(lineList) == 1 else 1
        bCharType = None
        if vType[-1] == '{':
            bCharType = 1
            vType=vType[:-1] #- remove the '{' from the name
        # elif vType == 'codeExecute':
        elif vType in OF_VERBATIM_CODE_ENTRIES.keys():
            bCharType = 2
        elif lineList[bi][0] == '"':
            bCharType = 0
        elif lineList[bi][:1] == '#{':
            bCharType = 2
        else:
            #- Search the next lines
            while bCharType is None:            
                self.i +=1
                # lineList = lineList = self._getLinesList(self.lines[self.i])
                lineList = self._getLinesList(self.lines[self.i])
                if len(lineList) > 0:
                    logger.debug(f"lineList[0][0]: {lineList[0][0]}")
                    if lineList[0][0] == '{':
                        bCharType = 1
                    elif lineList[0][0] == '"':
                        bCharType = 0
                    elif lineList[0][:1] == '#{':
                        bCharType = 2
                    else:
                        logger.error(f"Could not find functionEntry bracket type.")
                        sys.exit()

        openingChar = BRACKET_CHARS['verbatim'][bCharType][0]
        closingChar = BRACKET_CHARS['verbatim'][bCharType][1]

        #- Check if single line entry
        valueList = ' '.join(lineList[1:]).split(';')
        #TODO:   Does this capture anything after the ';'?
        if closingChar in ''.join(lineList[1:])[1:]:
            value = valueList[0].rstrip(closingChar).strip()
            logger.debug(f"valueList: {valueList}")
            if len(valueList) > 1:
                self._addExtraLine(' '.join(valueList[1:]))
        else:
            value = ' '.join(valueList)+"\n"
            value = value.lstrip(openingChar)
            self.i += 1
            logger.debug(f"closingChar: {closingChar}")
            line_= self.lines[self.i]
            foundClosing = False
            while not foundClosing:
                logger.debug(f"line_: {line_}")
                # prevChar=None
                # for c in range(len(line_)):
                #     if line_[c] == closingChar:
                #         logger.debug("found closingChar.")
                #         #make sure '}' is not part of '#}'
                #         if closingChar == '}' and prevChar == '#':
                #             pass
                #         else:
                #             break
                #     value += line_[c]
                #     prevChar = line_[c]
                # value += "\n"
                value += line_+"\n"
                self.i += 1
                if self.i > len(self.lines):
                    userMsg("Unhandled Pattern:  Could not find end of "\
                            "function entry", "ERROR")
                line_= self.lines[self.i]
                foundClosing = re.search(rf"(?<!\#)\{closingChar}",line_) if \
                    closingChar == '}' else (closingChar in line_)
                # line_= self.lines[self.i]
            #- Add last line
            if line_.strip().strip(closingChar+';\n') != '':
                value += line_.strip(closingChar+';')+"\n"
        #- Add comment
        comment = None
        if self.lines[self.i].startswith(closingChar):
            #check for trailing comment
            extraLineList = self.lines[self.i].split(closingChar)
            if len(valueList) > 0:
                line = ''.join(extraLineList).strip()
                if line.startswith('//'):
                    comment = line.lstrip('//')
        else:
            # valueList = self.lines[self.i].split(closingChar)
            # value += valueList[0]+'\n'
            if len(valueList) >= 1: 
                extraLine = "".join(valueList[1:])
                if extraLine.startswith('//'):
                    comment = extraLine.lstrip('//')


        logger.debug(f"OF_FUNCTION_ENTRIES: {OF_FUNCTION_ENTRIES.keys()}")
        logger.debug(f"vType: {vType}")

        if vType in OF_FUNCTION_ENTRIES.keys():
            rv = OF_FUNCTION_ENTRIES[vType](
                value, name=name, _comment=comment
                )
            rv.vBracketType = bCharType
        else:
            rv = OF_VERBATIM_CODE_ENTRIES[vType](
                value,_comment=comment
                )
        
        return rv




    def _parseComments(self, line=None):
        """
        Returns 'ofComment' if the current line is a C++ comment type.  If block 
        comment, self.i is incremented to end of comment block.  If line is not 
        a comment, stores any inline comments to self and returns line string 
        without an inline comment
        """
        #TODO: Doesnt handle comments in middle of list (Maybe this should be 
        # handled elsewhere)

        if line is None:
            line = self.lines[self.i]

        # logger.debug("Checking for comment.")
        # logger.debug(f"line: {line}")

        if line.strip().startswith('//'):
            return ofComment(line.strip()[2:])

        if line.strip().startswith('/*'):
            firstLine = True
            comment_ = ""
            while not self.lines[self.i].strip().endswith('*/'):
                if firstLine:
                    #- Remove the '*/
                    comment_ += self.lines[self.i].strip()[2:]
                    firstLine = False
                else:
                    comment_ += self.lines[self.i].strip()
                self.i+=1
                if self.i >= len(self.lines):
                    userMsg("Could not find end of commented block in"\
                        f" file {self.filepath}.", 'ERROR')
            comment_ += self.lines[self.i].strip()[:-2] # remove ending `*/`
            return ofComment(comment_, block=True)

        if '//' in line:
            self.comment.append('//'.join(line.split('//')[1:]))
            # logger.debug(f"comment: {self.comment}")

        return None

    def _parseDimensionedType(self):
        """ 
        Check to see if the line contained a entry for a dimensioned type.  If 
        so, return the ofType, else return None

        dimensioned types have the syntax: 

        nu      [0 2 -1 0 0 0 0] 1.138e-06;

        """

        i_ = self.i
        line = self.lines[i_]
        #- Parse the file to the end of the statement (maybe not at end of line)
        while ';' not in line:
            if i_ >= len(self.lines)-1:
                return None # No staement found, cant be dimensioned type
            i_+=1
            line += self.lines[i_]
        
        # lineList = line.split()
        lineList = self._getLinesList(line)

        if not len(lineList) >= 9:
            return None # Need at least nine entries to define a dimensioned type 

        try: 
            ofWord(lineList[0])
        except ValueError:
            return None  # First item is not a ofWord, and can't be a keyword
        
        if '[' not in lineList[1]:
            return None # Second item does not start a dimension specification
        
        if not any([']' in val for val in lineList[7:10]]): # handle 
            return None                                     # [0 1 2 0 0 0 0]
                                                            # [ 0 1 2 0 0 0 0]
                                                            # [0 1 2 0 0 0 0 ]
                                                            # [ 0 1 2 0 0 0 0 ]

        #- Get the dimension string
        dims = []
        try:
            d_ = int(lineList[1].strip('['))
            dims.append(d_)
        except ValueError:
            return None #- Dimensioned quantity is not an int

        for i, d in enumerate(lineList[2:10]):
            # logger.debug(f"i: {i}")
            try:
                d_ = int(d.strip(']'))
                dims.append(d_)
            except ValueError:
                return None
            if ']' in d:
                break
        
        #- parse the value
        strValue = " ".join(lineList[i+3:]).strip(';')
        type_ , value = self._parseValue(strValue)

        # logger.debug(f'type_: {type_}')
        # logger.debug(f'value: {value}')

        returnType = None
        if type_ is ofInt or type_ is ofFloat:
            returnType = ofDimensionedScalar
        elif type_ is ofSphericalTensor:
            returnType = ofDimensionedSphericalTensor
        if type_ == ofList:
            try:
                [float(v) for v in value]
            except ValueError:
                return None # not all values in list are numeric
            if len(value) == 3:
                returnType = ofDimensionedVector
            elif len(value) == 5:
                returnType = ofDimensionedSymmTensor
            elif len(value) == 9:
                returnType = ofDimensionedTensor

        if returnType:
            self.i = i_ 
            return returnType(value=value, name=lineList[0],
                              dimensions=dims, _comment=self._getComment())

        return None #- Could not find a suitable dimensioned type based on
                    # length of list 


    # def _storeOFDictValue(line):
    #     pass


    # def _appendOFDictEntry(line):
    #     pass


    # def _storeofListValue(line):
    #     pass


    # def _getMultiLineType(line):
    #     switcher = {
    #         '{': 'startDict',
    #         '(': 'startList'

    #     }

    #     typeSwitcher = {
    #         '{': ofDict(),
    #         '(': ofList()
    #     }

    #     self.entryList[self.entryList.keys[-1]] = typeSwitcher.get(line)

    #     return [switcher.get(line, 'multiLineValue'), 'read']


    # def _storeOFDictSingleLineSingleValuedEntry(line):
    #     values = line.split(" ")
    #     if len(values) != 2:
    #         raise Exception("Not able to process line format.")
    #     if values[1].isnumeric() is True:
    #         if '.' in values[1]:
    #             pyOFDict.add(ofFloatValue(values[0], values[1]))
    #         else:
    #             pyOFDict.add(ofIntValue(values[0], values[1]))
    #     elif values[1] in OF_BOOL_VALUES:
    #         pyOFDict.add(ofBoolValue(values[0], values[1]))
    #     else:
    #         pyOFDict.add(ofStrValue(values[0], values[1]))

    #     return ['newLine', 'end']

    # def _storeOFDictMultiLineEntryName(line):
    #     _currentEntryKey = line
    #     self.entryList.update({line: None})

    # def _ofDictFindBlockEntryStartStop(file, blockList, searchValues=False):
    #     #TODO:  Account for the case of opening and closing parenthesis or brackets
    #     #  on the same line.
    #     relPath = file
    #     file = os.path.join(os.getcwd(), file)

    #     if os.path.isfile(file) is False:
    #         raise FileNotFoundError(file)

    #     copyfile(file, file+"_old")

    #     start = 0
    #     stop = 0

    #     try:
    #         old = open(file, 'r')
    #         for line in old:
    #             stop+=1
    #         old.seek(0)
    #         lines = old.readlines()

    #         if stop <= 0:
    #             raise Exception('File is empty: '+file)

    #         if blockList is not None:

    #             for block in blockList:
    #                 #- initialize variables to be defined below
    #                 openStr = None
    #                 closeStr = None

    #                 #old.seek(start-1)

    #                 # while 'block' is not the first word in the line:
    #                 while True:
    #                     lineList = lines[start].strip().split(" ")
    #                     if block == lineList[0]:
    #                         break
    #                     start += 1
    #                     if start >= stop:
    #                         logger.warning("End of file '"+relPath+"' reached "\
    #                                 "without finding a match for block '"+\
    #                                 str(block)+"'.")
    #                         return None, stop-1
    #                 for i in [0,1]: #search line with block name and next line
    #                     if len(lines[start+i].split(" ")) > 1:
    #                         #- Search for opening and closing of block on the same line
    #                         for openChar, closeChar in zip(['(', '{'],[')', '}']):
    #                             if openChar in lines[start+i]:
    #                                 openStr = openChar
    #                                 closeStr = closeChar
    #                                 start = start+i
    #                                 break
    # #                                if closeStr in lines[start+i]:
    # #                                    print("Warning:  No values found matching block '"+block+"' within "+file)
    #                 #- If block is not opened on same line assume it is opened on next
    #                 #  line:
    #                 if not openStr:
    #                     start+=1
    #                     openStr = lines[start].lstrip()[0]

    #                 if openStr == '(':
    #                     closeStr = ')'
    #                 elif openStr == '{':
    #                     closeStr = '}'
    #                 else:
    #                     raise Exception("Unexpected file format enountered at line "+str(start+1)+" of "+file)
    #                 stop = start

    #                 nOpenStr = 1
    #                 nCloseStr = 0

    #                 while nOpenStr > nCloseStr:
    #                     if stop >= len(lines)-1:
    #                         raise Exception("End of file '"+relPath+"' reached without terminating block.")
    #                     stop+=1
    #                     nOpenStr+= lines[stop].count(openStr)
    #                     nCloseStr+= lines[stop].count(closeStr)
    #             start+=1
    #         else:  #Search top level.  Find end of file
    #             if len(lines) > 0:
    #                 start = len(lines)-1
    #                 stop = len(lines)-1
    #             else:
    #                 start = 0
    #                 stop = 0

    #     except:
    #         copyfile(file+"_old", file)
    #         raise

    #     return start, stop

    def _parseDimensionValue(self):
        """ 
        Check to see if the line containd key value entry for a ofDimension 
        value.  If so, return the ofType, else return None.

        Example syntax: 

        dimension      [0 2 -1 0 0 0 0];

        """

        line = self.lines[self.i]

        lineList = self._getLinesList(line)
        
        try:
            ofWord(lineList[0])
        except:
            return None  # first item is not valid key
        #- try to convert list to dimension, return None if error
        dimList = []
        for value in lineList[1:]:
            try:
                v = int(value.strip('[];'))
                dimList.append(v)
            except ValueError:
                pass
        # logger.debug(f"dimList: {dimList}")
        try:
            dimValue = ofNamedDimension(name=lineList[0], 
                                        dimensions=dimList)
            return dimValue
        except ValueError:
            return None

    def _parseBoundBoxValue(self):
        """ 
        Check to see if the line contains key value entry for a ofBoundBox 
        value.  If so, return the ofType, else return None.

        Example syntax: 

        box      (0.0 0.0 0.0) (1.0 1.0 1.0);

        """

        line = self.lines[self.i]

        logger.debug(f"Parsing bound box: '{line}'")

        lineList = self._getLinesList(line)

        logger.debug(f"lineList: {lineList}")
        
        try:
            ofWord(lineList[0])
        except:
            logger.debug("Failed.  First entry not a valid key.")
            return None  # first item is not valid key

        # #- determine if value has 6 numeric entries
        # n = 0
        # for v in lineList[1:]: 
        #     if v.strip('();').isnumeric(): 
        #         n+=1
        # logger.debug(f"# numeric entries: {n}")
        # if n != 6:
        #     logger.debug("Failed.  Value does not contain 6 numeric entries.")
        #     return None # value does not contain 6 entries   

        # #- determine if entries are two lists of three
        # if not all([
        #     lineList[1].strip()[0] == '(',
        #     lineList[3].strip()[-1] == ')',
        #     lineList[4].strip()[0] == '(',
        #     lineList[6].strip(';')[-1] == ')',
        # ]):
        #     logger.debug("Failed.  Value does not contain two lists of 3 items.")
        #     return None

        # #- determine if all items are numeric:
        # bounds = []
        # for j in range(2): # for each list of three
        #     bounds.append([])
        #     for i in range(3): # for each item in list
        #         try:
        #             v_ = float(lineList[3*j+i+1].strip('();'))
        #         except ValueError:
        #             logger.debug("Failed.  Value entry is not numeric.")
        #             return None
        #         bounds[-1].append(v_)
        
        logger.debug(f"match string: {' '.join(lineList[1:])}")

        matches = re.findall(r"(?<=\()[\s\d.-]+(?=\))", " ".join(lineList[1:]))

        logger.debug(f"matches: {matches}")

        if len(matches) != 2:
            #- Value does not contain two lists
            return None
        bounds=[]
        for match in matches:
            bounds.append([])
            values = match.split()
            if len(values) != 3:
                #- List does not have 3 values
                return None
            for v in values:
                try:
                    v_ = float(v)
                except ValueError:
                    #- List values are not numeric
                    return None
                bounds[-1].append(v_)
                

        logger.debug("Found bounding box.")
        return ofBoundBox(name=lineList[0], value=bounds)




    def _findEndOfDict(self):
        """
        Returns the line number of an OpenFOAM dictionary corresponding to the
        whitespace after the last entry of the root dictionary.
        """
        #- TODO: Handle the case where a subdict of an existing dictionary is
        #  not found.

        endofDict = None

        lines = self.lines
        nLines = len(lines)
        for i, line in enumerate(reversed(lines)):
            #TODO:  This does not properly handle commented blocks at end of
            #       file.
            if (len(line.strip()) > 0 and
                any([line.lstrip()[:2] == c for c in ['//', '/*']]) is False):
                    endOfDict = nLines - i
                    break
        if endOfDict is None:
            endOfDict = self._findEndOfHeader()

        # logger.debug('endofDict: '+str(endOfDict))

        return endOfDict

    def _findEndOfHeader(self):
        # foamFileFound = False
        # foamFileStart = False

        # with open(self.filepath) as f:
        #     for i, line in enumerate(f.readlines()):
        #         if line.strip() == 'FoamFile':
        #             foamFileFound = True
        #         if (foamFileFound and line.startswith('{')):
        #             foamFileStart = True
        #         if (foamFileFound and foamFileStart and '}' in line):
        #             return i+1

        #-  Parse to end of first commented block, and always parse the FoamFile
        #TODO: Can this be made more efficient, i.e. without two `with open(..)`
        #       statements.
        with open(self.filepath) as f:
            for i, line in enumerate(f.readlines()):
                if '*/' in line:
                    return i+1

        logger.error('Invalid OpenFOAM file specified: '+str(self.filepath))
        sys.exit()
