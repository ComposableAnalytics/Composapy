import os
import shutil
import subprocess
import sys

from termcolor import colored
from wheel_filename import parse_wheel_filename
import jupytext
import zipfile
import hashlib
from tools.test_data import copy_tests, stale_files
from tools.wheel_check import unexpected_files
from tfs_utils import (
    grant_permissions,
    CopyFileToSolutionException,
    tfs_command,
    tfs_files_info,
    remove_composapy_csproj_items,
    TfsWheel,
    LocalWheel,
)
from _const import (
    DATALABSERVICE_STATIC_DIR,
    COMPOSAPY_ROOT_DIR,
    COMPOSAPY_DOCS_README_IPYNB,
    COMPOSAPY_SPHINX_DOCS_DIR,
    COMPOSAPY_TESTS_DIR,
    COMPOSAPY_CONSTRAINTS_DIR,
    COMPOSABLE_TESTDATA_COMPOSAPY_DIR,
    DATALABSERVICE_WHEELS_DIR,
    _DATALAB_SUPPORTED_PYTHON_VERSIONS,
)

os.system("color")  # for colored text


def sync_project():
    _refresh_operations()
    _refresh_constraints()
    sync_composapy()

    _write_static_artifacts()

    compile_docs()

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
            "-a",
            "-E",
            "-b",
            "html",
            "source",
            "build",
        ],
        cwd=(COMPOSAPY_SPHINX_DOCS_DIR.as_posix()),
        capture_output=True,
    )

    try:
        _build_run.check_returncode()
    except:
        print(colored("failed.", "red"))

        print(_build_run.stdout.decode("utf-8"))
        print(_build_run.stderr.decode("utf-8"))

        raise

    print(colored("done.", "green"))


def _refresh_operations():
    print("Regenerating operations manifest... ", end="")
    try:
        subprocess.run(
            [
                sys.executable,
                str(COMPOSAPY_ROOT_DIR / "tools" / "generate_operations.py"),
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        print(colored("failed.", "red"))
        raise
    print(colored("done.", "green"))


def _refresh_constraints():
    print("Refreshing constraints files... ", end="")
    try:
        subprocess.run(
            [
                sys.executable,
                str(COMPOSAPY_ROOT_DIR / "tools" / "refresh_constraints.py"),
                str(DATALABSERVICE_STATIC_DIR),
                str(COMPOSAPY_CONSTRAINTS_DIR),
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        print(colored("failed.", "red"))
        raise
    print(colored("done.", "green"))


def sync_composapy():
    new_wheel = _build_wheel()
    if _wheel_version_guard(new_wheel):
        print("Already up to date; nothing to do.")
        return

    files_info = tfs_files_info()
    for wheel in files_info:
        if wheel.local_path.name.startswith("composapy-"):
            tfs_wheel = TfsWheel(
                tfs_file=wheel,
                wheel_info=parse_wheel_filename(wheel.local_path),
            )
            tfs_wheel.remove()
    remove_composapy_csproj_items()

    LocalWheel(path=new_wheel).add(_DATALAB_SUPPORTED_PYTHON_VERSIONS)


def _build_wheel():
    print("Building wheel... ", end="")
    dist = COMPOSAPY_ROOT_DIR / "dist"
    for old in dist.glob("composapy-*.whl"):  # so the only wheel left is the new one
        old.unlink()
    shutil.rmtree(
        COMPOSAPY_ROOT_DIR / "build", ignore_errors=True
    )  # setuptools keeps files deleted from the source in build/lib
    run = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist)],
        cwd=COMPOSAPY_ROOT_DIR,
        capture_output=True,
    )
    if run.returncode != 0:
        print(colored("failed.", "red"))
        print(run.stdout.decode("utf-8"))
        print(run.stderr.decode("utf-8"))
        raise SystemExit(1)

    wheel = next(dist.glob("composapy-*.whl"))
    stale = unexpected_files(wheel, COMPOSAPY_ROOT_DIR / "composapy")
    if stale:
        print(colored("failed.", "red"))
        raise SystemExit(
            "The wheel contains files the source no longer has: " + ", ".join(stale)
        )
    print(colored("done.", "green"))
    return wheel


def _wheel_version_guard(new_wheel):
    new = parse_wheel_filename(new_wheel)
    for existing in DATALABSERVICE_WHEELS_DIR.glob("composapy-*.whl"):
        if parse_wheel_filename(existing).version == new.version:
            if _wheel_contents(existing) == _wheel_contents(new_wheel):
                return True
            raise SystemExit(
                f"{existing.name} already exists with different contents; bump the version "
                f"in setup.cfg (or use a .devN version) and run again."
            )
    return False


def _wheel_contents(path):
    with zipfile.ZipFile(path) as z:
        return {
            n: hashlib.sha256(z.read(n)).hexdigest()
            for n in z.namelist()
            if not n.endswith(("/", ".dist-info/RECORD", ".dist-info/WHEEL"))
        }


def _write_unittests_test_data() -> None:
    print("Writing unit test data... ", end="")

    # add/replace tests in local save_dir
    try:
        copy_tests(COMPOSAPY_TESTS_DIR, COMPOSABLE_TESTDATA_COMPOSAPY_DIR)
    except Exception:
        print(colored("failed.", "red"))

        raise CopyFileToSolutionException(
            f"Failed to copy tests from {COMPOSAPY_TESTS_DIR} to "
            f"{COMPOSABLE_TESTDATA_COMPOSAPY_DIR}."
        )

    print(colored("done.", "green"))

    for path in stale_files(COMPOSAPY_TESTS_DIR, COMPOSABLE_TESTDATA_COMPOSAPY_DIR):
        print(
            colored(
                f"  {path} is in TestData but not in tests; `tf delete` it if it was removed on purpose.",
                "yellow",
            )
        )


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


if __name__ == "__main__":
    OPTIONS = ["-sync-project", "-sync-composapy", "-docs"]

    if len(sys.argv) == 1:
        raise Exception("Must include command arg (build, docs, etc.).")

    arg = sys.argv[1]

    if "options" in arg:
        print(", ".join(OPTIONS))

    elif "sync-project" in arg:
        sync_project()

    elif "sync-composapy" in arg:
        sync_composapy()

    elif "docs" in arg:
        compile_docs()

    else:
        print(f"{arg} is not a valid option.")
