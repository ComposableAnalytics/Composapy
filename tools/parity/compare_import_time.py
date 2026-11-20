"""Compare the candidate's `import composapy` time with the baseline's, per Python version.

The baselines are tests/baseline/import_time_<label>.json (made with tools/measure_import.py in an environment with the
baseline wheel). The candidate's are made the same way, with the label <label>-candidate, into tools/parity/results:

    python measure_import.py --python <python.exe> --label py311-candidate --out-dir tools/parity/results
    python compare_import_time.py py38 py311 py313

For each label it prints both medians, and checks that the candidate is faster and that the `-X importtime` run lists no
papermill, clr, pythonnet, or clr_loader. Exits 1 when any label fails either check.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FORBIDDEN = ("papermill", "clr", "pythonnet", "clr_loader")
IMPORT_LINE = re.compile(r"^import time:\s+\d+ \|\s+\d+ \|\s*(\S+)")


def imported_modules(importtime_text):
    """The module names in the output of `python -X importtime`, one per import line."""
    return [
        m.group(1)
        for m in (IMPORT_LINE.match(line) for line in importtime_text.splitlines())
        if m
    ]


def forbidden_imports(importtime_text):
    return sorted(
        {
            name
            for name in imported_modules(importtime_text)
            if name.split(".")[0] in FORBIDDEN
        }
    )


def compare(baseline, candidate):
    return {
        "baseline_median": baseline["median_seconds"],
        "candidate_median": candidate["median_seconds"],
        "faster": candidate["median_seconds"] < baseline["median_seconds"],
        "forbidden": forbidden_imports(candidate.get("importtime", "")),
        "candidate_version": candidate.get("composapy_version"),
        "python": candidate.get("python"),
        "runs": candidate.get("runs"),
    }


def main(argv):
    labels = argv[1:] or ["py38", "py311", "py313"]
    failed = False
    for label in labels:
        baseline_file = ROOT / "tests" / "baseline" / f"import_time_{label}.json"
        candidate_file = (
            ROOT
            / "tools"
            / "parity"
            / "results"
            / f"import_time_{label}-candidate.json"
        )
        if not candidate_file.exists():
            print(f"{label}: no candidate measurement at {candidate_file}")
            failed = True
            continue
        result = compare(
            json.loads(baseline_file.read_text(encoding="utf-8")),
            json.loads(candidate_file.read_text(encoding="utf-8")),
        )
        ratio = (
            result["baseline_median"] / result["candidate_median"]
            if result["candidate_median"]
            else float("inf")
        )
        print(
            f"{label}: baseline {result['baseline_median']:.3f} s, candidate {result['candidate_median']:.3f} s "
            f"({ratio:.0f}x faster, composapy {result['candidate_version']}, Python {result['python']}, {result['runs']} runs)"
            + ("" if result["faster"] else "  NOT FASTER")
            + (
                f"  FORBIDDEN IMPORTS: {', '.join(result['forbidden'])}"
                if result["forbidden"]
                else ""
            )
        )
        failed = failed or not result["faster"] or bool(result["forbidden"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
