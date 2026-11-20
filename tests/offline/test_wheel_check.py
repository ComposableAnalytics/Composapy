"""Offline tests for tools/wheel_check.py: files in a built wheel that the source folder no longer has."""

import ast
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from tools.wheel_check import unexpected_files  # noqa: E402


def make_package(root, files):
    for name in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    return root


def make_wheel(path, names):
    with zipfile.ZipFile(path, "w") as z:
        for name in names:
            z.writestr(name, "x")
    return path


def test_a_wheel_that_matches_its_source_has_nothing_unexpected(tmp_path):
    package = make_package(
        tmp_path / "composapy",
        ["__init__.py", "session.py", "static/readme.ipynb", "_wire/operations.json"],
    )
    wheel = make_wheel(
        tmp_path / "w.whl",
        [
            "composapy/__init__.py",
            "composapy/session.py",
            "composapy/static/readme.ipynb",
            "composapy/_wire/operations.json",
            "composapy-1.0.0.dist-info/RECORD",
        ],
    )
    assert unexpected_files(wheel, package) == []


def test_a_module_deleted_from_the_source_but_still_in_the_wheel_is_reported(tmp_path):
    package = make_package(tmp_path / "composapy", ["__init__.py", "session.py"])
    wheel = make_wheel(
        tmp_path / "w.whl",
        [
            "composapy/__init__.py",
            "composapy/session.py",
            "composapy/bindings.py",
            "composapy/stream.py",
        ],
    )
    assert unexpected_files(wheel, package) == [
        "composapy/bindings.py",
        "composapy/stream.py",
    ]


def test_a_file_in_a_sub_folder_is_reported_too(tmp_path):
    package = make_package(tmp_path / "composapy", ["__init__.py", "key/__init__.py"])
    wheel = make_wheel(
        tmp_path / "w.whl",
        [
            "composapy/__init__.py",
            "composapy/key/__init__.py",
            "composapy/key/old_models.py",
        ],
    )
    assert unexpected_files(wheel, package) == ["composapy/key/old_models.py"]


def test_a_file_the_wheel_leaves_out_is_not_reported(tmp_path):
    package = make_package(tmp_path / "composapy", ["__init__.py", "notes.txt"])
    wheel = make_wheel(tmp_path / "w.whl", ["composapy/__init__.py"])
    assert unexpected_files(wheel, package) == []


def test_caches_are_ignored_on_both_sides(tmp_path):
    package = make_package(
        tmp_path / "composapy",
        ["__init__.py", "__pycache__/session.cpython-311.pyc", "mod.pyc"],
    )
    wheel = make_wheel(
        tmp_path / "w.whl",
        [
            "composapy/__init__.py",
            "composapy/__pycache__/old.cpython-311.pyc",
            "composapy/old.pyc",
        ],
    )
    assert unexpected_files(wheel, package) == []


def test_the_dist_info_folder_is_not_checked(tmp_path):
    package = make_package(tmp_path / "composapy", ["__init__.py"])
    wheel = make_wheel(
        tmp_path / "w.whl",
        [
            "composapy/__init__.py",
            "composapy-1.0.0.dist-info/METADATA",
            "composapy-1.0.0.dist-info/RECORD",
        ],
    )
    assert unexpected_files(wheel, package) == []


def test_a_package_next_to_composapy_is_reported(tmp_path):
    # `packages = find:` once installed a top-level tests package (with the offline tests) into every environment
    package = make_package(tmp_path / "composapy", ["__init__.py"])
    wheel = make_wheel(
        tmp_path / "w.whl",
        [
            "composapy/__init__.py",
            "tests/__init__.py",
            "tests/offline/test_codec.py",
            "other/thing.py",
        ],
    )
    assert unexpected_files(wheel, package) == [
        "other/thing.py",
        "tests/__init__.py",
        "tests/offline/test_codec.py",
    ]


def test_a_top_level_module_file_is_reported_too(tmp_path):
    package = make_package(tmp_path / "composapy", ["__init__.py"])
    wheel = make_wheel(tmp_path / "w.whl", ["composapy/__init__.py", "conftest.py"])
    assert unexpected_files(wheel, package) == ["conftest.py"]


def test_the_real_package_has_no_net_modules_to_ship():
    # stream.py and bindings.py once leaked into the wheel, and both imported .NET. stream.py is gone for good.
    # bindings.py is back as a plain dictionary of timeouts, so it may exist only while it imports nothing at all.
    assert not (REPO_ROOT / "composapy" / "stream.py").exists()
    bindings = REPO_ROOT / "composapy" / "bindings.py"
    if bindings.exists():
        tree = ast.parse(bindings.read_text(encoding="utf-8"))
        assert not [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
