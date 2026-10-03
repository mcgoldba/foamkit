def _interpretUnitsAndConvert(dct):
    """
    Reads string formatted dimensional values and converts to a float in OpenFOAM standard units


    Parameters
    ----------

    dct: dict
        (Potentially nested) Dictionary of values to be parsed

    Returns
    -------

    convetedDict: dict
        Equivalent dictionary with dimensioned values converted to "float" types

    """
    pass


    try:
        ureg
    except NameError:
        ureg=UnitRegistry()


    convertedDict = {}

    #- Parse nested dictionaries (from https://stackoverflow.com/questions/10756427/loop-through-all-nested-dictionary-values)
    def loopContents(v):
        if any([type(v) is t for t in [dict, list, tuple]]):
            iterateIterable(obj, v, k=None)
        elif type(v) is str:
            #- Process 'str' values
            if len(v.split(" "))>=2:
                vList = v.split(" ")
                try:
                    mag = float(vList)
                except ValueError:
                    pass
                try:
                    unit = " ".join(vList[1:])
                    ureg[unit]
                except UndefinedUnitError:
                    pass
                v = mag*ureg[unit]



    def iterateIterable(obj):
        if type(obj) is dict:
            for k, v in obj.items():
                loopContents(obj, v, k)
        elif type(obj) is list or type(obj) is tuple:
            for v in obj:
                loopContents(obj, v)
        else:
            log.error('Invalid "obj" provided')
            sys.exit()

    loopContents(dct)

    return convertedDict
