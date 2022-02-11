import os
from dotenv import dotenv_values
from pathlib import Path
import shutil
import subprocess


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


composapy_root = Path(__file__).parent
product_root = Path(dotenv_values(".local.env").get("ROOT_PATH_COMPOSABLE")).joinpath(
    "Product"
)
datalabservice_static_dir = product_root.joinpath(
    "CompAnalytics.DataLabService", "static"
)
tf_exe_path = Path(dotenv_values(".local.env").get("TF_EXE_PATH"))

print(f"{tf_exe_path}")

print("Copying composapy-readme.ipynb...")
notebook_src = composapy_root.joinpath("composapy-readme.ipynb")
notebook_dest = datalabservice_static_dir.joinpath(notebook_src.name)
shutil.copy(notebook_src, notebook_dest)
grant_permissions(notebook_dest)

print("Copying tests...")
tests_src = composapy_root.joinpath("tests")
tests_dest = product_root.joinpath("UnitTests", "TestData", "composapy")
shutil.copytree(tests_src, tests_dest, dirs_exist_ok=True)
grant_permissions(tests_dest)

print("Copying wheel...")
wheel_src = sorted(composapy_root.joinpath(".tox", "dist").glob("*.whl"))[0]
wheel_dest = datalabservice_static_dir.joinpath("wheels")

try:
    old_wheel = sorted(wheel_dest.glob("composapy-*.whl"))[0]
    os.remove(old_wheel)
except IndexError:
    print(
        "Could not find old version of composapy... updating with newly built composapy wheel."
    )

shutil.copy(wheel_src, wheel_dest)
grant_permissions(wheel_dest)

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
