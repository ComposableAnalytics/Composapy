"""Compare the baseline's and the candidate's result files and match every difference to a classification.

    python compare_results.py [results dir]        (default: tools/parity/results)

Writes <results dir>/differences.json. A classification is an entry in tools/parity/classifications.json:

    {"script": "dataflow_run", "name": "modules_repr", "classification": "visual", "note": "..."}

"name" may be "*" for every record of the script, and "script" may be "*" for every script. An entry may also have "kind"
(only that kind of difference) and "detail_contains" (only differences whose detail note contains that text). The classification is one of
fixed, visual (permitted by R5), intentional (a Decision Log entry; the note names it), or escalated (the scope owner
decides). Exits 1 while any difference is unclassified or escalated, which is what a release cannot have.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLASSIFICATIONS = ("fixed", "visual", "intentional", "escalated")


def load(directory):
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(Path(directory).glob("*.json"))
        if p.name != "differences.json"
    }


def _text(value):
    """The canonical JSON text of a value. Compared as text because Python says 3 == 3.0 and 1 == True, and a caller can
    tell an int from a float and a bool from an int."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _is_error(value):
    return isinstance(value, dict) and "$error" in value


def _error_message(value):
    return value["$error"]["message"] if _is_error(value) else None


def _short(value, limit=300):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= limit else text[:limit] + "..."


def compare_script(script, baseline, candidate):
    """The differences between two result dicts of one script, as a list of dicts."""
    found = []

    def add(kind, name, base, cand):
        found.append(
            {
                "script": script,
                "name": name,
                "kind": kind,
                "baseline": _short(base),
                "candidate": _short(cand),
            }
        )

    def error_of(
        result,
    ):  # the traceback tail differs by variant, so it is not compared
        error = result["error"]
        return error and {"type": error["type"], "message": error["message"]}

    if _text(error_of(baseline)) != _text(error_of(candidate)):
        add("script error", "*", error_of(baseline), error_of(candidate))

    base_records = {r["name"]: r["value"] for r in baseline["records"]}
    cand_records = {r["name"]: r["value"] for r in candidate["records"]}
    for name in list(base_records) + [n for n in cand_records if n not in base_records]:
        if name not in cand_records:
            add("record only in baseline", name, base_records[name], None)
        elif name not in base_records:
            add("record only in candidate", name, None, cand_records[name])
        elif _text(base_records[name]) != _text(cand_records[name]):
            add(
                (
                    "error differs"
                    if _is_error(base_records[name]) or _is_error(cand_records[name])
                    else "value differs"
                ),
                name,
                base_records[name],
                cand_records[name],
            )
            base_message, cand_message = _error_message(
                base_records[name]
            ), _error_message(cand_records[name])
            if (
                base_message
                and cand_message
                and "FaultException" in base_message
                and cand_message in base_message
            ):
                found[-1][
                    "detail"
                ] = "the candidate's message is inside the baseline's: same server message, different wrapper"
    return found


def compare(baseline_results, candidate_results):
    differences = []
    for script in sorted(set(baseline_results) | set(candidate_results)):
        if script not in candidate_results:
            differences.append(
                {
                    "script": script,
                    "name": "*",
                    "kind": "script only in baseline",
                    "baseline": "",
                    "candidate": "",
                }
            )
        elif script not in baseline_results:
            differences.append(
                {
                    "script": script,
                    "name": "*",
                    "kind": "script only in candidate",
                    "baseline": "",
                    "candidate": "",
                }
            )
        else:
            differences.extend(
                compare_script(
                    script, baseline_results[script], candidate_results[script]
                )
            )
    return differences


def classify(differences, classifications):
    """Adds 'classification' and 'note' to each difference ('unclassified' when no entry matches); returns the list."""
    for entry in classifications:
        if entry.get("classification") not in CLASSIFICATIONS:
            raise ValueError(
                f"classification must be one of {CLASSIFICATIONS}: {entry}"
            )
    for difference in differences:
        match = next(
            (
                c
                for c in classifications
                if c["script"] in ("*", difference["script"])
                and c["name"] in ("*", difference["name"])
                and c.get("kind", difference["kind"]) == difference["kind"]
                and c.get("detail_contains", "") in difference.get("detail", "")
            ),
            None,
        )
        difference["classification"] = (
            match["classification"] if match else "unclassified"
        )
        difference["note"] = match.get("note", "") if match else ""
    return differences


def open_differences(differences):
    return [
        d for d in differences if d["classification"] in ("unclassified", "escalated")
    ]


def main(argv):
    results = Path(argv[1]) if len(argv) > 1 else HERE / "results"
    classification_file = HERE / "classifications.json"
    classifications = (
        json.loads(classification_file.read_text(encoding="utf-8"))
        if classification_file.exists()
        else []
    )
    baseline, candidate = load(results / "baseline"), load(results / "candidate")
    differences = classify(compare(baseline, candidate), classifications)
    (results / "differences.json").write_text(
        json.dumps(differences, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    counts = {}
    for d in differences:
        counts[d["classification"]] = counts.get(d["classification"], 0) + 1
    print(
        f"{len(baseline)} baseline and {len(candidate)} candidate scripts; {len(differences)} differences: {counts or 'none'}"
    )
    for d in open_differences(differences):
        print(
            f"  [{d['classification']}] {d['script']} / {d['name']}: {d['kind']}\n      baseline : {d['baseline']}\n      candidate: {d['candidate']}"
            + (f"\n      note     : {d['detail']}" if d.get("detail") else "")
        )
    return 1 if open_differences(differences) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
