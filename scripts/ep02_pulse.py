"""Join restart histories and compare a completed 56 km/h pulse with Locey et al."""
import argparse
import csv
import json
import os
from pathlib import Path
import re
import subprocess

import numpy as np
from scipy.signal import butter, sosfiltfilt
from ep02_history import extract, derived


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--until", type=int, required=True, help="Last completed engine segment")
    args = parser.parse_args()
    case = args.case.resolve()
    converter = Path(__file__).resolve().parents[1] / "work/OpenCourant/exec/th_to_csv_linux64_gf"
    chunks = []
    for i in range(1, args.until + 1):
        log = (case / f"combine_{i:04d}.out").read_text()
        if "NORMAL TERMINATION" not in log:
            raise ValueError(f"Segment {i} incomplete")
        hist = f"combineT{i:02d}"
        subprocess.run([converter, hist], check=True, cwd=case, stdout=subprocess.DEVNULL)
        chunks.append(extract(case / (hist + ".csv")))
    d = {k: np.concatenate([c[k] for c in chunks]) for k in chunks[0]}
    # A restart can repeat the boundary sample. Drop it only if channels agree.
    dup = np.flatnonzero(np.diff(d["time_s"]) == 0)
    for k in d:
        if len(dup) and not np.allclose(d[k][dup], d[k][dup+1]):
            raise ValueError(f"Restart boundary disagrees for {k}")
        d[k] = np.delete(d[k], dup+1)
    t = d["time_s"]
    if np.max(np.diff(t)) > .00011:
        raise ValueError("Gap in time history")
    derived(d, True)
    tc = d["contact_time_s"]
    g = d["seat_decel_cfc60_g"]
    peak = np.flatnonzero(tc >= 0)[np.argmax(g[tc >= 0])]
    # Locey uses a CFC18 curve and a backwards search from the end, using
    # the mean over the first 200 ms. If the simulation stops earlier, only
    # a measured-window estimate can be reported.
    grid = np.linspace(0, t[-1], round(t[-1] / .0001) + 1)
    fs = 1 / (grid[1] - grid[0])
    g18 = sosfiltfilt(butter(2, 2.0775 * 18, fs=fs, output="sos"),
                      np.interp(grid, t, -d["seat_AX"]/9806.65), padtype="constant", padlen=round(fs*.05))
    rel = grid + tc[0]
    avg = np.mean(g18[(rel >= 0) & (rel <= .2)])
    last = np.flatnonzero((rel >= 0) & (g18 >= avg))[-1]
    threshold = .05 * g18.max()
    ends = np.flatnonzero((np.arange(len(grid)) > last) & (g18 <= threshold))
    duration = None
    if ends.size:
        i = ends[0]
        duration = float(1000*(rel[i-1] + (rel[i]-rel[i-1])*(g18[i-1]-threshold)/(g18[i-1]-g18[i])))
    valid_ie = d["internal_Nmm"] > 0
    ratio = 100*d["hourglass_Nmm"][valid_ie]/d["internal_Nmm"][valid_ie]
    stop = np.flatnonzero((tc >= 0) & (d["cg_VX"] <= 0))
    summary = dict(peak_g=float(g[peak]), peak_time_ms=float(tc[peak]*1000),
                   seat_pulse_end_ms=duration, duration_mean_window_ms=min(200, float(tc[-1]*1000)),
                   last_time_ms=float(t[-1]*1000), end_speed_kmh=float(d["cg_speed_kmh"][-1]),
                   cg_first_zero_ms=float(tc[stop[0]]*1000) if stop.size else None,
                   max_energy_residual_pct=float(np.max(np.abs(d["energy_residual_pct"]))),
                   max_hourglass_internal_pct=float(np.max(np.abs(ratio))),
                   sample_count=len(t), max_sample_gap_us=float(np.diff(t).max()*1e6))
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    with (output/"56kmh-history.csv").open("w", newline="") as f:
        w=csv.writer(f, lineterminator="\n"); w.writerow(d); w.writerows(zip(*d.values()))
    (output/"56kmh-metrics.json").write_text(json.dumps(summary, indent=2, allow_nan=False)+"\n")
    os.environ.setdefault("MPLCONFIGDIR",str(case / "mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(8,6.2), sharex=True, layout="constrained")
    ax[0].plot(tc*1000, g, label="Driver seat crossmember", color="#192f49", lw=2)
    for loc,col in [("left","#549a8a"),("right","#b87343")]:
        ax[0].plot(tc*1000,d[f"{loc}_decel_cfc60_g"],label=loc.title()+" lower B-pillar", alpha=.8,lw=.9,color=col)
    ax[0].scatter([47.5],[43.5],color="#8f293d",marker="x",label="Small-car fleet mean")
    ax[0].set(ylabel="Longitudinal deceleration (g)", title="56 km/h full-width rigid barrier  •  CFC 60")
    ax[0].legend(fontsize=8,frameon=False)
    ax[1].plot(tc*1000,d["energy_residual_pct"],label="Energy balance residual / initial energy")
    ax[1].plot(tc[valid_ie]*1000,ratio,label="Hourglass / internal energy")
    ax[1].set(xlabel="Time since first recorded barrier force (ms)",ylabel="Percent")
    ax[1].legend(fontsize=8,frameon=False)
    for a in ax:
        a.grid(alpha=.2);a.spines[["right","top"]].set_visible(False)
    fig.savefig(output/"56kmh-pulse.png",dpi=170)
    print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    main()
