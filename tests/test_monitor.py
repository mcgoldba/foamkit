"""Probe and function object monitors read from 'postProcessing'."""
import threading

import pytest

import foamkit.functions as pf
import foamkit.types as pt
from conftest import assert_golden


def test_probe_scalar(case):
    probe = pf.getProbe("p", workingDir=case)
    assert probe.field == "p"
    assert [str(v) for v in probe.locations] == ["(0.0254 0.0253 0.0)", "(0.1 0.0 0.0)"]
    assert probe.nSamples == 40
    assert_golden("monitor/probe_p.csv", probe.data.to_csv())


def test_probe_vector_columns(case):
    probe = pf.getProbe("U", workingDir=case)
    assert list(probe.data.columns) == [
        "Probe 0 X", "Probe 0 Y", "Probe 0 Z", "Probe 1 X", "Probe 1 Y", "Probe 1 Z"]
    assert_golden("monitor/probe_U.csv", probe.data.to_csv())


def test_function_object_monitor(case):
    mon = pf.getMonitor("residuals", workingDir=case)
    assert mon._name == "residuals"
    assert_golden("monitor/residuals.csv", mon.data.to_csv())


def test_monitor_explicit_log_path(case):
    path = case / "postProcessing" / "residuals" / "0" / "residuals.dat"
    assert pf.getMonitor(logPath=path).nSamples == 40


def _append(path, rows, newline=True):
    with open(path, "a") as f:
        f.write("\n".join(rows) + ("\n" if newline else ""))


def _update(monitor, timeout=10):
    """Run `update()` with a timeout (it used to loop forever)."""
    t = threading.Thread(target=monitor.update, daemon=True)
    t.start()
    t.join(timeout)
    assert not t.is_alive(), "update() did not return"


def test_update_appends_only_new_rows(case):
    path = case / "postProcessing" / "residuals" / "0" / "residuals.dat"
    mon = pf.getMonitor("residuals", workingDir=case)
    before = mon.data.copy()

    _append(path, ["41\t0.5\t0.05\t1e-07", "42\t0.6\t0.06\t1e-08"])
    _update(mon)

    assert mon.nSamples == 42
    assert list(mon.data.index[-2:]) == [41.0, 42.0]
    assert mon.data.iloc[:40].equals(before)

    _update(mon)    # nothing new
    assert mon.nSamples == 42


def test_update_waits_for_partially_written_line(case):
    path = case / "postProcessing" / "probes" / "0" / "p"
    probe = pf.getProbe("p", workingDir=case)

    _append(path, ["41            0.5"], newline=False)   # solver mid-write
    _update(probe)
    assert probe.nSamples == 40

    _append(path, ["            -0.5"])                   # line completed
    _update(probe)
    assert probe.nSamples == 41
    assert list(probe.data.iloc[-1]) == [0.5, -0.5]


def test_update_with_few_data_rows_does_not_hang(case):
    """Fewer data rows than header lines used to loop forever."""
    path = case / "postProcessing" / "probes" / "0" / "p"
    lines = path.read_text().splitlines(keepends=True)
    path.write_text("".join(lines[:5]))         # 4 header lines + 1 row
    probe = pf.getProbe("p", workingDir=case)
    _update(probe)
    assert probe.nSamples == 1


def test_large_monitor_file(case):
    path = case / "postProcessing" / "residuals" / "0" / "residuals.dat"
    with open(path, "w") as f:
        f.write("# Solver performance\n# Time        \tUx_initial\tUy_initial\tp_initial\n")
        for t in range(1, 20001):
            f.write(f"{t}\t{t * 1e-3}\t{t * 2e-3}\t{1e-3 / t}\n")
    mon = pf.getMonitor("residuals", workingDir=case)
    assert mon.nSamples == 20000
    assert mon.data.iloc[-1, 0] == pytest.approx(20.0)
