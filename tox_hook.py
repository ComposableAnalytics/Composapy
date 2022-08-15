import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

from termcolor import colored
from wheel_filename import parse_wheel_filename, ParsedWheelFilename
import jupytext
from pathlib import Path
from tfs_utils import (
    grant_permissions,
    CopyFileToSolutionException,
    tfs_command,
    add_to_csproj,
    remove_from_csproj,
)
from _const import (
    DATALABSERVICE_STATIC_DIR,
    COMPOSAPY_ROOT_DIR,
    COMPOSAPY_DOCS_README_IPYNB,
    COMPOSAPY_SPHINX_DOCS_DIR,
    DATALABSERVICE_WHEELS_DIR,
    COMPOSAPY_TESTS_DIR,
    DATALAB_DLL_DIR,
    COMPOSABLE_TESTDATA_COMPOSAPY_DIR,
)

os.environ["DATALAB_DLL_DIR"] = str(DATALAB_DLL_DIR)

os.system("color")  # for colored text


def sync_project():
    _write_static_artifacts()

    _compile_local_docs()
    _compile_sphinx_docs()

    _write_composapy_wheel_and_add_to_tfs()
    _add_dependency_wheels_tfs()

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


def _write_composapy_wheel_and_add_to_tfs() -> None:
    print("Copying Composapy wheel to static wheels dir and adding to tfs... ", end="")

    try:
        # grab .whl from most recent tox build
        wheel = sorted(COMPOSAPY_ROOT_DIR.joinpath(".tox", "dist").glob("*.whl"))[0]

        # grab all .whl from composable datalabservice static wheels directory
        old_wheels = sorted(DATALABSERVICE_WHEELS_DIR.glob("composapy-*.whl"))

        # add new composapy wheel to local save_dir
        try:
            shutil.copy(wheel, DATALABSERVICE_WHEELS_DIR)
            grant_permissions(DATALABSERVICE_WHEELS_DIR)
        except Exception:
            raise CopyFileToSolutionException(
                f"Failed to copy wheel from {wheel} to {DATALABSERVICE_WHEELS_DIR}."
            )

        print("Adding Composapy wheel to tfs...")

        # add new composapy wheel to tfs tracking
        tfs_command(DATALABSERVICE_WHEELS_DIR, "add", wheel.name)

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
                    tfs_command(DATALABSERVICE_WHEELS_DIR, "undo", old_wheel.name)
                except Exception:
                    pass
                try:
                    tfs_command(DATALABSERVICE_WHEELS_DIR, "delete", old_wheel.name)
                except Exception:
                    pass
                try:
                    remove_from_csproj(old_wheel.name)
                    os.remove(Path(old_wheel))
                except Exception:
                    pass  #  if tfs did not fail to remove the file, this is expected
    except:
        print(colored("failed.", "red"))
        raise

    print(colored("done.", "green"))


def _add_dependency_wheels_tfs() -> None:
    # Goes through all wheels in ComposableAnalytics.DataLabService\static\wheels save_dir and
    # attempts to add them to tfs tracking source. This will pick up any manually added wheels
    # and fail silently with a return code of 1 if they already exist.
    print("Adding dependency wheels to tfs... ", end="")

    try:
        tfs_command(DATALABSERVICE_STATIC_DIR, "add", "*", "/recursive")
    except:
        print(colored("failed.", "red"))

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


@dataclass
class WheelUpgrade:
    project_name: str
    old_version: str
    new_version: str
    old_wheel: ParsedWheelFilename
    new_wheel: ParsedWheelFilename

    def make_upgrade(self):
        try:
            print(
                f"Upgrading {self.project_name} from {self.old_version} to "
                f"{self.new_version}... ",
                end="",
            )

            try:
                tfs_command(DATALABSERVICE_WHEELS_DIR, "delete", str(self.old_wheel))
                remove_from_csproj(str(self.old_wheel))
                DATALABSERVICE_WHEELS_DIR.joinpath(str(self.old_wheel)).unlink()

                tfs_command(DATALABSERVICE_WHEELS_DIR, "add", str(self.new_wheel))
            except:
                tfs_command(DATALABSERVICE_WHEELS_DIR, "undo", str(self.old_wheel))
                raise

            print(colored("done."), "green")
        except:
            print(colored("failed.", "red"))


def upgrade_wheels(new_wheels_dir: Path):
    new_wheel_names = [wheel.name for wheel in new_wheels_dir.glob("*.whl")]
    current_wheels_dir = DATALABSERVICE_WHEELS_DIR
    current_wheel_names = [wheel.name for wheel in current_wheels_dir.glob("*.whl")]

    current_wheels = [parse_wheel_filename(wheel) for wheel in current_wheel_names]
    new_wheels = [parse_wheel_filename(wheel) for wheel in new_wheel_names]

    current_wheels_dict = {wheel.project: wheel for wheel in current_wheels}
    new_wheels_dict = {wheel.project: wheel for wheel in new_wheels}

    upgrades = {
        key: WheelUpgrade(
            project_name=key,
            old_version=val.version,
            new_version=new_wheels_dict[key].version,
            old_wheel=val,
            new_wheel=new_wheels_dict[key],
        )
        for key, val in current_wheels_dict.items()
        if new_wheels_dict.get(key) and new_wheels_dict[key].version != val.version
    }

    for key, val in upgrades.items():
        val.make_upgrade()


if __name__ == "__main__":
    OPTIONS = ["-sync-project", "-docs"]

    if len(sys.argv) == 1:
        raise Exception("Must include command arg (build, docs, etc.).")
    arg = sys.argv[1]

    if "options" in arg:
        print(", ".join(OPTIONS))

    elif "sync-project" in arg:
        sync_project()

    elif "docs" in arg:
        _compile_local_docs()
        _compile_sphinx_docs()

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
