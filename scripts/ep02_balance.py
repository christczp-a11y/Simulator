"""Audit the full-width wall run against OpenCourant's independent global totals."""
import argparse
import csv
import json
from pathlib import Path
import re

import numpy as np


# This converter labels global channel 23 "NO NAME". Its position and formula
# are specified in hist2.F at the solver revision used for this project.
GLOBAL = ["time", "INTERNAL ENERGY", "KINETIC ENERGY", "X-MOMENTUM", "Y-MOMENTUM",
          "Z-MOMENTUM", "MASS", "TIME STEP", "ROTATION ENERGY", "EXTERNAL WORK",
          "SPRING ENERGY", "CONTACT ENERGY", "HOURGLASS ENERGY", "ELASTIC CONTACT ENERGY",
          "FRICTIONAL CONTACT ENERGY", "DAMPING CONTACT ENERGY", "PLASTIC WORK",
          "ADDED MASS", "PERCENTAGE ADDED MASS", "INLET MASS", "OUTLET MASS",
          "INLET ENERGY", "OUTLET ENERGY", "NO NAME"]


def read_history(case):
    samples = []
    log_errors = []
    for segment, path in enumerate(sorted(case.glob("combineT[0-9][0-9].csv")), 1):
        if path.stem != f"combineT{segment:02d}":
            raise ValueError(f"Missing segment before {path.name}")
        log = (case / f"combine_{segment:04d}.out").read_text()
        if "NORMAL TERMINATION" not in log:
            raise ValueError(f"Unfinished segment {segment}")
        errors = re.findall(r"^\s*\d+\s+[-.+\dE]+\s+[-.+\dE]+\s+\S+\s+\d+\s+([-+.\d]+)%", log, re.M)
        if not errors:
            raise ValueError(f"No cycle diagnostics in segment {segment}")
        log_errors.extend(map(float, errors))
        with path.open(newline="") as stream:
            reader = csv.reader(stream)
            headers = [" ".join(x.split()) for x in next(reader)]
            if headers[:len(GLOBAL)] != GLOBAL:
                raise ValueError("Unknown global channel ordering")
            walls = []
            for wall in range(10000001, 10000007):
                for component in ("FNX", "FTX"):
                    (index,) = [i for i, h in enumerate(headers) if h.startswith(f"TH-RWALL {wall} ") and h.endswith(" "+component)]
                    walls.append(index)
            for row in reader:
                values = [float(row[i]) for i in [*range(len(GLOBAL)), *walls]]
                if samples and values[0] == samples[-1][0]:
                    np.testing.assert_allclose(values, samples[-1], rtol=1e-6)
                else:
                    samples.append(values)
    a = np.array(samples)
    if not len(samples) or not np.isfinite(a).all() or a[0,0] != 0 or np.any(np.diff(a[:,0]) <= 0) or np.max(np.diff(a[:,0])) > .00011:
        raise ValueError("Incomplete or non-finite 10 kHz history")
    return a, log_errors


def audit(case):
    a, printed = read_history(case)
    t = a[:,0]
    total = a[:,23]
    calculated = a[:,1]+a[:,2]+a[:,8]+a[:,11]+a[:,12]-a[:,9]+a[:,21]+a[:,22]
    # th_to_csv exports seven significant figures in these channels.
    np.testing.assert_allclose(total, calculated, rtol=2e-6, atol=1.)
    np.testing.assert_allclose(a[:,11], a[:,13:16].sum(axis=1), rtol=2e-6, atol=1.)
    drift = 100*(total/total[0]-1)
    peak = np.argmax(abs(drift))
    # Wall channels are reaction forces on the wall. Sum both tangential
    # and normal X components, including the four tyre-ground planes.
    impulse = np.sum(.5*(a[1:,24:]+a[:-1,24:])*np.diff(t)[:,None], axis=0).reshape(6,2)
    momentum = a[-1,3]-a[0,3]
    return dict(samples=len(t), last_sample_ms=t[-1]*1000,
                native_initial_kJ=total[0]/1e6, native_end_kJ=total[-1]/1e6,
                peak_abs_native_drift_pct=abs(drift[peak]), peak_simulation_ms=t[peak]*1000,
                end_native_drift_pct=drift[-1], max_channel_roundoff_J=max(abs(total-calculated))*.001,
                engine_printed_error_range_pct=[min(printed), max(printed)],
                end_contact_kJ=dict(total=a[-1,11]/1e6, elastic=a[-1,13]/1e6,
                                    friction=a[-1,14]/1e6, damping=a[-1,15]/1e6),
                end_added_mass_pct=a[-1,18],
                barrier_x_impulse_Ns=impulse[:2].sum(), ground_x_impulse_Ns=impulse[2:].sum(),
                delta_global_x_momentum_Ns=momentum, impulse_closure_Ns=momentum+impulse.sum())


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    result = audit(args.case)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
