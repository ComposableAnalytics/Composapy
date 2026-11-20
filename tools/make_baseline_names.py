"""Write public_names.json for King Snake task 1 step 6, using the BASELINE composapy.

For `composapy` and every submodule it can find, record the sorted dir() names and each name's type name.
A submodule that cannot be imported is recorded under "import_errors" with the reason; it never stops the run.

Run in a shared DataLab environment that has the baseline composapy, in a terminal where DATALAB_DLL_DIR is set,
from a folder that does NOT contain a `composapy` folder or a composapy.ini (so the installed package is the one imported):
    python make_public_names.py --out C:\\path\\to\\Composapy\\tests\\baseline\\public_names.json
"""

import argparse
import importlib
import importlib.metadata as md
import json
import pkgutil
import sys

import composapy


def describe(module):
    names = {}
    for name in sorted(dir(module)):
        try:
            value = getattr(module, name)
            names[name] = {
                "type": type(value).__name__,
                "defined_in": getattr(value, "__module__", None),
            }
        except (
            Exception
        ) as e:  # a few attributes raise when read; record that and move on
            names[name] = {
                "type": f"<unreadable: {type(e).__name__}>",
                "defined_in": None,
            }
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    import_errors = {}

    def on_walk_error(name):
        import_errors[name] = (
            "could not be imported while listing the package: "
            + repr(sys.exc_info()[1])
        )

    # pkgutil lists submodules from the files on disk, so a module is found even when importing it would fail
    found = sorted(
        m.name
        for m in pkgutil.walk_packages(
            composapy.__path__, prefix="composapy.", onerror=on_walk_error
        )
    )

    modules = {"composapy": describe(composapy)}
    for name in found:
        try:
            modules[name] = describe(importlib.import_module(name))
        except (
            BaseException
        ) as e:  # includes SystemExit and NameError from code that only works inside IPython
            import_errors[name] = (
                f"{type(e).__name__}: {str(e).strip().splitlines()[0][:200] if str(e).strip() else ''}"
            )

    record = {
        "python": sys.version.split()[0],
        "composapy_version": md.version("composapy"),
        "composapy_location": composapy.__file__,
        "modules": modules,
        "import_errors": import_errors,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    print(
        f"python {record['python']} | composapy {record['composapy_version']} | {record['composapy_location']}"
    )
    print(
        f"{len(modules)} modules recorded, {len(import_errors)} could not be imported"
    )
    for name, reason in sorted(import_errors.items()):
        print(f"  NOT IMPORTABLE  {name}: {reason}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
