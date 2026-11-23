"""Convert one OpenCourant A-file at a time via official anim_to_vtk and cache NPZ frames.

Stores the solver coordinates (mm) directly; adding Displacement again would
double the deformation. Element/part IDs, node IDs, and connectivity must
match throughout a run. Blender can consume frames out of core.
"""
import argparse
import hashlib
import fcntl
from pathlib import Path
import re
import subprocess
import tempfile

import numpy as np
from vtk_seq import faces


def numbers(data, pattern, dtype, size):
    match = re.search(pattern, data, re.M)
    if not match:
        raise ValueError(f"Missing VTK field {pattern!r}")
    # The converter emits one tuple per line. The next keyword begins with
    # a letter; scientific notation and signed values remain inside the block.
    end = re.compile(rb"^[A-Za-z]", re.M).search(data, match.end())
    a = np.fromstring(data[match.end():end.start() if end else len(data)], sep=" ", dtype=dtype)
    if len(a) != size:
        raise ValueError(f"Wrong field length for {pattern!r}: {len(a)} vs {size}")
    return a


def scalar(data, name, dtype, size):
    return numbers(data, rb"^SCALARS " + name + rb" \w+ 1\r?\nLOOKUP_TABLE default\r?\n", dtype, size)


def convert(data):
    n = int(re.search(rb"^POINTS (\d+) float", data, re.M)[1])
    count, total = map(int, re.search(rb"^CELLS (\d+) (\d+)", data, re.M).groups())
    xyz = numbers(data, rb"^POINTS \d+ float\r?\n", np.float32, n * 3).reshape(n, 3)
    t = float(re.search(rb"^TIME 1 1 double\s+(\S+)", data, re.M)[1])
    flat = numbers(data, rb"^CELLS \d+ \d+\r?\n", np.int32, total)
    types = numbers(data, rb"^CELL_TYPES \d+\r?\n", np.int32, count)
    top = dict(node_id=scalar(data, b"NODE_ID", np.int32, n),
               elem_id=scalar(data, b"ELEMENT_ID", np.int32, count),
               part_id=scalar(data, b"PART_ID", np.int32, count), cells_flat=flat, cell_types=types)
    active = scalar(data, b"EROSION_STATUS", np.int32, count)
    if not np.isin(active, [0, 1]).all() or not np.isfinite(xyz).all():
        raise ValueError("Invalid erosion status or non-finite positions.")
    return top, dict(time_s=t, xyz=xyz, active=active.astype(bool))


def cache(converter, animations, output, resume=False):
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".writer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        build_cache(converter, animations, output, resume)


def write_arrays(path, **arrays):
    temporary = path.with_suffix(".part")
    with temporary.open("wb") as f:
        np.savez_compressed(f, **arrays)
    temporary.replace(path)


def build_cache(converter, animations, output, resume):
    if not resume and any(p.name != ".writer.lock" for p in output.iterdir()):
        raise ValueError("Use an empty output directory or explicitly resume.")
    times, fingerprint = [], None
    if resume and (output / "mesh.npz").is_file():
        with np.load(output / "mesh.npz") as mesh:
            fingerprint = bytes(mesh["fingerprint"])
    for index, filename in enumerate(animations):
        packed = output / f"frame-{index:04d}.npz"
        with filename.open("rb") as stream:
            source_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if resume and packed.exists():
            with np.load(packed) as frame:
                if fingerprint is None or str(frame["source_hash"]) != source_hash:
                    raise ValueError(f"Cached frame does not match {filename}")
                times.append(float(frame["time_s"]))
            continue
        with tempfile.TemporaryFile(dir=output) as vtk:
            subprocess.run([str(converter.resolve()), str(filename.resolve())], stdout=vtk, check=True)
            vtk.seek(0)
            top, frame = convert(vtk.read())
        digest = hashlib.sha256()
        for array in top.values():
            digest.update(array)
        if index == 0:
            fingerprint = digest.digest()
            quad, tri, qi, ti = faces(top)
            write_arrays(output / "mesh.npz", **top, fingerprint=np.frombuffer(fingerprint, dtype=np.uint8), quad=quad, tri=tri, quad_cell=qi, tri_cell=ti)
        if digest.digest() != fingerprint:
            raise ValueError(f"Connectivity or IDs changed at {filename.name}")
        t = frame["time_s"]
        if times and t <= times[-1]:
            raise ValueError(f"Non-increasing solver time at {filename.name}")
        times.append(t)
        write_arrays(packed, **frame, source_hash=source_hash)
        with (output / "times.part").open("wb") as f:
            np.save(f, times)
        (output / "times.part").replace(output / "times.npy")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("converter", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("animations", nargs="+", type=Path)
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()
    cache(args.converter, args.animations, args.output, args.resume)
