import os

from .dictUtil import _ofDictFindBlockEntryStartStop, _appendBlockEntryWithLineNum


def removeEntry(file, blockList, searchValues=False):
    #- Removes lists or dicts in an OpenFOAM dictionary that are split between
    #   many lines.
    #- blockList = list heiarchy to be searched
    #-   e.g.  ['geometry', 'wetwell'] removes everything within:
    #-      geometry{ wetwell{*delete_everything_here}}
    #- searchValues = switch to search within a line for block start / stop
    #-  (not yet implemented)

    entryName = blockList[len(blockList)-1]

    print("Deleting entry '"+entryName+"' in file: "+file)

    start, stop = _ofDictFindBlockEntryStartStop(
        file,
        blockList,
        searchValues=searchValues
    )

    if any([s is None for s in [start,stop]]):
        print("\tBlock entry '"+entryName+"' not found.  Nothing to delete.")
        return None

    #- Correct start and stop locations to delete entry including names and
    #   brackets or parenthesis
    start -= 2
    stop+=1

    file = os.path.join(os.getcwd(), file)

    if start>= stop:
        print("\tNo lines to delete.")
    else:
        print("\tDeleting values for block '"+entryName+"', between lines "\
              +str(start+1)+" and "+str(stop)+".")
        #- delete lines in file
        with open(file, 'r+') as new:
            lines = new.readlines()
            del lines[start:stop]
            new.seek(0)
            new.truncate()
            new.writelines(lines)



    return start # return the line where the block ends, so values can be
                 # written here with _ofDictAppendBlockEntryWithLineNum
