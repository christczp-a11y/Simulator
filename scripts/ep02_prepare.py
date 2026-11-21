"""Prepare an ignored run folder from the unchanged CCSA v1l coarse ZIP."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZipFile

DIGEST = "4f2b837ba0c85c2ef123a75201ac341c5de6763fb2768b818d41ec4c027af921aabea83f0069bfa8b457a56c44c34ed0"
PREFIX = "2010-toyota-yaris-coarse-v1l"
FILES = ["combine.key", "set-yaris-coarse-v1l.key", "yaris-coarse-v1l.key", "wall.key"]


def replace_line(lines, old, new):
    if lines.count(old) != 1:
        raise ValueError(f"Expected one exact card line: {old!r}")
    lines[lines.index(old)] = new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("--speed", type=int, choices=[40, 56, 90, 100, 120], required=True)
    parser.add_argument("--ms", type=int, choices=range(1, 251), metavar="1..250", required=True)
    args = parser.parse_args()
    if hashlib.sha384(args.archive.read_bytes()).hexdigest() != DIGEST:
        parser.error("Archive SHA-384 differs from the CCSA v1l release.")
    if not args.run.resolve().is_relative_to(Path(__file__).resolve().parents[1] / "work"):
        parser.error("Run directory must be inside work/.")
    args.run.mkdir(parents=True, exist_ok=False)
    with ZipFile(args.archive) as archive:
        for name in FILES:
            content = archive.read(f"{PREFIX}/{name}")
            if name == "combine.key":
                lines = content.decode("ascii").splitlines()
                replace_line(lines, "*KEYWORD", "*KEYWORD\n*CONTROL_UNITS\nmm        sec       mtrc_ton  K")
                replace_line(lines, "R VEL_1     15646.40", f"R VEL_1   {args.speed / 3.6 * 1000:10.3f}")
                replace_line(lines, "  0.200000", f"{args.ms / 1000:10.6f}")
                for keyword, interval in [("*DATABASE_BINARY_D3PLOT", 0.0005), ("*DATABASE_BINARY_D3THDT", 0.0001)]:
                    lines[lines.index(keyword) + 1] = f"{interval:10.6f}"
                content = ("\n".join(lines) + "\n").encode("ascii")
            elif name == "set-yaris-coarse-v1l.key":
                lines = content.decode("latin1").splitlines()
                i = lines.index("   5000554Left B-pillar Lower")
                # Nearest shell node on the right B-pillar inner to the reflected
                # left accelerometer position (target -2237.92,-662.58,526.537 mm).
                lines.insert(i + 1, "   2274453Right lower B-pillar inner structural node")
                content = ("\n".join(lines) + "\n").encode("latin1")
            (args.run / name).write_bytes(content)


if __name__ == "__main__":
    main()
