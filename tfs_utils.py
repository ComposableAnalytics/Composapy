import os
import shutil
import subprocess
from pathlib import Path

from dotenv import dotenv_values

COMPOSAPY_ROOT_DIR = Path(__file__).parent
COMP_APP_PROD_DIR = COMPOSAPY_ROOT_DIR.parent.parent.joinpath("Product")
DATALAB_SERVICE_STATIC_DIR = COMP_APP_PROD_DIR.joinpath(
    "CompAnalytics.DataLabService", "static"
)
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


def update_composapy_readme_artifacts(readme_artifacts: list[Path]) -> None:
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

    if len(old_wheels) == 0:
        return

    # remove old composapy wheels from tfs tracking and local save_dir after new wheel was
    # successfully loaded
    for old_wheel in old_wheels:
        if old_wheel.name != wheel.name:
            tfs_command(wheel_dest, "delete", old_wheel.name)
            try:
                os.remove(Path(old_wheel))  # sometimes tfs fails to remove the file
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
