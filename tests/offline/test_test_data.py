"""Offline tests for tools/test_data.py: what is copied to the C# suites' TestData folder, and what is left behind."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from tools.test_data import copy_tests, stale_files  # noqa: E402


def make(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def listing(root):
    return sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )


@pytest.fixture
def tests_dir(tmp_path):
    return make(
        tmp_path / "tests",
        {
            "__init__.py": "",
            "conftest.py": "c",
            "iis.py": "i",
            ".test.env": "e",
            "test_api.py": "a",
            "test_windows_auth.py": "w",
            "TestFiles/data.json": "{}",
            "TestFiles/sub/more.txt": "m",
            "offline/test_codec.py": "x",
            "offline/__init__.py": "",
            "baseline/pickles/table.pkl": "p",
            "wire_captures/A.json": "{}",
            "__pycache__/conftest.cpython-311.pyc": "b",
            ".pytest_cache/README.md": "r",
            "TestFiles/.pytest_cache/v": "v",
            "TestFiles/stale.pyc": "b",
        },
    )


def test_what_the_csharp_suites_need_is_copied(tests_dir, tmp_path):
    destination = tmp_path / "TestData" / "composapy"
    copy_tests(tests_dir, destination)
    assert listing(destination) == [
        ".test.env",
        "TestFiles/data.json",
        "TestFiles/sub/more.txt",
        "__init__.py",
        "conftest.py",
        "iis.py",
        "test_api.py",
        "test_windows_auth.py",
    ]


@pytest.mark.parametrize("folder", ["offline", "baseline", "wire_captures"])
def test_the_python_only_folders_are_not_copied(tests_dir, tmp_path, folder):
    destination = tmp_path / "out"
    copy_tests(tests_dir, destination)
    assert not (destination / folder).exists()


def test_a_folder_with_an_excluded_name_deeper_down_is_still_copied(
    tests_dir, tmp_path
):
    make(
        tests_dir,
        {"TestFiles/offline/keep.txt": "k", "TestFiles/baseline/keep.txt": "k"},
    )
    destination = tmp_path / "out"
    copy_tests(tests_dir, destination)
    assert (destination / "TestFiles" / "offline" / "keep.txt").exists()
    assert (destination / "TestFiles" / "baseline" / "keep.txt").exists()


def test_the_caches_and_compiled_files_are_not_copied(tests_dir, tmp_path):
    destination = tmp_path / "out"
    copy_tests(tests_dir, destination)
    names = {p.name for p in destination.rglob("*")}
    assert not names & {"__pycache__", ".pytest_cache", "stale.pyc"}


def test_a_second_copy_replaces_changed_files_and_deletes_nothing(tests_dir, tmp_path):
    destination = tmp_path / "out"
    copy_tests(tests_dir, destination)
    (tests_dir / "conftest.py").write_text("changed", encoding="utf-8")
    (tests_dir / "test_api.py").unlink()
    copy_tests(tests_dir, destination)
    assert (destination / "conftest.py").read_text(encoding="utf-8") == "changed"
    assert (
        destination / "test_api.py"
    ).exists()  # removal is for `tf delete`, not for the copy


def test_a_path_given_as_text_works_too(tests_dir, tmp_path):
    copy_tests(str(tests_dir), str(tmp_path / "out"))
    assert (tmp_path / "out" / "conftest.py").exists()


# ----------------------------------------------------------------------------------------------
# Files that are left behind
# ----------------------------------------------------------------------------------------------


def test_nothing_is_stale_right_after_a_copy(tests_dir, tmp_path):
    destination = tmp_path / "out"
    copy_tests(tests_dir, destination)
    assert stale_files(tests_dir, destination) == []


def test_a_test_file_removed_from_the_tests_folder_is_reported(tests_dir, tmp_path):
    destination = tmp_path / "out"
    copy_tests(tests_dir, destination)
    (tests_dir / "test_api.py").unlink()
    (tests_dir / "TestFiles" / "sub" / "more.txt").unlink()
    assert stale_files(tests_dir, destination) == [
        "TestFiles/sub/more.txt",
        "test_api.py",
    ]


def test_files_from_an_earlier_copy_of_a_now_excluded_folder_are_reported(
    tests_dir, tmp_path
):
    destination = make(
        tmp_path / "out",
        {
            "offline/test_codec.py": "x",
            "baseline/pickles/table.pkl": "p",
            "conftest.py": "c",
        },
    )
    assert stale_files(tests_dir, destination) == [
        "baseline/pickles/table.pkl",
        "offline/test_codec.py",
    ]


def test_caches_in_the_destination_are_not_reported(tests_dir, tmp_path):
    destination = make(
        tmp_path / "out",
        {
            "conftest.py": "c",
            "__pycache__/x.pyc": "b",
            ".pytest_cache/y": "y",
            "TestFiles/.pytest_cache/z": "z",
            "mod.pyc": "b",
        },
    )
    assert stale_files(tests_dir, destination) == []


def test_an_empty_or_missing_destination_has_nothing_stale(tests_dir, tmp_path):
    assert stale_files(tests_dir, tmp_path / "does-not-exist") == []
