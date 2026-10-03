import subprocess
import sys
from pathlib import Path
import os
from foamkit.functions import isCase
from foamkit import userMsg
from foamkit.types import CaseParser

def allRun(runDir=Path.cwd()):
    # script_ = str(Path(runDir) / 'Allrun')
    # userMsg(f"Running Allrun script from {runDir}.")
    # subprocess.check_call('./'+script_, stdout=sys.stdout, stderr=subprocess.STDOUT)
    case_ = CaseParser(runDir).initOFCase()
    case_.allRun()
