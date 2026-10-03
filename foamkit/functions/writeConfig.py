import json
import os


def writeConfig(entry, file="config.json"):
    """
    Writes a value to the specified configuration file.  If the specified key is already defined, the value is appended.

    Parameters
    ----------

    entry : dict
        The dictionary entries to add to the config file

    file : str
        The ini file to write the data in.

    """

    if file[-5:] != ".json":
        file = file+".json"

    filepath = os.path.join(".params", file)

    config = {}

    #convert the entry to string
    #entry = {str(key): str(value) for key, value in entry.items()}

    if os.path.isdir(".params") is False:
        os.mkdir(".params")
    if os.path.isfile(filepath) is False:
        config = entry
    else:
        config = json.load(open(filepath))
        # Make sure existing key values are not overwritten
        #for key in entry:
        #    if key in config:
        #        if any(isinstance(config[key], type_) for type_
        #               in [list, dict]):
        #            config[key].append(entry[key])
        #        else:
        #            config[key] = [config[key], entry[key]]
        #    else:
        #        config.update(entry)

        # Values will be overwritten if they already exist in config
        config.update(entry)

    with open(filepath, 'w') as configfile:
        json.dump(config, configfile, indent=4)
