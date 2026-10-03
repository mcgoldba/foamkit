from foamkit.types import _ofTypeBase, ofComment, ofHeader
import copy

def clean(ofDict, keys=None):
    """
    Clears all entries of ofDict or ofDictFile. 

    Parameters
    ----------

    directory : str
        The case directory in which to search for a valid mesh.

    """

    #TODO:  Can this be implemented as a method the ofDict and ofDictFile classes?

    ofDict_ = copy.deepcopy(ofDict)

    rmKeys = []

    for key, item in ofDict.items():
        if isinstance(item, _ofTypeBase):
            if isinstance(item, ofComment):
                if not item.value.startswith('// * * * *'):
                    rmKeys.append(key)
                continue
            if not (isinstance(item, ofHeader) 
                or item._name=='FoamFile'):
                rmKeys.append(key)

    print(ofDict.__dict__)
    print(ofDict.items())
    print(f'rmKeys: {rmKeys}')

    for key in rmKeys:
        del ofDict_.__dict__[key]
        #ofDict.pop(key)

    return ofDict_