import sys
from pathlib import Path

from pyfoamd.types import _isDictFile

import logging
logger = logging.getLogger('pf')



def isDictFile(file):
    """
    Checks if the argument file is an OpenFOAM dictionary file.  It is assumed
    that all OpenFOAM dictionary files start with a block comment header of the 
    form:

/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  6
     \\/     M anipulation  |
-------------------------------------------------------------------------------
Description
    {Description of file contents}...

\\*---------------------------------------------------------------------------*/
    
    Previous implementation:

    It is assumed that all OpenFOAM dictionary files start with the first 
    uncommented line as 'FoamFile\n'

    Parameters:
        file (str or Path):  The path of the file to test.
    """

    # # -Convert to string in case of Path object
    # file = Path(file)

    # if file.is_dir():
    #     return False

    # isDictFile = False

    # with open(file) as f:
    #     lines = f.readlines()

    #     #- Parse file to first block comment
    #     for i, line in enumerate(lines): 
    #         if line.startswith('*/'):
    #             break

    #     blockComment = lines[i:i+7]

            
    # logger.debug(f"blockComment: {blockComment}")
    # sys.exit()


    return _isDictFile(file)

    #- Previous implementation

    # with open(file) as f:
    #     lines = f.readlines

    #     blockComment = False
    #     # -Check for line or block comments
    #     for line in lines:
    #         if blockComment:
    #             if line.rstrip()[-2:] == '*/':
    #                 blockComment = False
    #             continue

    #         testStr = line.lstrip()[:2]
    #         if testStr == '//':
    #             continue
    #         elif testStr == '/*':
    #             blockComment = True
    #             continue
    #         else:
    #             if line.startswith('FoamFile'):
    #                 isDictFile = True
    #             break

    # return isDictFile
