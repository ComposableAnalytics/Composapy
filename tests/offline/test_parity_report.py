"""Offline tests for tools/parity/make_report.py: grouping and rendering, with made-up results."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from tools.parity.make_report import area, group_by_note, render  # noqa: E402


def diff(script, name, classification, note):
    return {
        "script": script,
        "name": name,
        "kind": "value differs",
        "baseline": "1",
        "candidate": "2",
        "classification": classification,
        "note": note,
    }


def result(n):
    return {"records": [{"name": f"r{i}", "value": i} for i in range(n)]}


DIFFS = [
    diff("a", "x", "intentional", "one reason"),
    diff("a", "y", "intentional", "one reason"),
    diff("b", "z", "fixed", "a baseline bug"),
    diff("b", "w", "visual", "looks different"),
]


def test_differences_are_grouped_by_their_note_in_first_seen_order():
    groups = group_by_note(DIFFS, "intentional")
    assert list(groups) == ["one reason"] and [
        d["name"] for d in groups["one reason"]
    ] == ["x", "y"]
    assert (
        list(group_by_note(DIFFS, "fixed")) == ["a baseline bug"]
        and group_by_note(DIFFS, "escalated") == {}
    )


def test_the_report_counts_records_and_names_every_classification():
    text = render(
        {"a": result(5), "b": result(3)}, {}, DIFFS, {}, "", {"Baseline": "0.13.3"}
    )
    assert (
        "8 records each" in text
        and "4 records are identical; 4 differ" in text
        and "**0 are open.**" in text
    )
    assert "2 intentional" in text and "1 fixed" in text and "1 visual" in text
    assert (
        "one reason" in text and "a baseline bug" in text and "`a / x`, `a / y`" in text
    )


def test_a_long_group_is_cut_with_a_count_of_the_rest():
    many = [diff("s", f"n{i}", "intentional", "same reason") for i in range(15)]
    text = render({"s": result(20)}, {}, many, {}, "", {})
    assert "and 3 more" in text


def test_areas_group_scripts_by_name():
    assert (
        area("queryview_types") == "queryview"
        and area("wrapper_nb_pandas_str_int8") == "notebook DataFrames"
    )
    assert area("wrapper_script_strings") == "scripts" and area("unheard_of") == "other"


def test_the_import_time_table_has_one_row_per_python_and_the_speedup():
    times = {
        "py311": {
            "python": "3.11.4",
            "baseline_median": 30.0,
            "candidate_median": 0.6,
            "forbidden": [],
            "candidate_version": "1.0.0",
        }
    }
    text = render({"a": result(1)}, {}, [], times, "", {})
    assert "| py311 (3.11.4) | 30.000 s | 0.600 s | 50x | none |" in text
