"""Continue a completed 5 ms benchmark from its native restarts (4-thread OpenMP)."""
import argparse
import os
from pathlib import Path
import re
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case", type=Path)
    p.add_argument("end_ms", nargs="+", type=int, help="Absolute run ends after 5 ms, in increasing order")
    args = p.parse_args()
    case = args.case.resolve()
    work = Path(__file__).resolve().parents[1] / "work"
    if not case.is_relative_to(work) or not 5 < args.end_ms[0] or sorted(set(args.end_ms)) != args.end_ms:
        p.error("Expected a work/ case and increasing times above 5 ms")
    solver = work / "OpenCourant"
    env = os.environ.copy()
    env.update(OPENRADIOSS_PATH=str(solver), RAD_CFG_PATH=str(solver / "hm_cfg_files"), OMP_NUM_THREADS="4")
    libs = [solver / "extlib/hm_reader/linux64", solver / "extlib/h3d/lib/linux64"]
    env["LD_LIBRARY_PATH"] = ":".join(map(str, libs)) + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    template = (case / "combine_0001.rad").read_text()
    if not re.search(r"^/RUN/combine/1/\s*\n0\.005\s*$", template, re.M):
        raise ValueError("Expected the 5 ms benchmark Engine deck")
    for i, end in enumerate(args.end_ms, 2):
        prev = case / f"combine_{i-1:04d}"
        if "NORMAL TERMINATION" not in prev.with_suffix(".out").read_text() or not (case / (prev.name + "_0001.rst")).is_file():
            raise ValueError(f"No completed restart for segment {i-1}")
        deck = case / f"combine_{i:04d}.rad"
        cfg = re.sub(r"^/RUN/combine/1/\n0\.005$", f"/RUN/combine/{i}/\n{end/1000:.6f}", template, count=1, flags=re.M)
        if deck.exists() and deck.read_text() != cfg:
            raise ValueError(f"Existing {deck} has a different configuration.")
        if deck.with_suffix(".out").exists():
            if "NORMAL TERMINATION" in deck.with_suffix(".out").read_text():
                continue
            raise ValueError(f"Inspect the incomplete segment before retrying {deck}")
        deck.write_text(cfg)
        print(f"Continuing segment {i} to {end} ms", flush=True)
        with (case / f"engine-{i:04d}.log").open("x") as log:
            subprocess.run([solver / "exec/engine_linux64_gf", "-i", deck.name, "-nt", "4"],
                           cwd=case, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        if "NORMAL TERMINATION" not in deck.with_suffix(".out").read_text():
            raise ValueError(f"Engine did not complete segment {i}")


if __name__ == "__main__":
    main()
