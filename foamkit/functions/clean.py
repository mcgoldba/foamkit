from foamkit.types import ofDictFile
import copy

def clean(ofDict, keys=None):
    """
    Return a copy of an ofDict or ofDictFile with all entries removed, except
    the header, the FoamFile dictionary and '// * * * *' separator comments
    (see `ofDictFile.clear`).  The argument is not modified.

    Parameters
    ----------

    ofDict : ofDict or ofDictFile
        The dictionary to clean.

    keys : unused

    """
    ofDict_ = copy.deepcopy(ofDict)

    for key in ofDictFile._clearableKeys(ofDict_):
        del ofDict_.__dict__[key]

    return ofDict_
