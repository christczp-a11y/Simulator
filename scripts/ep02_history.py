"""Extract the EP02 channels from the official th_to_csv export (keep its _TITLES file)."""
import argparse
import csv
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt


def extract(path):
    with path.open(newline="") as f:
        reader = csv.reader(f)
        headers = [" ".join(h.split()) for h in next(reader)]
        columns = {}
        for short, name in [
            ("time_s", "time"), ("internal_Nmm", "INTERNAL ENERGY"),
            ("kinetic_Nmm", "KINETIC ENERGY"), ("rotation_Nmm", "ROTATION ENERGY"),
            ("contact_Nmm", "CONTACT ENERGY"), ("hourglass_Nmm", "HOURGLASS ENERGY"),
            ("external_Nmm", "EXTERNAL WORK"), ("mass_t", "MASS"),
        ]:
            columns[short] = headers.index(name)
        for label, family, item, channels in [
            ("seat", "DATABASE_HISTORY_NODE", 5000513, ("AX", "AY", "AZ", "VX")),
            ("cg", "DATABASE_HISTORY_NODE", 5000404, ("VX", "VY", "VZ")),
            ("rear_left", "DATABASE_HISTORY_NODE", 5000390, ("AX",)),
            ("rear_right", "DATABASE_HISTORY_NODE", 5000398, ("AX",)),
            ("left", "DATABASE_HISTORY_NODE", 5000554, ("AX",)),
            ("right", "DATABASE_HISTORY_NODE", 2274453, ("AX",)),
            ("wall1", "TH-RWALL", 10000001, ("FNX",)),
            ("wall2", "TH-RWALL", 10000002, ("FNX",)),
        ]:
            for channel in channels:
                matches = [i for i, h in enumerate(headers) if h.startswith(f"{family} {item} ") and h.endswith(f" {channel}")]
                if len(matches) != 1:
                    raise ValueError(f"Expected exactly one {label}/{channel}. Convert with the original T01_TITLES beside the T01.")
                columns[f"{label}_{channel}"] = matches[0]
        # In QEPH shells the per-part HE also includes numerical damping.
        # The global HOURGLASS ENERGY excludes that damping. Keep both.
        he=[i for i,h in enumerate(headers) if h.endswith(" HE") and i>0
            and headers[i-1]==h[:-3]+" MASS"]
        samples=[]
        for row in reader:
            values=[float(row[i]) for i in columns.values()]
            if he:
                values.append(sum(float(row[i]) for i in he))
            samples.append(values)
        data=np.asarray(samples)
    if data.ndim != 2 or len(data) < 2 or not np.all(np.isfinite(data)):
        raise ValueError("Missing or non-finite time history.")
    fields=list(columns)+(["part_HE_with_damping_Nmm"] if he else [])
    return dict(zip(fields, data.T))


def derived(d, complete):
    t = d["time_s"]
    if t[0] != 0 or np.any(np.diff(t) <= 0):
        raise ValueError("History must start at zero and progress monotonically.")
    wall = np.abs(d["wall1_FNX"]) + np.abs(d["wall2_FNX"])
    hits = np.flatnonzero(wall > 0)
    d["contact_time_s"] = t - t[hits[0]] if len(hits) else np.full_like(t, np.nan)
    energy = sum(d[k] for k in ("internal_Nmm", "kinetic_Nmm", "rotation_Nmm", "contact_Nmm", "hourglass_Nmm"))
    d["energy_residual_pct"] = 100 * (energy - energy[0] - (d["external_Nmm"] - d["external_Nmm"][0])) / energy[0]
    d["cg_speed_kmh"] = d["cg_VX"] * 0.0036
    d["cg_resultant_kmh"] = np.sqrt(sum(d["cg_"+v]**2 for v in ("VX","VY","VZ"))) * 0.0036
    if complete:
        if not len(hits) or t[-1] - t[hits[0]] < 0.1:
            raise ValueError("A short benchmark cannot validate the crash pulse.")
        # Uniform grid for J211 CFC60's forward/backward two-pole Butterworth.
        # Each pass uses the compensated design frequency (2.0775 * CFC).
        grid = np.linspace(t[0], t[-1], int(round((t[-1] - t[0]) / np.median(np.diff(t)))) + 1)
        fs = 1 / (grid[1] - grid[0])
        if np.max(np.diff(t)) > 0.00011 or fs < 9950:
            raise ValueError("Node output too sparse for the 10 kHz analysis.")
        sos = butter(2, 2.0775 * 60, fs=fs, output="sos")
        for loc in ("seat", "left", "right", "rear_left", "rear_right"):
            a = np.interp(grid, t, d[f"{loc}_AX"]) / -9806.65
            # Constant endpoint extension absorbs the filter transient without
            # introducing a mirrored impact before the start of the simulation.
            y = sosfiltfilt(sos, a, padtype="constant", padlen=int(round(0.050 * fs)))
            d[f"{loc}_decel_cfc60_g"] = np.interp(t, grid, y)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--full-pulse", action="store_true")
    args = p.parse_args()
    history = extract(args.csv)
    derived(history, args.full_pulse)
    with args.output.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(history)
        w.writerows(zip(*history.values()))
