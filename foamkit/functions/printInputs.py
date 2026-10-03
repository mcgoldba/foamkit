from .readInputs import readInputs

def printInputs(filepath='inputParameters'):

    params = readInputs(filepath)

    print(params)
