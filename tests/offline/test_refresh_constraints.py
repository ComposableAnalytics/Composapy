"""Offline tests for tools/refresh_constraints.py: the DataLab requirements files become tox constraints files.

The real requirements38.txt starts with a UTF-8 byte order mark and all three files use CRLF line endings, so both are
tested here, and the last test reads the product tree's files when they are present.
"""

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = REPO_ROOT / "tools" / "refresh_constraints.py"
PRODUCT_STATIC = Path(
    os.getenv(
        "DATALAB_STATIC_DIR", r"C:\repo\Product\CompAnalytics.DataLabService\static"
    )
)

spec = importlib.util.spec_from_file_location("refresh_constraints", TOOL)
refresh_constraints = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh_constraints)
write_constraints = refresh_constraints.write_constraints

PIN = re.compile(r"[A-Za-z0-9_.\-]+==\S+(\s*;.*)?")


@pytest.fixture
def dirs(tmp_path):
    static, constraints = tmp_path / "static", tmp_path / "constraints"
    static.mkdir()
    return static, constraints


def write(path, text, encoding="utf-8"):
    path.write_bytes(text.encode(encoding))


def read(path):
    return path.read_bytes().decode("utf-8")


def test_one_constraints_file_is_written_for_each_requirements_file(dirs):
    static, constraints = dirs
    for version in ("38", "311", "313"):
        write(static / f"requirements{version}.txt", "numpy==1.0\n")
    write_constraints(static, constraints)
    assert sorted(p.name for p in constraints.iterdir()) == [
        "py311.txt",
        "py313.txt",
        "py38.txt",
    ]


@pytest.mark.parametrize(
    "name",
    [
        "requirements.txt",
        "requirements38.md",
        "requirementsX.txt",
        "requirements38.txt.bak",
        "notes.txt",
        "worker.py",
        "my-requirements38.txt",
    ],
)
def test_other_files_in_the_folder_are_ignored(dirs, name):
    static, constraints = dirs
    write(static / "requirements311.txt", "numpy==1.0\n")
    write(static / name, "pandas==2.0.3\n")
    write_constraints(static, constraints)
    assert [p.name for p in constraints.iterdir()] == ["py311.txt"]


def test_sub_folders_are_ignored(dirs):
    static, constraints = dirs
    write(static / "requirements311.txt", "numpy==1.0\n")
    (static / "requirements38.txt").mkdir()
    write_constraints(static, constraints)
    assert [p.name for p in constraints.iterdir()] == ["py311.txt"]


def test_the_pinned_lines_are_kept_in_order(dirs):
    static, constraints = dirs
    write(static / "requirements311.txt", "zeta==1.0\nalpha==2.0\nnumpy==1.25.0\n")
    write_constraints(static, constraints)
    assert read(constraints / "py311.txt") == "zeta==1.0\nalpha==2.0\nnumpy==1.25.0\n"


@pytest.mark.parametrize(
    "line",
    [
        "composapy==1.0.0",
        "composapy==0.13.3",
        "Composapy==1.0.0",
        "COMPOSAPY==1.0.0",
        "composapy[deps]==1.0",
        "composapy ==1.0",
    ],
)
def test_composapy_itself_is_left_out(dirs, line):
    static, constraints = dirs
    write(static / "requirements311.txt", f"numpy==1.0\n{line}\npandas==2.0.3\n")
    write_constraints(static, constraints)
    assert read(constraints / "py311.txt") == "numpy==1.0\npandas==2.0.3\n"


def test_a_package_whose_name_only_starts_with_composapy_is_kept(dirs):
    static, constraints = dirs
    write(static / "requirements311.txt", "composapy-extras==1.0\n")
    write_constraints(static, constraints)
    assert read(constraints / "py311.txt") == "composapy-extras==1.0\n"


def test_comments_blank_lines_and_options_are_left_out(dirs):
    static, constraints = dirs
    write(
        static / "requirements311.txt",
        "# the DataLab packages\n\n-r other.txt\n--find-links wheels\n-e .\nnumpy==1.0\n   \n",
    )
    write_constraints(static, constraints)
    assert read(constraints / "py311.txt") == "numpy==1.0\n"


def test_a_line_with_an_environment_marker_is_kept_whole(dirs):
    static, constraints = dirs
    write(static / "requirements311.txt", 'pywin32==306 ; sys_platform == "win32"\n')
    write_constraints(static, constraints)
    assert read(constraints / "py311.txt") == 'pywin32==306 ; sys_platform == "win32"\n'


def test_a_byte_order_mark_on_the_first_line_is_removed(dirs):
    static, constraints = dirs
    write(
        static / "requirements38.txt", "\ufeffansiwrap==0.8.4\nnumpy==1.22.2\n"
    )  # as in the real file
    write_constraints(static, constraints)
    assert not (constraints / "py38.txt").read_bytes().startswith(b"\xef\xbb\xbf")
    assert read(constraints / "py38.txt") == "ansiwrap==0.8.4\nnumpy==1.22.2\n"


def test_windows_line_endings_become_unix_line_endings_and_the_file_ends_with_one(dirs):
    static, constraints = dirs
    write(static / "requirements311.txt", "numpy==1.0\r\npandas==2.0.3\r\n")
    write_constraints(static, constraints)
    assert (constraints / "py311.txt").read_bytes() == b"numpy==1.0\npandas==2.0.3\n"


def test_a_file_without_a_final_newline_still_gets_one(dirs):
    static, constraints = dirs
    write(static / "requirements311.txt", "numpy==1.0")
    write_constraints(static, constraints)
    assert read(constraints / "py311.txt") == "numpy==1.0\n"


def test_the_constraints_folder_is_created_when_it_is_missing(dirs):
    static, constraints = dirs
    write(static / "requirements311.txt", "numpy==1.0\n")
    assert not constraints.exists()
    write_constraints(static, constraints / "deeper")
    assert (constraints / "deeper" / "py311.txt").exists()


def test_an_existing_file_is_replaced_and_a_second_run_changes_nothing(dirs):
    static, constraints = dirs
    constraints.mkdir()
    write(constraints / "py311.txt", "old==0.1\n")
    write(static / "requirements311.txt", "numpy==1.0\n")
    write_constraints(static, constraints)
    first = (constraints / "py311.txt").read_bytes()
    write_constraints(static, constraints)
    assert (
        first == b"numpy==1.0\n" and (constraints / "py311.txt").read_bytes() == first
    )


def test_the_script_takes_the_two_folders_as_arguments(dirs):
    static, constraints = dirs
    write(static / "requirements311.txt", "numpy==1.0\n")
    result = subprocess.run(
        [sys.executable, str(TOOL), str(static), str(constraints)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert read(constraints / "py311.txt") == "numpy==1.0\n"


def test_the_script_does_not_depend_on_the_current_folder(dirs, tmp_path):
    static, constraints = dirs
    write(static / "requirements311.txt", "numpy==1.0\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = subprocess.run(
        [sys.executable, str(TOOL), str(static), str(constraints)],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert (
        result.returncode == 0
    ), result.stderr  # it once opened file.name instead of the full path
    assert (constraints / "py311.txt").exists()


@pytest.mark.skipif(
    not PRODUCT_STATIC.is_dir(),
    reason="the product tree's static folder is not present",
)
def test_the_real_requirements_files_give_clean_constraints(tmp_path):
    constraints = tmp_path / "constraints"
    write_constraints(PRODUCT_STATIC, constraints)
    assert sorted(p.name for p in constraints.iterdir()) == [
        "py311.txt",
        "py313.txt",
        "py38.txt",
    ]
    for out in constraints.iterdir():
        lines = read(out).splitlines()
        assert lines and all(PIN.fullmatch(line) for line in lines), [
            l for l in lines if not PIN.fullmatch(l)
        ]
        assert not any(line.lower().startswith("composapy") for line in lines)
        assert "\r" not in read(out) and not out.read_bytes().startswith(
            b"\xef\xbb\xbf"
        )
        assert any(
            line.startswith(("numpy==", "pandas==", "requests==")) for line in lines
        )
