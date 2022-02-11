import os
from dotenv import dotenv_values
from pathlib import Path
import shutil
import subprocess


class CopyFileToSolutionException(Exception):
    pass


def grant_permissions(path: Path) -> None:
    subprocess.check_output(
        ["icacls", f"{path}", "/grant", "Everyone:F", "/t"],
        stderr=subprocess.STDOUT,
    )


def add_to_tfs(path: Path, recursive: bool = False) -> None:
    subprocess.check_output(
        [
            f"{tf_exe_path}",
            "add",
            f"{path}",
            f"{'/recursive' if recursive else ''}",
        ],
        stderr=subprocess.STDOUT,
    )


composapy_root_dir = Path(__file__).parent
composable_analytics_product_dir = composapy_root_dir.parent.parent.joinpath("Product")

datalabservice_static_dir = composable_analytics_product_dir.joinpath(
    "CompAnalytics.DataLabService", "static"
)
tf_exe_path = Path(dotenv_values(".local.env").get("TF_EXE_PATH"))


print("Copying composapy-readme.ipynb...")
notebook_src = composapy_root_dir.joinpath("composapy-readme.ipynb")
notebook_dest = datalabservice_static_dir.joinpath(notebook_src.name)
try:
    shutil.copy(notebook_src, notebook_dest)
except Exception:
    raise CopyFileToSolutionException(
        f"Failed to copy composapy-readme.ipynb from {notebook_src} to {notebook_dest}."
    )
grant_permissions(notebook_dest)


print("Copying tests...")
tests_src = composapy_root_dir.joinpath("tests")
tests_dest = composable_analytics_product_dir.joinpath(
    "UnitTests", "TestData", "composapy"
)
try:
    shutil.copytree(tests_src, tests_dest, dirs_exist_ok=True)
except Exception:
    raise CopyFileToSolutionException(
        f"Failed to copy tests from {tests_src} to {tests_dest}."
    )
grant_permissions(tests_dest)


print("Copying wheel...")
wheel_src = sorted(composapy_root_dir.joinpath(".tox", "dist").glob("*.whl"))[0]
wheel_dest = datalabservice_static_dir.joinpath("wheels")

try:
    old_wheel = sorted(wheel_dest.glob("composapy-*.whl"))[0]
    os.remove(old_wheel)
except IndexError:
    print(
        "Could not find old version of composapy... updating with newly built composapy wheel."
    )

try:
    shutil.copy(wheel_src, wheel_dest)
    grant_permissions(wheel_dest)
except Exception:
    raise CopyFileToSolutionException(
        f"Failed to copy wheel from {wheel_src} to {wheel_dest}."
    )


add_to_tfs(datalabservice_static_dir.joinpath("*"), recursive=True)  #  static/*
add_to_tfs(tests_dest.joinpath("test_*.py"))  #  tests/test_*.py
add_to_tfs(tests_dest.joinpath("conftest.py"))  #  tests/conftest.py
add_to_tfs(tests_dest.joinpath("__init__.py"))  #  tests/__init__.py
add_to_tfs(tests_dest.joinpath(".test.env"))  #  tests/.test.env
add_to_tfs(tests_dest.joinpath("TestFiles"), recursive=True)  #  tests/TestFiles/*


## cleanup unwanted directory
subprocess.check_output(
    [
        f"{tf_exe_path}",
        "undo",
        f"{tests_dest.joinpath('TestFiles', '.pytest_cache')}",
        "/recursive",
    ],
    stderr=subprocess.STDOUT,
)
