"""Check t=0 solver velocities against the v1l input, for every connected vehicle node."""
import argparse
from itertools import islice
from pathlib import Path
import re

import numpy as np


def check(mesh, vtk, setup, speed_kmh):
    # Node numbering in VTK differs from the original LS-DYNA array order.
    with vtk.open() as src:
        for line in src:
            if line.startswith("TIME "):
                if float(next(src)) != 0:
                    raise ValueError("Expected the initial frame at t=0.")
            if line.startswith("POINTS "):
                n = int(line.split()[1])
            if line.startswith("SCALARS NODE_ID "):
                next(src)
                ids = np.loadtxt(islice(src, n), dtype=np.int64)
            if line.startswith("VECTORS Velocity "):
                v = np.loadtxt(islice(src, n))
                break
        else:
            raise ValueError("No velocity vector in the supplied animation.")
    with np.load(mesh) as archive:
        d = dict(archive)
    order = np.argsort(ids)
    idx = order[np.searchsorted(ids[order], d["node_id"])]
    if not np.array_equal(ids[idx], d["node_id"]):
        raise ValueError("Solver output is missing vehicle nodes.")
    speed = speed_kmh / 3.6 * 1000
    axes = {"front rotating parts": (-777.06, 303.154), "rear rotating parts": (-3315.69, 303.236)}
    groups = re.findall(r"^\*SET_PART_LIST_TITLE\ninitial velocity: (.+?)\n([^*]+)", setup.read_text(), re.M)
    covered = set()
    largest = 0.0
    for group, block in groups:
        lines = [line for line in block.splitlines() if line and not line.startswith("$")]
        parts = list(map(int, " ".join(lines[1:]).split()))
        covered.update(parts)
        for kind in ("shell", "solid", "beam"):
            nodes = np.unique(d[kind + "_n"][np.isin(d[kind + "_pid"], parts)])
            if not len(nodes):
                continue
            expected = np.zeros((len(nodes), 3))
            expected[:, 0] = speed
            if group in axes:
                x, z = axes[group]
                expected[:, 0] += (d["xyz"][nodes, 2] - z) * speed / 303
                expected[:, 2] = -(d["xyz"][nodes, 0] - x) * speed / 303
            err = np.linalg.norm(v[idx[nodes]] - expected, axis=1)
            largest = max(largest, err.max())
            print(f"{group:20s} {kind:5s} {len(nodes):6d} nodes, max error {err.max():.4f} mm/s")
    if not set(d["part_id"]).issubset(covered) or largest > 0.2:
        raise ValueError("Initial condition differs from the original vehicle prescription.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mesh", type=Path)
    p.add_argument("initial_vtk", type=Path)
    p.add_argument("setup", type=Path)
    p.add_argument("--speed", type=int, required=True)
    args = p.parse_args()
    check(args.mesh, args.initial_vtk, args.setup, args.speed)
