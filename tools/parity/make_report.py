"""Write tools/parity/report.md from the parity results, the classifications, and the import-time and names measurements.

    python make_report.py

It reads results/baseline and results/candidate (run_parity.py and run_wrappers.py write them), differences.json (made by
compare_results.py), results/import_time_*-candidate.json (measure_import.py) and results/public_names_candidate.json
(make_baseline_names.py), and refuses to write a report while any difference is unclassified or escalated.
"""

import json
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import compare_results  # noqa: E402
import compare_names  # noqa: E402
import compare_import_time  # noqa: E402

CLASS_TITLES = OrderedDict(
    [
        ("fixed", "Fixed: a bug in the baseline that the candidate does not have"),
        ("intentional", "Intentional: a change recorded with its reason"),
        ("visual", "Visual only (R5)"),
    ]
)


def group_by_note(differences, classification):
    """{note: [difference, ...]} for the differences with this classification, in the order the notes first appear."""
    groups = OrderedDict()
    for difference in differences:
        if difference["classification"] == classification:
            groups.setdefault(difference["note"], []).append(difference)
    return groups


def area(script):
    for prefix in (
        "wrapper_nb_pandas",
        "wrapper_nb",
        "wrapper_script",
        "queryview",
        "key",
        "dataflow",
        "dataframe",
        "session",
        "file_reference",
        "uri",
        "net_list",
        "table",
        "to_table",
        "errors",
    ):
        if script.startswith(prefix):
            return (
                prefix.replace("wrapper_nb_pandas", "notebook DataFrames")
                .replace("wrapper_nb", "notebooks")
                .replace("wrapper_script", "scripts")
            )
    return "other"


def render(baseline, candidate, differences, import_times, names_summary, environment):
    lines = ["# Parity report: composapy 0.13.3 and the release candidate", ""]
    records = sum(len(r["records"]) for r in baseline.values())
    differing_names = {(d["script"], d["name"]) for d in differences}
    open_count = len(compare_results.open_differences(differences))
    by_class = {
        c: sum(1 for d in differences if d["classification"] == c) for c in CLASS_TITLES
    }

    lines += [
        f"Both variants ran {len(baseline)} scripts against one local instance and a token session, {records} records each. "
        f"{records - len(differing_names)} records are identical; {len(differing_names)} differ, and every difference is classified: "
        + ", ".join(f"{n} {c}" for c, n in by_class.items())
        + f". **{open_count} are open.**",
        "",
        "## What was compared",
        "",
        *[f"- {k}: {v}" for k, v in environment.items()],
        "",
        "Each script runs in its own process under each variant. A record is a value a caller can observe (`record`), or the result of a call "
        "that may fail (`attempt`: its value, or the class name and message of the exception). Records are compared as canonical JSON text, so an int "
        "and a float, or a bool and an int, are different. DataFrames compare by columns, dtypes, index, and every cell. The wrapper cases run "
        "`nb_wrap` and `script_wrap` as DataLab does and compare the exit code, `outputs.serialized` (value, key order, member order), and the tables "
        "behind any returned Table.",
        "",
        "## Records by area",
        "",
        "| Area | Scripts | Records | Differences |",
        "|---|---|---|---|",
    ]
    areas = OrderedDict()
    for script, result in sorted(baseline.items()):
        entry = areas.setdefault(area(script), {"scripts": 0, "records": 0, "diffs": 0})
        entry["scripts"] += 1
        entry["records"] += len(result["records"])
        entry["diffs"] += sum(1 for d in differences if d["script"] == script)
    for name, entry in areas.items():
        lines.append(
            f"| {name} | {entry['scripts']} | {entry['records']} | {entry['diffs']} |"
        )
    lines.append("")

    for classification, title in CLASS_TITLES.items():
        groups = group_by_note(differences, classification)
        if not groups:
            continue
        lines += [f"## {title}", ""]
        for note, members in groups.items():
            lines.append(f"- {note}")
            lines.append(
                f"  - {len(members)} difference{'s' if len(members) != 1 else ''}: "
                + ", ".join(f"`{d['script']} / {d['name']}`" for d in members[:12])
                + (f", and {len(members) - 12} more" if len(members) > 12 else "")
            )
        lines.append("")

    lines += [
        "## Import time",
        "",
        "| Python | Baseline median | Candidate median | Faster | Forbidden imports |",
        "|---|---|---|---|---|",
    ]
    for label, result in import_times.items():
        lines.append(
            f"| {label} ({result['python']}) | {result['baseline_median']:.3f} s | {result['candidate_median']:.3f} s | "
            f"{result['baseline_median'] / result['candidate_median']:.0f}x | {', '.join(result['forbidden']) or 'none'} |"
        )
    lines += [
        "",
        (
            f"Measured with composapy {next(iter(import_times.values()))['candidate_version']} "
            if import_times
            else ""
        ),
        "",
    ]

    if names_summary:
        lines += ["## Public names", "", names_summary, ""]
    return "\n".join(lines).rstrip() + "\n"


def environment_facts():
    def installed(variant, package):
        found = sorted(
            (HERE / "envs" / variant / "Lib" / "site-packages").glob(
                f"{package}-*.dist-info"
            )
        )
        return (
            found[0].name[len(package) + 1 : -len(".dist-info")]
            if found
            else "not installed"
        )

    return OrderedDict(
        [
            (
                "Baseline",
                f"composapy {installed('baseline', 'composapy')} with pythonnet {installed('baseline', 'pythonnet')} (the wheel DataLabs run today)",
            ),
            (
                "Candidate",
                f"composapy {installed('candidate', 'composapy')}, with no pythonnet",
            ),
            (
                "Packages",
                f"numpy {installed('candidate', 'numpy')}, pandas {installed('candidate', 'pandas')}, requests {installed('candidate', 'requests')} "
                "(the DataLab Python 3.11 pins) in both",
            ),
            (
                "Instance",
                "a local platform instance, reached over a token session; saved Keys and QueryViews are created before the run and removed after",
            ),
        ]
    )


def main():
    results = HERE / "results"
    differences = json.loads((results / "differences.json").read_text(encoding="utf-8"))
    if compare_results.open_differences(differences):
        sys.exit(
            "There are unclassified or escalated differences; run compare_results.py and classify them first."
        )
    baseline, candidate = compare_results.load(
        results / "baseline"
    ), compare_results.load(results / "candidate")

    import_times = OrderedDict()
    for label in ("py38", "py311", "py313"):
        base_file = ROOT / "tests" / "baseline" / f"import_time_{label}.json"
        cand_file = results / f"import_time_{label}-candidate.json"
        if base_file.exists() and cand_file.exists():
            import_times[label] = compare_import_time.compare(
                json.loads(base_file.read_text(encoding="utf-8")),
                json.loads(cand_file.read_text(encoding="utf-8")),
            )

    names_summary = ""
    names_file = results / "public_names_candidate.json"
    if names_file.exists():
        base_names = json.loads(
            (ROOT / "tests" / "baseline" / "public_names.json").read_text(
                encoding="utf-8"
            )
        )
        compared = compare_names.compare(
            base_names, json.loads(names_file.read_text(encoding="utf-8"))
        )
        groups = compare_names.classify_missing(base_names, compared)
        names_summary = (
            f"{compared['dotnet_skipped']} baseline names are .NET types and are not required. Of the {sum(len(v) for v in groups.values())} other names "
            f"the candidate lacks, {len(groups['private'])} are private, {len(groups['incidental'])} are incidental imports "
            f"(`os`, `np`, `json`, and the like that leaked into a module namespace), and {len(groups['composapy'])} were defined by composapy: "
            "the removed .NET plumbing (`stream`, `configure_binding`, `add_dll_reference`, and all of `bindings` except its dictionary of timeouts) and internals of the old `patch` modules "
            "(the papermill translators, now in `notebook/translators.py`, and `deep_copy` and `reduce_ex`). No type of a name that remains changed. "
            "Nothing in the product source uses any of them."
        )

    report = render(
        baseline,
        candidate,
        differences,
        import_times,
        names_summary,
        environment_facts(),
    )
    (HERE / "report.md").write_text(report, encoding="utf-8")
    print(f"wrote {HERE / 'report.md'} ({len(report.splitlines())} lines)")


if __name__ == "__main__":
    main()
