"""Small path helpers shared by the `foamkit.functions` modules."""
from pathlib import Path


def latestTimeName(directory):
    """
    Return the name of the entry in `directory` with the largest numeric name
    (e.g. the latest start time in 'postProcessing/probes'), or '0' if there is
    none.
    """
    latest = 0
    for entry in Path(directory).iterdir():
        try:
            if float(entry.name) > float(latest):
                latest = entry.name
        except ValueError:
            pass
    return str(latest)


def withJsonSuffix(path):
    """Append '.json' to `path` unless it already ends with it."""
    if str(path)[-5:] != '.json':
        return Path(str(path)+'.json')
    return Path(path)
