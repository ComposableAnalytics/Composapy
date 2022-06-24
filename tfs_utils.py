import os
import shutil
import subprocess
from pathlib import Path, WindowsPath
from dotenv import dotenv_values
from typing import List
import xml.etree.ElementTree as et


COMPOSAPY_ROOT_DIR = Path(__file__).parent
COMP_APP_PROD_DIR = COMPOSAPY_ROOT_DIR.parent.parent.joinpath("Product")

DATALAB_SERVICE_DIR = COMP_APP_PROD_DIR.joinpath("CompAnalytics.DataLabService")
DATALAB_SERVICE_STATIC_DIR = DATALAB_SERVICE_DIR.joinpath("static")
DATALAB_SERVICE_CSPROJ = DATALAB_SERVICE_DIR.joinpath(
    "CompAnalytics.DataLabService.csproj"
)
XML_NAMESPACE = "http://schemas.microsoft.com/developer/msbuild/2003"  # for xml nodes
et.register_namespace("", XML_NAMESPACE)

TF_EXE_PATH = Path(dotenv_values(".local.env").get("TF_EXE_PATH"))


class CopyFileToSolutionException(Exception):
    pass


class TfsException(Exception):
    pass


def grant_permissions(path: Path) -> None:
    subprocess.check_output(
        ["icacls", f"{path}", "/grant", "Everyone:F", "/t"],
        stderr=subprocess.STDOUT,
    )


def tfs_command(cwd: Path, *args) -> None:
    run = subprocess.run([f"{TF_EXE_PATH}", *args], cwd=cwd, capture_output=True)
    if run.returncode > 1:
        raise TfsException(
            f"Return code greater than 1, failed tf.exe with args: {args} and cwd: {cwd}."
            f"Return Code: {run.returncode}\n"
            f"StdOut: {run.stdout}\n"
            f"StdErr: {run.stderr}\n"
        )


def update_composapy_readme_artifacts(readme_artifacts: List[Path]) -> None:
    for artifact in readme_artifacts:
        destination_path = DATALAB_SERVICE_STATIC_DIR.joinpath(artifact.name)
        shutil.copy(artifact, destination_path)
        grant_permissions(destination_path)


def update_composapy_wheel(wheel: Path) -> None:
    wheel_dest = DATALAB_SERVICE_STATIC_DIR.joinpath("wheels")
    old_wheels = sorted(wheel_dest.glob("composapy-*.whl"))

    # add new composapy wheel to local save_dir
    try:
        shutil.copy(wheel, wheel_dest)
        grant_permissions(wheel_dest)
    except Exception:
        raise CopyFileToSolutionException(
            f"Failed to copy wheel from {wheel} to {wheel_dest}."
        )

    # add new composapy wheel to tfs tracking
    tfs_command(wheel_dest, "add", wheel.name)

    # add new composapy wheel to csproj
    add_to_csproj(wheel.name)

    # return if there are no wheels to remove from tfs and the csproj
    if len(old_wheels) == 0:
        return

    # it is easier and faster to try deleting and undoing the file in tfs than it is to check for
    # what state the file is in and doing the appropriate action.
    for old_wheel in old_wheels:
        if old_wheel.name != wheel.name:
            try:
                tfs_command(wheel_dest, "undo", old_wheel.name)
            except Exception:
                pass
            try:
                tfs_command(wheel_dest, "delete", old_wheel.name)
            except Exception:
                pass
            try:
                remove_from_csproj(old_wheel.name)
                os.remove(Path(old_wheel))
            except Exception:
                pass  #  if tfs did not fail to remove the file, this is expected


def update_static_wheel_deps() -> None:
    tfs_command(DATALAB_SERVICE_STATIC_DIR, "add", "*", "/recursive")


def update_composapy_tests(tests: Path) -> None:
    tests_dest = COMP_APP_PROD_DIR.joinpath("UnitTests", "TestData", "composapy")

    # add/replace tests in local save_dir
    try:
        shutil.copytree(tests, tests_dest, dirs_exist_ok=True)
    except Exception:
        raise CopyFileToSolutionException(
            f"Failed to copy tests from {tests} to {tests_dest}."
        )
    grant_permissions(tests_dest)

    # add specific tfs test file dependencies here
    tfs_command(tests_dest, "add", "test_*.py")  # tests/test_*.py
    tfs_command(tests_dest, "add", "conftest.py")  # tests/conftest.py
    tfs_command(tests_dest, "add", "__init__.py")  # tests/__init__.py
    tfs_command(tests_dest, "add", ".test.env")  # tests/.test.env
    tfs_command(tests_dest, "add", "TestFiles", "/recursive")  # tests/TestFiles/*

    ## cleanup unwanted cache from previous command
    tfs_command(tests_dest.joinpath("TestFiles"), "undo", ".pytest_cache", "/recursive")


def add_to_csproj(wheel: str) -> None:
    tree = et.parse(DATALAB_SERVICE_CSPROJ)
    root = tree.getroot()

    # this selects the ItemGroup element with sub-element None that has attribute Include
    item_group = root.find(
        f".//{{{XML_NAMESPACE}}}ItemGroup/{{{XML_NAMESPACE}}}None[@Include]/.."
    )

    # add a new None element with an Include attribute equal to the relative wheel path
    relative_wheel_path = str(WindowsPath(f"static/wheels/{wheel}"))
    wheel_element = item_group.find(
        f".//{{{XML_NAMESPACE}}}None[@Include='{relative_wheel_path}']"
    )
    # return if element already exists, no need to add it again. be sure to check for None,
    # __bool__() checks the length of contained nodes to discern true/false
    if wheel_element is not None:
        return

    new_wheel_element = et.Element(f"{{{XML_NAMESPACE}}}None")
    new_wheel_element.set("Include", relative_wheel_path)

    # add the None element to the appropriate ItemGroup element
    item_group.append(new_wheel_element)

    # update the csproj with changes
    tree.write(DATALAB_SERVICE_CSPROJ)


def remove_from_csproj(wheel: str) -> None:
    tree = et.parse(DATALAB_SERVICE_CSPROJ)
    root = tree.getroot()

    # this selects the ItemGroup element with sub-element None that has attribute Include
    item_group = root.find(
        f".//{{{XML_NAMESPACE}}}ItemGroup/{{{XML_NAMESPACE}}}None[@Include]/.."
    )

    # this selects the None element with Include attribute equal to relative wheel path
    relative_wheel_path = str(WindowsPath(f"static/wheels/{wheel}"))
    wheel_element = item_group.find(
        f".//{{{XML_NAMESPACE}}}None[@Include='{relative_wheel_path}']"
    )

    # check element exists before removing. be sure to check for None, __bool__() checks the
    # length of contained nodes to discern true/false
    if wheel_element is not None:
        item_group.remove(wheel_element)

    # update the csproj with changes
    tree.write(DATALAB_SERVICE_CSPROJ)
