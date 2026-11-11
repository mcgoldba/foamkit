from pathlib import Path
from typing import List, Optional, Union

from foamkit.functions._paths import listTimes


def timeDirs(
    path: Optional[Union[str, Path]] = None, processor: bool = False
) -> List[str]:
    """
    Return the names of the time directories of a case in numeric order,
    exactly as on disk (e.g. ['0', '1e-05', '0.5', '100']).  Names that are not
    times (`constant`, `nan`, `1_0`, files, hidden entries) are ignored.  Names
    with the same value (`1` and `1.0`) are all listed.

    Parameters:
        path [str or Path]:  The case directory (default: the current
            directory).
        processor [bool]:  List the times of 'processor0' instead of the
            reconstructed times.  Returns [] if there is no 'processor0'.

    Raises FoamKitError if the directory cannot be read.
    """
    directory = Path.cwd() if path is None else Path(path)
    if processor:
        directory = directory / "processor0"
        if not directory.is_dir():
            return []
    return listTimes(directory)
