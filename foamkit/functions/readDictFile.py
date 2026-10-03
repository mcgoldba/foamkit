import foamkit.types as pt


def readDictFile(path):
    """
    Reads an OpenFOAM dictionary from file and returns an ofDictFile object.
    
    Parameters:
        path (pathlib.Path or str): Location of the dictionary file to read.
    
    """

    return pt.DictFileParser(path).readDictFile()