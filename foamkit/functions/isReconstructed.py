from foamkit.functions.isDecomposed import isDecomposed

def isReconstructed(caseDir=None):
    """
    Return True unless the decomposed ('processor0') data is at least as
    recent as the reconstructed data (see `isDecomposed`).

    Parameters:
        caseDir [str or Path]:  The case directory (default: the current
            directory).
    """
    return not isDecomposed(caseDir)
