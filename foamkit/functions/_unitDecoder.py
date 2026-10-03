from pint import UnitRegistry

import logging

logger = logging.getLogger('foamkit')

def _unitDecoder(dct):
    """
    Object hook function for the python 'json.load()' function.
    Reads in dimensional values as strings and converts to float value in SI units.
    Parameters
    ----------
    dct: dict
        The parsed json file as a python dictionary
    Returns
    -------
    dct: dict
        The parsed Python dictionary with converted units
    """

    # logger.setLevel(logging.DEBUG)

    ureg = UnitRegistry()
    Q_ = ureg.Quantity

    ###- Helper function 1
    def _decodeUnits(v):
        if isinstance(v, str):
            logger.debug("Found string value")
            try:
                v_ = ureg(v).to_base_units().magnitude
                logger.debug(f"Interpreted string as '{v_}'")
                return v_
            #vList = v.split(" ")
            #if len(vList) >= 2:
            #    try:
            #        mag = float(vList[0])
            #    except:
            #        #continue
            #        return v
            #    try:
            #        unit = (" ".join(vList[1:]))
            #        #log.debug("trying unit conversion on "+str(v)+"...")
            #        unit = ureg(unit)
            #    except:
            #        unit = ureg(unit)
            #        #log.debug("Failed.")
            #        #continue
            #        return v
            #    #log.debug("Success.")
            #    v = mag*unit
            #    return v.to_base_units().magnitude
            except:
                return v
        else:
            return v

    ###- Helper function 2
    #- from stackoverflow: 34615164
    def _parseOrDecode(obj):
        if isinstance(obj, dict):
            return {k:_parseOrDecode(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            logger.debug("Parsing list...")
            return [_parseOrDecode(v) for v in obj]
        else:
            logger.debug(f"Parsing value '{obj}'...")
            return _decodeUnits(obj)

    return _parseOrDecode(dct)
