"""Cache completed animation outputs while the explicit solver runs."""
import argparse
from pathlib import Path
import re
import time

from ep02_anim_cache import cache


def completed_animations(case, last_segment):
    index = 1
    while True:
        logs = [case / "engine.log"] + sorted(case.glob("engine-*.log"))
        texts = [p.read_text(errors="replace") for p in logs]
        written = {int(n) for text in texts for n in re.findall(r"ANIMATION FILE: combineA(\d+) WRITTEN", text)}
        while index in written:
            yield case / f"combineA{index:03d}"
            index += 1
        if any("ERROR TERMINATION" in text for text in texts):
            raise RuntimeError("Solver stopped with an error; inspect the run.")
        final = case / f"engine-{last_segment:04d}.log"
        if final in logs and "NORMAL TERMINATION" in texts[logs.index(final)]:
            if written and max(written) >= index:
                raise ValueError(f"Missing animation {index}")
            return
        time.sleep(30)


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("case",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--last-segment",type=int,required=True)
    args=p.parse_args()
    converter=Path(__file__).resolve().parents[1]/"work/OpenCourant/exec/anim_to_vtk_linux64_gf"
    cache(converter,completed_animations(args.case,args.last_segment),args.output,resume=True)
