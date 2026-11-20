"""Time `import composapy` in fresh Python processes and save the result as import_time_<label>.json.

python measure_import.py --python C:\\dataLabsArtifacts\\python\\python311\\Scripts\\python.exe --label py311

What it records
    - median (and every individual) wall-clock time of N runs of `python -c "import composapy"`, each in a new
      process, so every run pays the full import cost (this is the headline number)
    - the text of one `python -X importtime -c "import composapy"` run, for the per-module breakdown. That run is
      separate because -X importtime slows the import down, so it is never part of the timings.

Run it on an otherwise idle machine, with nothing else using the CPU, and use the same machine for the baseline
and for the candidate so the two are comparable.
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone


def run(cmd):
    start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True)
    return time.perf_counter() - start, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--python",
        required=True,
        help="the interpreter to measure (a shared DataLab environment's python.exe)",
    )
    parser.add_argument(
        "--label", required=True, help="used in the output file name, e.g. py311"
    )
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument(
        "--statement",
        default="import composapy",
        help="what to time; leave as is except to test this script",
    )
    parser.add_argument("--out-dir", default=".")
    args = parser.parse_args()

    if "composapy" in args.statement and not os.environ.get("DATALAB_DLL_DIR"):
        sys.exit(
            "DATALAB_DLL_DIR is not set in this terminal (see how to set it for your shell), so every run would fail."
        )

    version = subprocess.run(
        [args.python, "-c", "import sys; print(sys.version.split()[0])"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    composapy_version = (
        subprocess.run(
            [
                args.python,
                "-c",
                "import importlib.metadata as m; print(m.version('composapy'))",
            ],
            capture_output=True,
            text=True,
        ).stdout.strip()
        or "not installed"
    )
    print(f"python {version} ({args.python}), composapy {composapy_version}")

    seconds = []
    for i in range(1, args.runs + 1):
        elapsed, result = run([args.python, "-c", args.statement])
        if result.returncode != 0:
            sys.exit(
                f"run {i} failed (exit {result.returncode}); nothing was saved.\n{result.stderr.strip()[-1500:]}"
            )
        seconds.append(round(elapsed, 3))
        print(f"  run {i:>2}/{args.runs}: {elapsed:6.2f} s")

    _, profiled = run([args.python, "-X", "importtime", "-c", args.statement])
    if profiled.returncode != 0:
        sys.exit(
            f"the -X importtime run failed (exit {profiled.returncode}); nothing was saved.\n{profiled.stderr.strip()[-1500:]}"
        )

    record = {
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": version,
        "python_exe": args.python,
        "composapy_version": composapy_version,
        "statement": args.statement,
        "runs": args.runs,
        "median_seconds": round(statistics.median(seconds), 3),
        "min_seconds": min(seconds),
        "max_seconds": max(seconds),
        "seconds": seconds,
        "importtime": profiled.stderr,
    }
    path = os.path.join(args.out_dir, f"import_time_{args.label}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    print(
        f"median {record['median_seconds']} s  (min {record['min_seconds']}, max {record['max_seconds']})  -> {path}"
    )


if __name__ == "__main__":
    main()
