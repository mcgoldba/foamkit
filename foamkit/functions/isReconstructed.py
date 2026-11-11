from foamkit.functions.isDecomposed import isDecomposed

def isReconstructed(caseDir=None):
    """
    Return True unless the decomposed ('processor0') data is more recent than
    the reconstructed data (see `isDecomposed`; equal times count as
    reconstructed).

    Parameters:
        caseDir [str or Path]:  The case directory (default: the current
            directory).
    """
    return not isDecomposed(caseDir)
