import re
import sys
from pathlib import Path

REQUIREMENTS_FILE = re.compile(r"requirements(\d+)\.txt")
PIN = re.compile(
    r"[A-Za-z0-9_.\-\[\]]+\s*=="
)  # name==version, optionally followed by a marker


def write_constraints(static_dir, constraints_dir):
    constraints_path = Path(constraints_dir)
    constraints_path.mkdir(parents=True, exist_ok=True)
    for file in sorted(Path(static_dir).iterdir()):
        match = REQUIREMENTS_FILE.fullmatch(file.name)
        if not (file.is_file() and match):
            continue
        lines = [
            line.strip() for line in file.read_text(encoding="utf-8-sig").splitlines()
        ]
        pinned = [
            line
            for line in lines
            if PIN.match(line)
            and re.split(r"[\[=<>!~; ]", line)[0].lower() != "composapy"
        ]
        with open(
            constraints_path / f"py{match.group(1)}.txt",
            "w",
            encoding="utf-8",
            newline="\n",
        ) as target:
            target.write("\n".join(pinned) + "\n")


if __name__ == "__main__":
    static_dir = sys.argv[1]
    constraints_dir = sys.argv[2]

    write_constraints(static_dir, constraints_dir)
