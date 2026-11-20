"""Check a built wheel against the package folder it was built from.

Two things have gone wrong, and unexpected_files reports both:
  - setuptools copies the package into build/lib and never removes a file that was deleted from the source, so a wheel
    can carry modules that no longer exist (it once shipped bindings.py and stream.py, which import .NET);
  - `packages = find:` installs any folder with an __init__.py, so the wheel carried a top-level `tests` package into
    every environment's site-packages.
It lists every file in the wheel that is neither in the source's composapy folder nor in the wheel's own dist-info.
"""

import zipfile
from pathlib import Path

IGNORED = ("__pycache__",)


def unexpected_files(wheel_path, package_dir):
    package_dir = Path(package_dir)
    source = {
        "composapy/" + p.relative_to(package_dir).as_posix()
        for p in package_dir.rglob("*")
        if p.is_file()
        and not set(p.relative_to(package_dir).parts) & set(IGNORED)
        and p.suffix != ".pyc"
    }
    with zipfile.ZipFile(wheel_path) as wheel:
        packaged = {
            n
            for n in wheel.namelist()
            if not n.endswith("/")
            and "__pycache__" not in n
            and not n.endswith(".pyc")
            and not n.split("/")[0].endswith(".dist-info")
        }
    return sorted(packaged - source)
