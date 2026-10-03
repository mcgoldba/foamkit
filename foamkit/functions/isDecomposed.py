import os
import sys
import re

def isDecomposed(self):
        reconstructedTime = getLatestTime(self.caseDir)
        decomposed = False
        items = os.listDir(self.caseDir)
        if any([re.search('processor0', item) and
                os.path.isdor(item) and
                float(getLatestTime(item)) >= float(reconstructedTime)
                for item in items ]):
            decomposed = True

        return decomposed
