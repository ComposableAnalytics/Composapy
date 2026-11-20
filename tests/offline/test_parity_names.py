"""Offline tests for tools/parity/compare_names.py: which baseline names the candidate must still have."""

import copy
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from tools.parity.compare_names import compare, has_breaks, report  # noqa: E402

BASELINE_FILE = REPO_ROOT / "tests" / "baseline" / "public_names.json"


def entry(kind, defined_in="composapy.x"):
    return {"type": kind, "defined_in": defined_in}


BASE = {
    "modules": {
        "composapy": {
            "Session": entry("type"),
            "to_table": entry("function"),
            "Table": entry("CLRMetatype", "CompAnalytics.Contracts.Tables"),
            "CompAnalytics": entry("ModuleObject", None),
        },
        "composapy.auth": {"AuthMode": entry("EnumType")},
    },
    "import_errors": {},
}


def candidate(module="composapy", **changes):
    """A copy of BASE with the named entries of one module replaced, or removed when the value is None."""
    result = copy.deepcopy(BASE)
    for name, value in changes.items():
        if value is None:
            result["modules"][module].pop(name, None)
        else:
            result["modules"][module][name] = value
    return result


def test_identical_names_have_no_differences():
    result = compare(BASE, copy.deepcopy(BASE))
    assert (
        not has_breaks(result)
        and result["changed_types"] == {}
        and result["dotnet_skipped"] == 2
    )


def test_dotnet_types_are_not_required():
    result = compare(BASE, candidate(Table=None, CompAnalytics=None))
    assert not has_breaks(result) and result["dotnet_skipped"] == 2


def test_a_missing_python_name_is_a_break():
    result = compare(BASE, candidate(to_table=None))
    assert has_breaks(result) and result["missing_names"] == {"composapy": ["to_table"]}
    assert "MISSING NAME    composapy.to_table" in report(result)


def test_a_missing_module_is_a_break_and_its_names_are_not_listed_twice():
    cand = candidate()
    del cand["modules"]["composapy.auth"]
    result = compare(BASE, cand)
    assert (
        has_breaks(result)
        and result["missing_modules"] == ["composapy.auth"]
        and result["missing_names"] == {}
    )


def test_a_new_name_in_the_candidate_is_not_a_difference():
    assert not has_breaks(compare(BASE, candidate(ServiceFault=entry("type"))))


def test_a_changed_type_is_reported_but_is_not_a_break():
    result = compare(BASE, candidate(Session=entry("function")))
    assert not has_breaks(result) and result["changed_types"] == {
        "composapy": {"Session": ("type", "function")}
    }
    assert "TYPE CHANGED    composapy.Session: type -> function" in report(result)


def test_an_import_error_only_in_the_candidate_is_a_break():
    cand = candidate()
    cand["import_errors"] = {"composapy.magics": "NameError: nothing"}
    assert has_breaks(compare(BASE, cand))
    base = copy.deepcopy(BASE)
    base["import_errors"] = {"composapy.magics": "NameError: nothing"}
    assert not has_breaks(compare(base, cand))  # the baseline had the same error


def test_the_checked_in_baseline_compared_with_itself_has_no_breaks():
    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    result = compare(baseline, copy.deepcopy(baseline))
    assert not has_breaks(result) and result["dotnet_skipped"] > 0


def test_removing_any_python_name_from_the_real_baseline_is_caught():
    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    cand = copy.deepcopy(baseline)
    module = "composapy.dataflow.api"
    victim = next(
        n
        for n, i in cand["modules"][module].items()
        if i["type"] not in ("CLRMetatype", "ModuleObject")
    )
    del cand["modules"][module][victim]
    assert compare(baseline, cand)["missing_names"] == {module: [victim]}


def test_the_script_exits_1_on_a_break_and_0_otherwise(tmp_path):
    tool = REPO_ROOT / "tools" / "parity" / "compare_names.py"
    base, good, bad = (
        tmp_path / "base.json",
        tmp_path / "good.json",
        tmp_path / "bad.json",
    )
    base.write_text(json.dumps(BASE), encoding="utf-8")
    good.write_text(json.dumps(BASE), encoding="utf-8")
    bad.write_text(json.dumps(candidate(to_table=None)), encoding="utf-8")
    ok = subprocess.run(
        [sys.executable, str(tool), str(base), str(good)],
        capture_output=True,
        text=True,
    )
    broken = subprocess.run(
        [sys.executable, str(tool), str(base), str(bad)], capture_output=True, text=True
    )
    assert (
        ok.returncode == 0
        and broken.returncode == 1
        and "MISSING NAME" in broken.stdout
    )


def test_missing_names_are_grouped_as_private_incidental_or_defined_by_composapy():
    from tools.parity.compare_names import classify_missing

    base = copy.deepcopy(BASE)
    base["modules"]["composapy"].update(
        {
            "_helper": entry("function"),
            "os": entry("module", None),
            "Path": entry("type", "pathlib"),
            "deep_copy": entry("function", "composapy.patch.execution_handle"),
        }
    )
    result = compare(base, candidate())
    groups = classify_missing(base, result)
    assert [g.split(" ")[0] for g in groups["private"]] == ["composapy._helper"]
    assert sorted(g.split(" ")[0] for g in groups["incidental"]) == [
        "composapy.Path",
        "composapy.os",
    ]
    assert [g.split(" ")[0] for g in groups["composapy"]] == ["composapy.deep_copy"]


def test_the_report_lists_only_the_composapy_names_unless_asked_for_all():
    base = copy.deepcopy(BASE)
    base["modules"]["composapy"].update(
        {
            "os": entry("module", None),
            "deep_copy": entry("function", "composapy.patch.x"),
        }
    )
    result = compare(base, candidate())
    short, everything = report(result, base, show_all=False), report(
        result, base, show_all=True
    )
    assert (
        "composapy.deep_copy" in short
        and "composapy.os" not in short
        and "missing names, incidental: 1" in short
    )
    assert "composapy.os" in everything
