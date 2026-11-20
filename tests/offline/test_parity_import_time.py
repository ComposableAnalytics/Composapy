"""Offline tests for tools/parity/compare_import_time.py."""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from tools.parity import compare_import_time  # noqa: E402
from tools.parity.compare_import_time import (  # noqa: E402
    compare,
    forbidden_imports,
    imported_modules,
    main,
)

SAMPLE = """\
import time: self [us] | cumulative | imported package
import time:       120 |        120 |   _io
import time:       350 |        350 | composapy
import time:       200 |       1500 |   composapy._wire
import time:       900 |        900 |     composapy._wire.codec
import time:      4000 |       4000 |   pandas
import time:        50 |         50 |   numpy.core
"""


def measurement(median, importtime=SAMPLE):
    return {
        "median_seconds": median,
        "importtime": importtime,
        "composapy_version": "1.0.0.dev4",
        "python": "3.11.4",
        "runs": 20,
    }


def test_the_module_names_are_read_from_each_import_line_whatever_their_indent():
    assert imported_modules(SAMPLE) == [
        "_io",
        "composapy",
        "composapy._wire",
        "composapy._wire.codec",
        "pandas",
        "numpy.core",
    ]


def test_a_faster_candidate_without_forbidden_imports_passes():
    result = compare(measurement(27.9), measurement(1.2))
    assert result["faster"] and result["forbidden"] == []


def test_a_candidate_that_is_not_faster_fails_even_by_a_little():
    assert not compare(measurement(1.0), measurement(1.0))["faster"]
    assert not compare(measurement(1.0), measurement(1.1))["faster"]


def test_forbidden_imports_are_found_with_their_submodules():
    text = (
        SAMPLE
        + "import time:  10 | 10 |   papermill.utils\nimport time:  10 | 10 |   clr\nimport time:  10 | 10 |   pythonnet\nimport time:  10 | 10 |   clr_loader.ffi\n"
    )
    assert forbidden_imports(text) == [
        "clr",
        "clr_loader.ffi",
        "papermill.utils",
        "pythonnet",
    ]


def test_a_module_that_only_starts_with_a_forbidden_word_is_not_forbidden():
    text = (
        SAMPLE
        + "import time: 10 | 10 |   clrfoo\nimport time: 10 | 10 |   papermillish\nimport time: 10 | 10 |   mypapermill\n"
    )
    assert forbidden_imports(text) == []


def test_forbidden_imports_make_the_comparison_report_them():
    result = compare(
        measurement(27.9),
        measurement(1.2, SAMPLE + "import time: 10 | 10 |   papermill\n"),
    )
    assert result["forbidden"] == ["papermill"]


def test_the_real_baseline_files_are_readable_and_carry_the_importtime_text():
    for label in ("py38", "py311", "py313"):
        baseline = json.loads(
            (REPO_ROOT / "tests" / "baseline" / f"import_time_{label}.json").read_text(
                encoding="utf-8"
            )
        )
        assert baseline["median_seconds"] > 0
        modules = imported_modules(baseline["importtime"])
        assert "composapy" in modules and any(
            name == "clr" or name.startswith("clr.") for name in modules
        )


# ----------------------------------------------------------------------------------------------
# main: what it reads, what it prints, and when it fails
# ----------------------------------------------------------------------------------------------


@pytest.fixture
def root(tmp_path, monkeypatch):
    """A folder laid out like the repo, so that main reads the baselines and candidates written here."""
    (tmp_path / "tests" / "baseline").mkdir(parents=True)
    (tmp_path / "tools" / "parity" / "results").mkdir(parents=True)
    monkeypatch.setattr(compare_import_time, "ROOT", tmp_path)
    return tmp_path


def write_pair(root, label, baseline, candidate, with_candidate=True):
    (root / "tests" / "baseline" / f"import_time_{label}.json").write_text(
        json.dumps(baseline), encoding="utf-8"
    )
    if with_candidate:
        (
            root
            / "tools"
            / "parity"
            / "results"
            / f"import_time_{label}-candidate.json"
        ).write_text(json.dumps(candidate), encoding="utf-8")


def test_main_prints_both_medians_the_ratio_and_the_candidates_details_and_exits_0(
    root, capsys
):
    write_pair(root, "py311", measurement(28.0), measurement(0.6))
    assert main(["compare_import_time.py", "py311"]) == 0
    assert capsys.readouterr().out == (
        "py311: baseline 28.000 s, candidate 0.600 s "
        "(47x faster, composapy 1.0.0.dev4, Python 3.11.4, 20 runs)\n"
    )


def test_main_without_labels_checks_py38_py311_and_py313_in_that_order(root, capsys):
    for label in ("py38", "py311", "py313"):
        write_pair(root, label, measurement(28.0), measurement(1.0))
    assert main(["compare_import_time.py"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split(":")[0] for line in lines] == ["py38", "py311", "py313"]


def test_the_first_argument_is_the_program_not_a_label(root, capsys):
    write_pair(root, "py311", measurement(28.0), measurement(1.0))
    # "py311" is taken as the program name, so the defaults run; only py311's files exist here
    assert main(["py311"]) == 1
    out = capsys.readouterr().out
    assert "py38: no candidate measurement" in out and "py311: baseline" in out


def test_a_label_without_a_candidate_is_reported_and_fails_without_reading_a_baseline(
    root, capsys
):
    # no baseline file is written either, so reading it would be a FileNotFoundError
    assert main(["compare_import_time.py", "py311"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("py311: no candidate measurement at ")
    assert "import_time_py311-candidate.json" in out


def test_a_candidate_that_is_not_faster_prints_not_faster_and_fails(root, capsys):
    write_pair(root, "py311", measurement(1.0), measurement(1.0))
    assert main(["compare_import_time.py", "py311"]) == 1
    out = capsys.readouterr().out
    assert out.endswith("  NOT FASTER\n") and "1x faster" in out


def test_forbidden_imports_are_listed_and_fail_even_for_a_faster_candidate(
    root, capsys
):
    extra = (
        SAMPLE + "import time: 10 | 10 |   papermill\nimport time: 10 | 10 |   clr\n"
    )
    write_pair(root, "py311", measurement(28.0), measurement(0.6, extra))
    assert main(["compare_import_time.py", "py311"]) == 1
    out = capsys.readouterr().out
    assert out.endswith("  FORBIDDEN IMPORTS: clr, papermill\n")
    assert "NOT FASTER" not in out


def test_a_candidate_that_is_slower_and_forbidden_reports_both(root, capsys):
    write_pair(
        root,
        "py311",
        measurement(1.0),
        measurement(2.0, SAMPLE + "import time: 1 | 1 |   pythonnet\n"),
    )
    assert main(["compare_import_time.py", "py311"]) == 1
    out = capsys.readouterr().out
    assert "NOT FASTER" in out and "FORBIDDEN IMPORTS: pythonnet" in out


def test_one_failing_label_fails_the_run_but_every_label_is_still_reported(
    root, capsys
):
    write_pair(root, "py38", measurement(28.0), measurement(0.6))
    write_pair(root, "py311", measurement(1.0), measurement(2.0))
    write_pair(root, "py313", measurement(28.0), measurement(0.6))
    assert main(["compare_import_time.py", "py38", "py311", "py313"]) == 1
    out = capsys.readouterr().out
    assert [line.split(":")[0] for line in out.splitlines()] == [
        "py38",
        "py311",
        "py313",
    ]
    assert out.count("NOT FASTER") == 1


def test_a_missing_candidate_does_not_stop_the_labels_after_it(root, capsys):
    write_pair(root, "py38", measurement(28.0), None, with_candidate=False)
    write_pair(root, "py311", measurement(28.0), measurement(0.6))
    assert main(["compare_import_time.py", "py38", "py311"]) == 1
    out = capsys.readouterr().out
    assert "py38: no candidate" in out and "py311: baseline 28.000 s" in out


def test_a_candidate_with_no_importtime_text_has_no_forbidden_imports(root, capsys):
    candidate = measurement(0.6)
    del candidate["importtime"]
    write_pair(root, "py311", measurement(28.0), candidate)
    assert main(["compare_import_time.py", "py311"]) == 0


def test_pinned_a_candidate_that_took_no_time_prints_inf_as_the_ratio(root, capsys):
    # Pinned, needs a decision: a median of 0 is a bad measurement, and it passes as infinitely faster
    write_pair(root, "py311", measurement(28.0), measurement(0))
    assert main(["compare_import_time.py", "py311"]) == 0
    assert "(infx faster" in capsys.readouterr().out


def test_pinned_a_candidate_without_a_baseline_file_is_a_file_not_found_error(root):
    # Pinned, needs a decision: it is a traceback, not a line saying which baseline is missing
    write_pair(root, "py311", None, measurement(0.6))
    (root / "tests" / "baseline" / "import_time_py311.json").unlink()
    with pytest.raises(FileNotFoundError):
        main(["compare_import_time.py", "py311"])


def test_compare_carries_the_candidates_version_python_and_runs():
    result = compare(measurement(27.9), measurement(1.2))
    assert (
        result["baseline_median"],
        result["candidate_median"],
        result["candidate_version"],
        result["python"],
        result["runs"],
    ) == (27.9, 1.2, "1.0.0.dev4", "3.11.4", 20)


def test_run_as_a_script_it_exits_with_main_s_result(tmp_path):
    import subprocess

    script = REPO_ROOT / "tools" / "parity" / "compare_import_time.py"
    done = subprocess.run(
        [sys.executable, str(script), "no-such-label"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 1
    assert done.stdout.startswith("no-such-label: no candidate measurement at ")
