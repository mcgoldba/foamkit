# pyfoamd has been renamed to FoamKit

**`pyfoamd` is now [`foamkit`](https://pypi.org/project/foamkit/)** — *A Pythonic interface to OpenFOAM.*

This package is a thin compatibility layer: it installs `foamkit` and forwards
`import pyfoamd` to it (with a `DeprecationWarning`) so existing scripts keep working.

To migrate:

```bash
pip uninstall pyfoamd
pip install foamkit
```

```python
import foamkit.functions as pf   # was: import pyfoamd.functions as pf
import foamkit.types as pt       # was: import pyfoamd.types as pt
```

The command line tool is unchanged (`pf`), and is also available as `foamkit`.
The user config directory `~/.pyfoamd` is still read; new settings belong in
`~/.foamkit`.

Source: <https://github.com/mcgoldba/foamkit>
