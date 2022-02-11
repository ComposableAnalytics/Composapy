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


def tfs_command(path: Path, command: str, recursive: bool = False) -> None:
    subprocess.check_output(
        [
            f"{tf_exe_path}",
            command,
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
    os.remove(Path(old_wheel))
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


tfs_command(datalabservice_static_dir.joinpath("*"), "add", recursive=True)  #  static/*
tfs_command(tests_dest.joinpath("test_*.py"), "add")  #  tests/test_*.py
tfs_command(tests_dest.joinpath("conftest.py"), "add")  #  tests/conftest.py
tfs_command(tests_dest.joinpath("__init__.py"), "add")  #  tests/__init__.py
tfs_command(tests_dest.joinpath(".test.env"), "add")  #  tests/.test.env
tfs_command(
    tests_dest.joinpath("TestFiles"), "add", recursive=True
)  #  tests/TestFiles/*

## cleanup unwanted directory
tfs_command(tests_dest.joinpath("TestFiles", ".pytest_cache"), "undo", recursive=True)
