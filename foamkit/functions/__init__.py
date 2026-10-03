import sys

from foamkit.types import ofDictFile, ofDict, ofList, ofInt, ofFloat, \
    ofStr, ofBool, ofDimensionedScalar, ofVector, ofDimensionedVector, TAB_STR

import os
from shutil import copyfile
import re
import math
#import numpy as np
import subprocess
import tempfile

import pint
from pint import UnitRegistry
import json
import pandas as pd
# from functools import reduce
# import operator
# from collections.abc import Mapping

from .readDict import readDict
from .dictUtil import _appendBlockEntryWithBlockName, _replaceStringEntry,\
_replaceSingleLineEntry, _findBlockEntryStartStop, _findEndOfDict,\
_appendBlockEntryWithLineNum, _readDictFile, _ofDictFindBlockEntryStartStop,\
_findEndOfHeader
from ._interpretUnitsAndConvert import _interpretUnitsAndConvert
from ._unitDecoder import _unitDecoder
from .appendEntry import appendEntry
from .getLatestTime import getLatestTime
from .replaceEntry import replaceEntry
from .removeEntry import removeEntry
from .removeBlockEntries import removeBlockEntries
from .readInputs import readInputs
from .writeParams import writeParams
from .printInputs import printInputs
from .cleanDictFile import cleanDictFile
from .isDecomposed import isDecomposed
from .isReconstructed import isReconstructed
from .isMeshed import isMeshed
from .cleanDictFile import cleanDictFile
from .isCase import isCase
from .listCases import listCases
from .monitor import monitor
from .writeConfig import writeConfig
from .readConfig import readConfig
from .extractLogData import extractLogData
from .isDictFile import isDictFile
from .init import init
from .readCaseFromCache import readCaseFromCache
from .writeCase import writeCase
from .load import load
from .restore import restore
from .allRun import allRun
from .readDictFile import readDictFile
from .plot import plot
from .getProbe import getProbe
from .getMonitor import getMonitor
from .foamVersion import foamVersion
from .parseNameTag import parseNameTag
from .clean import clean
from .cloneCase import cloneCase
from .cloneCases import cloneCases

#import logging

#Define padding for blockMeshDict
PAD = 1 / 12 / 3.281 # 1 inch


############################ Member Functions ###############################

######################## Private Member Functions ###########################
