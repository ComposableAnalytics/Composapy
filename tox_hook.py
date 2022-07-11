import os
import sys
from contextlib import contextmanager

import jupytext
from pathlib import Path
from tfs_utils import (
    update_composapy_wheel,
    update_composapy_tests,
    update_composapy_readme_artifacts,
    update_static_wheel_deps,
)


COMPOSAPY_ROOT_DIR = Path(__file__).parent
COMPOSAPY_README_IPYNB = COMPOSAPY_ROOT_DIR.joinpath("docs", "composapy-readme.ipynb")


def build():
    print("Copying composapy resource to local save_dir and adding to tfs...")
    readme_artifacts = [
        COMPOSAPY_README_IPYNB,
        COMPOSAPY_ROOT_DIR.joinpath("docs", "simple-dataflow.json"),
    ]
    update_composapy_readme_artifacts(readme_artifacts)

    _update_readme()

    print("Copying composapy wheel to local save_dir and adding to tfs...")
    wheel = sorted(COMPOSAPY_ROOT_DIR.joinpath(".tox", "dist").glob("*.whl"))[0]
    update_composapy_wheel(wheel)

    # Goes through all wheels in ComposableAnalytics.DataLabService\static\wheels save_dir and
    # attempts to add them to tfs tracking source. This will pick up any manually added wheels
    # and fail silently with a return code of 1 if they already exist.
    print(
        "Adding any wheels in wheel save_dir that are not currently being tracked by tfs..."
    )
    update_static_wheel_deps()

    print("Copying composapy test files to local save_dir and adding to tfs...")
    tests = COMPOSAPY_ROOT_DIR.joinpath("tests")
    update_composapy_tests(tests)


def docs():
    # convert notebook (composapy-readme.ipynb) to markdown (README.md)
    nb = jupytext.read(COMPOSAPY_README_IPYNB)
    jupytext.write(nb, "README.md")


def _update_readme():
    docs()


@contextmanager
def working_directory(path):
    """Change working directory to `path` and restore old path on exit.
    `path` can be `None` in which case this is a no-op.
    """
    if path is None:
        yield

    else:
        old_dir = Path.cwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(old_dir)


if __name__ == "__main__":
    OPTIONS = ["-build", "-docs"]

    if len(sys.argv) == 1:
        raise Exception("Must include command arg (build, docs, etc.).")

    arg = sys.argv[1]
    if "options" in arg:
        print(", ".join(OPTIONS))
    elif "build" in arg:
        build()
    elif "docs" in arg:
        docs()
    else:
        print(f"{arg} is not a valid option.")
