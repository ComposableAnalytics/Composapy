import os
import shutil
import subprocess
import sys

from termcolor import colored
from wheel_filename import parse_wheel_filename
import jupytext
from pathlib import Path
from tfs_utils import (
    grant_permissions,
    CopyFileToSolutionException,
    tfs_command,
    tfs_files_info,
    TfsWheel,
    LocalWheel,
    WheelUpgrade,
    TfsFile,
)
from _const import (
    DATALABSERVICE_STATIC_DIR,
    COMPOSAPY_ROOT_DIR,
    COMPOSAPY_DOCS_README_IPYNB,
    COMPOSAPY_SPHINX_DOCS_DIR,
    COMPOSAPY_TESTS_DIR,
    DATALAB_DLL_DIR,
    COMPOSABLE_TESTDATA_COMPOSAPY_DIR,
    DATALABSERVICE_WHEELS_DIR,
)

os.environ["DATALAB_DLL_DIR"] = str(DATALAB_DLL_DIR)

os.system("color")  # for colored text


def sync_project():
    _write_static_artifacts()

    compile_docs()

    _upgrade_composapy_wheel()

    _write_unittests_test_data()
    _add_test_data_tfs()


def _write_static_artifacts() -> None:
    print("Copying composapy resource to local save_dir and adding to tfs... ", end="")

    try:
        # these get put into every datalab so that users can read and learn about composapy
        readme_artifacts = [
            COMPOSAPY_DOCS_README_IPYNB,
            COMPOSAPY_ROOT_DIR.joinpath("docs", "simple-dataflow.json"),
        ]
        for artifact in readme_artifacts:
            destination_path = DATALABSERVICE_STATIC_DIR.joinpath(artifact.name)
            shutil.copy(artifact, destination_path)
            grant_permissions(destination_path)
    except:
        print(colored("failed.", "red"))
        raise

    print(colored("done.", "green"))


def compile_docs():
    _compile_local_docs()
    _compile_sphinx_docs()


def _compile_local_docs():
    print("Writing composapy-readme notebook as markdown... ", end="")

    try:
        # composapy-readme.ipynb is the source of truth, not README.md
        # any changes to README.md get overwritten with this command
        nb = jupytext.read(COMPOSAPY_DOCS_README_IPYNB)
        jupytext.write(nb, "README.md")
    except:
        print(colored("failed.", "red"))
        raise

    print(colored("done.", "green"))


def _compile_sphinx_docs():
    print("Rebuilding sphinx documentation... ", end="")

    # compiles the new readthedocs documentation from docstrings,
    _build_run = subprocess.run(
        [
            "sphinx-build",
            "-b",
            "html",
            "source",
            "build",
        ],
        cwd=(COMPOSAPY_SPHINX_DOCS_DIR.as_posix()),
        capture_output=True,
    )

    # cleans the previous build,
    _clean_run = subprocess.run(
        ["make", "clean"],
        cwd=(COMPOSAPY_SPHINX_DOCS_DIR.as_posix()),
        capture_output=True,
    )

    # makes new html files
    _make_run = subprocess.run(
        ["make", "html"],
        cwd=(COMPOSAPY_SPHINX_DOCS_DIR.as_posix()),
        capture_output=True,
    )

    try:
        _build_run.check_returncode()
        _clean_run.check_returncode()
        _make_run.check_returncode()
    except:
        print(colored("failed.", "red"))

        print(_build_run.stdout.decode("utf-8"))
        print(_build_run.stderr.decode("utf-8"))
        print(_clean_run.stdout.decode("utf-8"))
        print(_clean_run.stderr.decode("utf-8"))
        print(_make_run.stdout.decode("utf-8"))
        print(_make_run.stderr.decode("utf-8"))

        raise

    print(colored("done.", "green"))


def _write_unittests_test_data() -> None:
    print("Writing unit test data... ", end="")

    # add/replace tests in local save_dir
    try:
        shutil.copytree(
            COMPOSAPY_TESTS_DIR, COMPOSABLE_TESTDATA_COMPOSAPY_DIR, dirs_exist_ok=True
        )
    except Exception:
        print(colored("failed.", "red"))

        raise CopyFileToSolutionException(
            f"Failed to copy tests from {COMPOSAPY_TESTS_DIR} to "
            f"{COMPOSABLE_TESTDATA_COMPOSAPY_DIR}."
        )

    print(colored("done.", "green"))


def _add_test_data_tfs() -> None:
    """TODO: In the future, if ever refactoring something around tests, probably refactor this
    as well."""
    print("Adding unit test data to tfs... ", end="")

    try:
        grant_permissions(COMPOSABLE_TESTDATA_COMPOSAPY_DIR)

        # add specific tfs test file dependencies here
        tfs_command(COMPOSABLE_TESTDATA_COMPOSAPY_DIR, "add", "test_*.py")
        tfs_command(COMPOSABLE_TESTDATA_COMPOSAPY_DIR, "add", "conftest.py")
        tfs_command(COMPOSABLE_TESTDATA_COMPOSAPY_DIR, "add", "__init__.py")
        tfs_command(COMPOSABLE_TESTDATA_COMPOSAPY_DIR, "add", ".test.env")
        tfs_command(COMPOSABLE_TESTDATA_COMPOSAPY_DIR, "add", "TestFiles", "/recursive")

        ## cleanup unwanted cache from previous command
        tfs_command(
            COMPOSABLE_TESTDATA_COMPOSAPY_DIR.joinpath("TestFiles"),
            "undo",
            ".pytest_cache",
            "/recursive",
        )
    except:
        print(colored("failed.", "red"))
        raise

    print(colored("done.", "green"))


def upgrade_wheels(new_wheels_dir: Path):
    """Loads the wheels tracked by tfs in the datalabservice static wheels directory in addition
    to the wheels at the specified new_wheels_dir location and attempts to match any previous
    wheel packages before upgrading."""

    files_info = tfs_files_info()  # lazily loaded
    tfs_wheels = {}
    for wheel in files_info:
        tfs_wheel = TfsWheel(
            tfs_file=TfsFile(**wheel.__dict__),
            wheel_info=parse_wheel_filename(wheel.local_path),
        )
        tfs_wheels[tfs_wheel.wheel_info.project] = tfs_wheel

    local_wheels = {}
    for wheel in DATALABSERVICE_WHEELS_DIR.glob("*.whl"):
        local_wheel = LocalWheel(path=wheel)
        local_wheels[local_wheel.wheel_info.project] = local_wheel

    new_wheels = {}
    for wheel in new_wheels_dir.glob("*.whl"):
        new_wheel = LocalWheel(path=wheel)
        new_wheels[new_wheel.wheel_info.project] = new_wheel

    for key, val in new_wheels.items():
        WheelUpgrade(
            tfs_wheel=tfs_wheels.get(key),
            local_wheel=local_wheels.get(key),
            new_wheel=val,
        ).make_upgrade()


def _upgrade_composapy_wheel() -> None:
    wheel_dir = COMPOSAPY_ROOT_DIR.joinpath(".tox", "dist")
    upgrade_wheels(wheel_dir)


if __name__ == "__main__":
    OPTIONS = ["-sync-project", "-docs", "-upgrade-wheels"]

    if len(sys.argv) == 1:
        raise Exception("Must include command arg (build, docs, etc.).")

    arg = sys.argv[1]

    if "options" in arg:
        print(", ".join(OPTIONS))

    elif "sync-project" in arg:
        sync_project()

    elif "docs" in arg:
        compile_docs()

    # tox.ini manages the initial pip wheels download, which then passes
    # the path of the downloaded wheels to option.
    elif "upgrade-wheels" in arg:
        if not len(sys.argv) == 3:
            raise Exception(
                "Must include path to directory where wheels are downloaded."
            )

        temp_wheels_dir = Path(sys.argv[2])
        temp_wheels_dir.mkdir(parents=True, exist_ok=True)

        upgrade_wheels(temp_wheels_dir)

    else:
        print(f"{arg} is not a valid option.")
