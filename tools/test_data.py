"""What the C# suites receive from the tests folder (Product\\UnitTests\\TestData\\composapy).

They copy only the top-level test*.py files, conftest.py, .test.env, and TestFiles into a DataLab's working directory
(BaseDataLabCellExecutionTests.SetupTestsAndTestFiles), with no __init__.py, so conftest.py is a top-level module there
and cannot depend on iis.py or on being part of a package. The folders below belong to the Python test pipeline.
"""

import shutil
from pathlib import Path

EXCLUDED_DIRS = (
    "offline",
    "baseline",
    "wire_captures",
)  # top-level folders of the tests folder only
CACHE_DIRS = ("__pycache__", ".pytest_cache")


def copy_tests(source, destination):
    """Copies the tests folder over the destination without the Python-only folders or caches. Never deletes."""
    source = Path(source)

    def ignore(directory, names):
        skipped = {n for n in names if n in CACHE_DIRS or n.endswith(".pyc")}
        if Path(directory) == source:
            skipped |= {n for n in names if n in EXCLUDED_DIRS}
        return skipped

    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)


def stale_files(source, destination):
    """The files under destination (as '/'-separated relative paths) that copy_tests would not put there now: files
    whose source was removed, and anything inside a folder that is no longer copied. The copy never deletes them,
    so each one needs a `tf delete`."""
    source, destination = Path(source), Path(destination)
    stale = []
    for path in destination.rglob("*"):
        relative = path.relative_to(destination)
        if (
            not path.is_file()
            or set(relative.parts) & set(CACHE_DIRS)
            or path.suffix == ".pyc"
        ):
            continue
        if relative.parts[0] in EXCLUDED_DIRS or not (source / relative).exists():
            stale.append(relative.as_posix())
    return sorted(stale)
