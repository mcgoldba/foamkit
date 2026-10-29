"""Child process for the timeout-guarded parse tests (T-040).

Run as `python probe_runner.py <specs.json>`.  `specs.json` maps a label to a case:

    {"text": "...", "name": "fileName", "limit": 4.0, "kind": "load"}      # a dict file
    (optional "cycles": read/write rounds, default 3)
    {"kind": "init", "case": "<case dir>", "limit": 6.0}                   # pf.init

The child prints `{"ready": true}` once foamkit is imported, then one flushed JSON line
per case:

    {"label": ..., "status": "ok" | "error", "stage": ..., "etype": ..., "msg": ...,
     "tree1": ..., "w1": ..., "tree2": ..., "w2": ..., "tree3": ..., "w3": ...}

The parse runs in the main thread; the PARENT (tests/test_one_line_blocks.py) is the
watchdog: it kills the child when a case takes longer than its limit and restarts it
with the remaining cases.  (An in-process thread timeout is not reliable: a regex that
backtracks forever holds the GIL.)
"""

import json
import os
import sys
import tempfile
from pathlib import Path


def summary(node):
    """A JSON-able picture of a parsed node: dicts, lists and scalar values."""
    if isinstance(node, dict):
        return {
            k: summary(v)
            for k, v in vars(node).items()
            if not k.startswith("_") and type(v).__name__ != "ofComment"
        }
    value = getattr(node, "value", node)
    if isinstance(value, (list, tuple)):
        return [summary(i) for i in value]
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return f"<{type(node).__name__}>"


def _write(path, text):
    """Write `text` with LF line endings (`Path.write_text(newline=)` needs Python 3.10)."""
    with open(path, "w", newline="\n") as f:
        f.write(text)


def _run_load(spec, out, tmp):
    import foamkit.types as fkt

    path = Path(tmp) / spec.get("name", "probeDict")
    _write(path, spec["text"])
    d = None
    for n in range(1, spec.get("cycles", 3) + 1):
        out["stage"] = f"read {n}"
        d = fkt.DictFileParser(path).readDictFile()
        out[f"tree{n}"] = summary(d)
        out["stage"] = f"write {n}"
        out[f"w{n}"] = d.toString()
        _write(path, out[f"w{n}"])


def _run_init(spec, out, tmp):
    import foamkit.functions as pf

    out["stage"] = "init"
    c = pf.init(path=spec["case"])
    out["tree1"] = summary(c.system.controlDict)


def _run(label, spec):
    out = {"label": label, "status": "ok", "stage": "start"}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            (_run_init if spec.get("kind") == "init" else _run_load)(spec, out, tmp)
    except BaseException as err:  # noqa: BLE001 - every outcome is reported
        out["status"] = "error"
        out["etype"] = type(err).__name__
        out["msg"] = str(err)
    return out


def main():
    specs = json.loads(Path(sys.argv[1]).read_text())
    # - Import first: the import is slow and must not count against a case's time limit.
    import foamkit.functions  # noqa: F401
    import foamkit.types  # noqa: F401

    stdout = sys.stdout
    sys.stdout = sys.stderr = open(os.devnull, "w")  # the parser prints errors too
    stdout.write('{"ready": true}' + "\n")
    stdout.flush()
    for label, spec in specs.items():
        stdout.write(json.dumps(_run(label, spec)) + "\n")
        stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
