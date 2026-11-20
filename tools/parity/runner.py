"""Run corpus scripts in this interpreter and write one result file per script. Run by run_parity.py, once per variant.

    python runner.py <variant> <results dir> <corpus dir> [script name ...]

It uses the composapy installed in the interpreter it runs under, so the baseline and the candidate are two virtual
environments, not two flags. A token session is registered from PARITY_TOKEN and APPLICATION_URI before each script,
and each script runs in a fresh namespace holding these names:

    record(name, value)    keep a value, in canonical form, under a name
    attempt(name, fn, show=None)
                           call fn() and record its value, or the class name and message of what it raised; with show,
                           record show(value) instead, and still return the value
    scrub(text)            text with GUIDs and run or object ids replaced, for values that differ on every run
    int_input(value)       an int to pass as an external input: a System.Int32 under the baseline, whose pythonnet gave
                           a Python int to .NET as an Int64 that no Int32 input accepted, and the int under the candidate
    unique(name)           a name that is the same on every run of this variant and differs between variants
    variant                'baseline' or 'candidate'
    fixtures               the Key and saved QueryViews run_parity.py created: names and ids
    fixture(name)          the path of a file in tests/TestFiles
    uri_arg(text)          a URI to pass to FileReference.Create: a System.Uri under the baseline, which takes no string,
                           and the text under the candidate
    list_input(values)     a list to pass as an external input: a .NET List[Object] under the baseline, which could take
                           nothing else (its own tests called _init_cs_list), and a plain list under the candidate

The result file is <results dir>/<script>.json: {"variant", "script", "records": [{"name", "value"}], "error", "seconds"}.
"""

import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from canonical import canonicalize  # noqa: E402

TEST_FILES = HERE.parent.parent / "tests" / "TestFiles"


def error_record(error):
    return {"type": type(error).__name__, "message": str(error)}


def canonical_or_marker(value):
    """canonicalize(value), or a marker when the value cannot even be read (for example a repr that raises)."""
    try:
        return canonicalize(value)
    except Exception as error:
        return {
            "$unreadable": {"value_type": type(value).__name__, **error_record(error)}
        }


def run_script(path, variant):
    import composapy
    from composapy.auth import AuthMode
    from composapy.key.models import KeyObject
    from composapy.session import Session

    Session.clear_registration()
    KeyObject.clear_registration()
    Session(auth_mode=AuthMode.TOKEN, credentials=os.environ["PARITY_TOKEN"]).register()

    records = []

    def record(name, value):
        records.append({"name": name, "value": canonical_or_marker(value)})

    def attempt(name, fn, show=None):
        try:
            value = fn()
            shown = show(value) if show else value
        except Exception as error:  # a failure is a result, and it has to match
            records.append({"name": name, "value": {"$error": error_record(error)}})
            return None
        records.append({"name": name, "value": canonical_or_marker(shown)})
        return value

    def scrub(text):
        text = re.sub(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            "<guid>",
            str(text),
        )
        text = re.sub(r"(?<=\bid=)\d+", "<id>", text)
        return re.sub(r"(?<=/)\d{3,}(?=/|$)", "<id>", text)

    def int_input(value):
        if variant == "baseline" and type(value) is int:
            from System import Int32

            return Int32(value)
        return value

    def list_input(values):
        if variant == "baseline":
            from System import Object
            from composapy.patch.table import _init_cs_list

            return _init_cs_list(Object, list(values))
        return list(values)

    def uri_arg(text):
        if variant == "baseline":
            from System import Uri, UriKind

            return Uri(text, UriKind.RelativeOrAbsolute)
        return text

    fixtures_file = os.environ.get("PARITY_FIXTURES")
    fixtures = (
        json.loads(Path(fixtures_file).read_text(encoding="utf-8"))
        if fixtures_file
        else {}
    )

    namespace = {
        "scrub": scrub,
        "int_input": int_input,
        "fixtures": fixtures,
        "uri_arg": uri_arg,
        "list_input": list_input,
        "record": record,
        "attempt": attempt,
        "unique": lambda name: f"parity-{variant}-{name}",
        "variant": variant,
        "fixture": lambda name: str(TEST_FILES / name),
        "__name__": "__parity__",
    }
    started, failure = time.perf_counter(), None
    try:
        exec(
            compile(Path(path).read_text(encoding="utf-8"), str(path), "exec"),
            namespace,
        )
    except Exception as error:
        failure = {
            **error_record(error),
            "traceback_tail": traceback.format_exc().strip().splitlines()[-3:],
        }
    return {
        "variant": variant,
        "script": Path(path).stem,
        "records": records,
        "error": failure,
        "seconds": round(time.perf_counter() - started, 3),
    }


def main(argv):
    if len(argv) < 4:
        sys.exit(__doc__)
    variant, results_dir, corpus_dir, *names = argv[1:]
    for var in ("PARITY_TOKEN", "APPLICATION_URI"):
        if not os.environ.get(var):
            sys.exit(f"{var} is not set")
    scripts = sorted(Path(corpus_dir).glob("*.py"))
    if names:
        scripts = [s for s in scripts if s.stem in names]
    out = Path(results_dir)
    out.mkdir(parents=True, exist_ok=True)
    for script in scripts:
        result = run_script(script, variant)
        (out / f"{script.stem}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        status = (
            "ERROR " + result["error"]["type"]
            if result["error"]
            else f"{len(result['records'])} records"
        )
        print(
            f"[{variant}] {script.stem}: {status} ({result['seconds']} s)", flush=True
        )


if __name__ == "__main__":
    main(sys.argv)
