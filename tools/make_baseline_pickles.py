"""Write the baseline pickles for King Snake task 1 step 6, using the BASELINE composapy (the wheel DataLabs run today).

Run it in a shared DataLab environment that has that composapy installed, in a terminal where DATALAB_DLL_DIR is set:
    set TEST_API_KEY (and, if it is not http://localhost/CompApp/, APPLICATION_URI) as environment variables, then
    python make_baseline_pickles.py --testfiles path\\to\\Composapy\\tests\\TestFiles --out path\\to\\Composapy\\tests\\baseline\\pickles

Writes, into --out:
    table.pkl / table_behavior.pkl                       a Table from running tablecreator.json
    file_reference.pkl / file_reference_behavior.pkl     a FileReference from file_ref() on a local file
    execution_handle.pkl / execution_handle_behavior.pkl the run's ExecutionHandle
    manifest.json   for each file: the expected json.dumps output; whether the baseline itself can load it back
                    (loads_in_baseline, with the error if not); for the table, its to_pandas() dtypes and values

"*_behavior" means the object's __class__ was switched to composapy's *PickleBehavior class before pickling, the way
the DataLab wrappers do for the objects they receive.

Not every file is expected to load in the baseline: a pickle of a plain object records the .NET class itself, and
unpickling calls that class's constructor with the serialized text, which the .NET classes don't accept. That is
recorded in the manifest, not treated as a failure.

To only re-check files that already exist (no session or token needed):  add --verify-only
"""

import argparse
import json
import os
import pickle
from pathlib import Path

import composapy  # first: it loads the .NET types that unpickling needs
from composapy import (
    ExecutionHandlePickleBehavior,
    FileReferencePickleBehavior,
    TablePickleBehavior,
    file_ref,
)


def verify(out, names):
    """Try to load each pickle back in this (baseline) environment and report what happened."""
    results = {}
    for name in names:
        try:
            loaded = pickle.loads((out / name).read_bytes())
            results[name] = {
                "loads_in_baseline": True,
                "loads_as": f"{type(loaded).__module__}.{type(loaded).__name__}",
                "error": None,
            }
        except (
            Exception
        ) as e:  # report every kind of failure; nothing here is allowed to stop the run
            results[name] = {
                "loads_in_baseline": False,
                "loads_as": None,
                "error": f"{type(e).__name__}: {e}",
            }
    return results


def generate(out, testfiles):
    from composapy.auth import AuthMode
    from composapy.dataflow.api import DataFlow
    from composapy.session import Session

    Session(
        auth_mode=AuthMode.TOKEN,
        credentials=os.environ["TEST_API_KEY"],
        uri=os.environ.get("APPLICATION_URI", "http://localhost/CompApp/"),
    ).register()

    run = DataFlow.create(file_path=str(testfiles / "tablecreator.json")).run()
    table = run.modules.first_with_name("Table Creator").result.value
    handle = run.contract.Handle
    reference = file_ref(testfiles / "create_file_ref_target.txt")

    objects = {
        "table": (table, TablePickleBehavior),
        "file_reference": (reference, FileReferencePickleBehavior),
        "execution_handle": (handle, ExecutionHandlePickleBehavior),
    }

    manifest = {}
    for name, (obj, behavior_class) in objects.items():
        # json.dumps works on these objects because composapy patches it; take the expected output first
        expected_json = json.loads(json.dumps(obj))

        (out / f"{name}.pkl").write_bytes(pickle.dumps(obj))
        manifest[f"{name}.pkl"] = {"json": expected_json}

        obj.__class__ = behavior_class
        (out / f"{name}_behavior.pkl").write_bytes(pickle.dumps(obj))
        manifest[f"{name}_behavior.pkl"] = {"json": expected_json}

    df = table.to_pandas()
    for key in ("table.pkl", "table_behavior.pkl"):
        manifest[key]["dtypes"] = {
            column: str(dtype) for column, dtype in df.dtypes.items()
        }
        manifest[key]["values"] = json.loads(
            df.to_json(orient="split", date_format="iso")
        )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--testfiles",
        help="the Composapy tests\\TestFiles folder (not needed with --verify-only)",
    )
    parser.add_argument(
        "--out", required=True, help="where to write the .pkl files and manifest.json"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="re-check the files already in --out; write nothing else",
    )
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"

    if args.verify_only:
        manifest = (
            json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest_path.exists()
            else {}
        )
        for pkl in sorted(p.name for p in out.glob("*.pkl")):
            manifest.setdefault(pkl, {})
    else:
        if not args.testfiles:
            parser.error("--testfiles is required unless --verify-only is given")
        manifest = generate(out, Path(args.testfiles))

    # the files are on disk now; record whether this environment can read each one back
    for name, result in verify(out, sorted(manifest)).items():
        manifest[name].update(result)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n{'file':<34} {'loads in baseline':<18} result")
    for name in sorted(manifest):
        m = manifest[name]
        print(
            f"{name:<34} {str(m['loads_in_baseline']):<18} {m['loads_as'] or m['error']}"
        )
    print(f"\nwrote {len(manifest)} files and {manifest_path}")


if __name__ == "__main__":
    main()
