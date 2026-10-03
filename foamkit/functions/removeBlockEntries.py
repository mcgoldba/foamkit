def removeBlockEntries(file, blockList, searchValues=False):
    #TODO:  Merge this method with _ofDictRemoveBlockEntry() (only 2 lines are
    #  different)
    #- Removes entries in an OpenFOAM dictionary block
    #- blockList = list heiarchy to be searched
    #-   e.g.  ['geometry', 'wetwell'] removes everything within:
    #-      geometry{ wetwell{*delete_everything_here}}
    #- searchValues = switch to search within a line for block start / stop
    #-  (not yet implemented)

    print("Deleting block '"+blockList[len(blockList)-1]+"' in file: "+file)

    start, stop = _ofDictFindBlockEntryStartStop(
        file,
        blockList,
        searchValues=searchValues
    )

    file = os.path.join(os.getwd(), file)


    if start>= stop:
        print("\tNo lines to delete.")
    else:
        print("\tDeleting values for block '"+blockList[len(blockList)-1]+"', between lines "+str(start+1)+" and "+str(stop)+".")
        #- delete lines in file
        with open(file, 'r+') as new:
            lines = new.readlines()
            del lines[start:stop]
            new.seek(0)
            new.truncate()
            new.writelines(lines)



    return start # return the line where the block ends, so values can be
                 # written here with _ofDictAppendBlockEntryWithLineNum
