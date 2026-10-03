import os
from shutil import copyfile

from .dictUtil import _replaceStringEntry, _replaceSingleLineEntry

def replaceEntry(ofValue, location, filename, rType='singleLine', silent=False):
    #- Base function for ofDict replacements
    #- rType = Replacement type.  One of:  ['string', 'singleLine']

    file = os.path.join(
            os.getcwd(),
            location,
            filename
    )

    #- Check if the file exists
    open(file)

    copyfile(file, file+"_old")

    if rType == 'string':
        found = _replaceStringEntry(
            ofValue.name,
            ofValue.value,
            file,
            silent=silent
        )
    elif rType == 'singleLine':
        #found = _replaceSingleLineEntry(
        #    ofValue.name,
        #    ofValue.value,
        #    ofValue.asString(),
        #    file,
        #    silent=silent
        #)
        found = _replaceSingleLineEntry(
            ofValue,
            file,
            silent=silent
        )
    else:
        raise ValueError("Unrecognized replace type: "+str(rType))

    if found == False:
        copyfile(file+"_old", file)
        raise ValueError("Key "+ str(ofValue.name)+ \
                     " not found in file:  "+ \
                     os.path.join(location,filename)+'\n')
