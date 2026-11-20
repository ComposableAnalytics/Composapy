"""Compare the public names of the candidate composapy with the baseline's (tests/baseline/public_names.json).

Both files come from tools/make_baseline_names.py, run in a shared DataLab environment: the baseline's is checked in, and
the candidate's is made with the same script in an environment that has the candidate wheel.

    python compare_names.py tests/baseline/public_names.json tools/parity/results/public_names_candidate.json [--all]

By default the missing names are grouped as private, incidental (a module, or a name another package defines, that was
in a namespace), and defined by composapy; only the last group is listed, and --all lists every name.

A name the baseline has is required in the candidate unless it is a .NET type (a CLRMetatype or a ModuleObject: the
candidate has no .NET). Exits 1 when a required name or a module is missing, so every row of the output is something to
classify in the parity report.
"""

import json
import sys

DOTNET_TYPES = {"CLRMetatype", "ModuleObject"}


def compare(baseline, candidate):
    """Returns a dict of the differences: missing_modules, missing_names, changed_types, new_import_errors, dotnet_skipped."""
    base_modules, cand_modules = baseline["modules"], candidate["modules"]
    result = {
        "missing_modules": [],
        "missing_names": {},
        "changed_types": {},
        "new_import_errors": {},
        "dotnet_skipped": 0,
    }

    for module, names in base_modules.items():
        if module not in cand_modules:
            result["missing_modules"].append(module)
            continue
        for name, info in names.items():
            if info["type"] in DOTNET_TYPES:
                result["dotnet_skipped"] += 1
                continue
            found = cand_modules[module].get(name)
            if found is None:
                result["missing_names"].setdefault(module, []).append(name)
            elif found["type"] != info["type"]:
                result["changed_types"].setdefault(module, {})[name] = (
                    info["type"],
                    found["type"],
                )

    for module, error in candidate.get("import_errors", {}).items():
        if module not in baseline.get("import_errors", {}):
            result["new_import_errors"][module] = error
    return result


def classify_missing(baseline, result):
    """Splits the missing names into private ones, incidental imports (a module, or something another package defines,
    that happened to be in a namespace), and names composapy itself defined: only the last kind is API to classify.
    """
    buckets = {"private": [], "incidental": [], "composapy": []}
    for module, names in result["missing_names"].items():
        for name in names:
            info = baseline["modules"][module][name]
            defined_in = info["defined_in"] or ""
            if name.startswith("_"):
                kind = "private"
            elif info["type"] == "module" or not defined_in.startswith("composapy"):
                kind = "incidental"
            else:
                kind = "composapy"
            buckets[kind].append(
                f"{module}.{name} [{info['type']} defined in {defined_in}]"
            )
    return {kind: sorted(items) for kind, items in buckets.items()}


def has_breaks(result):
    return bool(
        result["missing_modules"]
        or result["missing_names"]
        or result["new_import_errors"]
    )


def report(result, baseline=None, show_all=True):
    """With the baseline, the missing names are grouped; unless show_all, only those composapy defined are listed."""
    lines = [
        f"{result['dotnet_skipped']} baseline names are .NET types and are not required."
    ]
    for module in result["missing_modules"]:
        lines.append(f"MISSING MODULE  {module}")
    if baseline is not None:
        for kind, items in classify_missing(baseline, result).items():
            lines.append(f"missing names, {kind}: {len(items)}")
            if kind == "composapy" or show_all:
                lines.extend(f"MISSING NAME    {item}" for item in items)
    else:
        for module, names in sorted(result["missing_names"].items()):
            for name in names:
                lines.append(f"MISSING NAME    {module}.{name}")
    for module, error in sorted(result["new_import_errors"].items()):
        lines.append(f"IMPORT ERROR    {module}: {error}")
    for module, changed in sorted(result["changed_types"].items()):
        for name, (old, new) in sorted(changed.items()):
            lines.append(f"TYPE CHANGED    {module}.{name}: {old} -> {new}")
    if not has_breaks(result):
        lines.append("No required name or module is missing.")
    return "\n".join(lines)


def main(argv):
    show_all = "--all" in argv
    argv = [a for a in argv if a != "--all"]
    if len(argv) != 3:
        sys.exit(__doc__)
    with open(argv[1], encoding="utf-8") as f:
        baseline = json.load(f)
    with open(argv[2], encoding="utf-8") as f:
        candidate = json.load(f)
    result = compare(baseline, candidate)
    print(report(result, baseline, show_all))
    return 1 if has_breaks(result) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
