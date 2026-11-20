"""The C# DataLab suites copy only the top-level test*.py files and conftest.py (and .test.env) into a DataLab's working
directory, with no __init__.py and no iis.py. conftest.py is then a top-level module, so it cannot import its siblings
as a package or rely on them being there. These tests stage the files the way BaseDataLabCellExecutionTests does and
have pytest collect them."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import composapy

TESTS_DIR = Path(__file__).resolve().parent.parent


def stage_like_the_csharp_suites(destination):
    """What SetupTestsAndTestFiles copies: top-level files whose names start with "test", and conftest.py."""
    destination.mkdir(parents=True)
    for path in TESTS_DIR.iterdir():
        if path.is_file() and (
            path.name.startswith("test") or path.name == "conftest.py"
        ):
            shutil.copy(path, destination / path.name)
    return destination


def test_the_staged_files_hold_no_package_marker_and_no_iis(tmp_path):
    staged = stage_like_the_csharp_suites(tmp_path / "working")
    names = {p.name for p in staged.iterdir()}
    assert "conftest.py" in names and "test_api.py" in names
    assert "__init__.py" not in names and "iis.py" not in names


def test_pytest_collects_the_staged_files(tmp_path):
    staged = stage_like_the_csharp_suites(tmp_path / "working")
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=staged,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(composapy.__file__).resolve().parent.parent),
        },  # the composapy under test
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = run.stdout + run.stderr
    assert "ImportError" not in output, output
    assert run.returncode == 0, output
    assert "test_windows_auth.py" in output
