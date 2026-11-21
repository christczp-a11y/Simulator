"""Express the CCSA v1l initial velocity on imported MAT_RIGID primary nodes.

Run once in a fresh EP02 case, after Starter first reports the rigid body
centres, then rerun Starter before Engine. Only initial velocities are added.
"""
import argparse
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    if not args.run.resolve().is_relative_to(Path(__file__).resolve().parents[1] / "work"):
        parser.error("Expected a case under work/.")
    deck = args.run / "combine.key"
    text = deck.read_text()
    if "*INITIAL_VELOCITY_RIGID_BODY" in text:
        parser.error("Explicit rigid-body velocities are already present.")
    speed = float(re.search(r"^R VEL_1\s+(\S+)", text, re.M)[1])
    setup = (args.run / "set-yaris-coarse-v1l.key").read_text()
    groups = {}
    for name, block in re.findall(r"^\*SET_PART_LIST_TITLE\ninitial velocity: (.+?)\n([^*]+)", setup, re.M):
        data = [line for line in block.splitlines() if line and not line.startswith("$")]
        for part in " ".join(data[1:]).split():
            if 2000000 < int(part) < 3000000:
                groups[int(part)] = name
    report = (args.run / "combine_0000.out").read_text()
    centers = {rb: (float(x), float(z)) for rb, x, z in re.findall(
        r"RIGID BODY ID +(\d+)\s+PRIMARY NODE +\d+\s+NEW X,Y,Z +(\S+) +\S+ +(\S+)", report)}
    axle = {"front rotating parts": (-777.06, 303.154), "rear rotating parts": (-3315.69, 303.236)}
    cards = []
    for rb, part in re.findall(r"/RBODY \((\d+)\) +rigid_PART_(\d+)", report):
        pid = int(part)
        if pid not in groups:  # The fixed barrier has no vehicle velocity.
            continue
        if rb not in centers:
            if pid in (2000399, 2000414):  # merged into the two uprights by the source deck
                continue
            raise ValueError(f"No centre of mass for rigid part {pid}")
        vx, vz, wy = speed, 0.0, 0.0
        if groups[pid] in axle:
            x, z = centers[rb]
            x0, z0 = axle[groups[pid]]
            wy = speed / 303.0
            vx += wy * (z - z0)
            vz = -wy * (x - x0)
        cards.extend(["*INITIAL_VELOCITY_RIGID_BODY", f"{pid:10d}{vx:10.3f}{0:10d}{vz:10.4f}{0:10d}{wy:10.5f}{0:10d}"])
    if len(cards) != 40 or len(groups) != 919 or text.count("\n*END\n") != 1:
        raise ValueError("Unexpected v1l model or incomplete Starter report")
    deck.write_text(text.replace("\n*END\n", "\n" + "\n".join(cards) + "\n*END\n"))


if __name__ == "__main__":
    main()
