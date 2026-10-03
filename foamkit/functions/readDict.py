import os

def readDict(filepath):
    """
    Reads in a generic  OpenFOAM dictionary file.

    Paarameters
    -----------
    filepath: path
        Location of the dictionary file to be read

    Returns
    -------
    ofDict: dict
        Python dictionary containing the OpenFOAM data
    """

    f = open(filepath, "r")

    dictFile = f.read()

    #- Parse the OpenFOAM header
    [header, dictFile] = dictFile.split('*/',1)
    header+='*/'

    #- Remove commented lines and comment blocks
    dictFile_  = dictFile.split('\n')
    dictFile = []
    commentedBlock = False
    for line in dictFile_:
        if commentedBlock:
            if '*/' in line:
                commentedBlock = False
                dictFile.append(line.split('*/')[-1])
            continue
        if line[:1] == '//':
            continue
        if line[:1] == '/*':
            commentedBlock = True
            continue
        dictFile.append(line.split('//')[0])

    if 'OpenFOAM: The Open Source CFD Toolbox' not in header:
        log.error('File is not an OpenFOAM dictionary.')
        sys.exit()

    print(header)

    dictFile = "\n".join(dictFile)

    cppCommands = dictFile.split(';')

    for cppCmd in cppCommands:
        print(cppCmd)

    #- Parse the foamFile information

    return cppCommands
