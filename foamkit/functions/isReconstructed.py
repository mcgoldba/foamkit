import os
import sys
import re

def isReconstructed(self):
        reconstructedTime = getLatestTime(self.caseDir)
        reconstructed = True
        items = os.listDir(self.caseDir)
        if any([re.search('processor0', item) and
                os.path.isdor(item) and
                float(getLatestTime(item)) >= float(reconstructedTime)
                for item in items ]):
            reconstructed = False

        return reconstructed
