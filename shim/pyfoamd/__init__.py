"""
Compatibility shim: ``pyfoamd`` has been renamed to ``foamkit``.

This package only forwards ``import pyfoamd`` (and its ``functions``, ``types``
and ``commandline`` submodules) to :mod:`foamkit`, so existing scripts keep
working while you migrate.  Replace ``pyfoamd`` with ``foamkit`` in your imports
and ``pip install foamkit`` going forward.
"""
import importlib
import sys
import warnings

import foamkit

warnings.warn(
    "The 'pyfoamd' package has been renamed to 'foamkit'. "
    "Please `pip install foamkit` and `import foamkit`; this compatibility "
    "package will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

#- Old public name of the config helper
foamkit.getPyFoamdConfig = foamkit.getFoamKitConfig

#- Make `import pyfoamd`, `import pyfoamd.functions as pf`, etc. resolve to the
#- foamkit modules themselves (same objects, so isinstance checks still work).
for _sub in ("functions", "types", "commandline"):
    sys.modules[f"pyfoamd.{_sub}"] = importlib.import_module(f"foamkit.{_sub}")
sys.modules["pyfoamd"] = foamkit
