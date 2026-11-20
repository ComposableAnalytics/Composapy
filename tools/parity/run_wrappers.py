"""Run the DLNBR test notebooks and scripts through the real wrappers under the baseline and the candidate.

Run it with the CANDIDATE environment's Python, from a folder with no composapy.ini or composapy folder:

    tools\\parity\\envs\\candidate\\Scripts\\python.exe tools\\parity\\run_wrappers.py [--only baseline|candidate] [case ...]

For each case it writes an inputs.serialized in the format the C# launcher writes (Appendix A.5), runs
`python -m composapy.notebook.script_wrap` or `nb_wrap` in the variant's own environment as DataLab does, and records the
exit code, the outputs.serialized it wrote, and the tables behind any Table it returned, as
results/<variant>/wrapper_<case>.json, in the format compare_results.py reads. A real execution handle, Table,
FileReference, and saved DataFlow are made per variant (wrapper_fixtures.py), and the token never reaches a file: the
notebook files it is injected into are deleted after each run.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_parity  # noqa: E402
from canonical import canonicalize  # noqa: E402

DATA = (
    run_parity.ROOT.parent.parent
    / "Product"
    / "UnitTests"
    / "TestData"
    / "DataLabTestData"
)
OWN = HERE / "wrapper_corpus"
KVP = "KeyValuePairOfstringanyType:#System.Collections.Generic"
STRING_BOOL = [
    "str",
    "np.str_",
    "string",
    "pd.StringDtype()",
    "bool",
    "np.bool_",
    "pd.BooleanDtype()",
]


def case(
    name, file, kind, source="data", extra=None, markers=(), values=True, **params
):
    return {
        "name": name,
        "file": file,
        "kind": kind,
        "source": source,
        "extra": extra,
        "markers": list(markers),
        "values": values,
        "params": params,
    }


def script(name, file, **kw):
    return case(name, file, "script", **kw)


def notebook(name, file, **kw):
    return case(name, file, "notebook", **kw)


CASES = [
    # the values a script receives and returns, through the real launcher format
    script("script_strings", "TestExecuteScript.py", input1="hello", input2="world"),
    script("script_bools", "TestExecuteScript.py", input1=True, input2=False),
    script("script_ints", "TestExecuteScript.py", input1=1, input2=2147483647),
    script("script_null", "TestExecuteScript.py", input1=None, input2=None),
    script("script_floats", "TestExecuteScript.py", input1=3.5, input2=2.0),
    script("script_big_ints", "TestExecuteScript.py", input1=2**40, input2=-(2**40)),
    script(
        "script_text_special",
        "TestExecuteScript.py",
        input1='it\'s "q" \\ café 中文',
        input2="line\nbreak\ttab",
    ),
    script("script_implicit_auth", "TestImplicitScript.py", inputId="$app_id"),
    script(
        "script_send_file_reference",
        "TestExecuteNotebookSendFileReference.py",
        input1="$file_ref",
    ),
    script("script_error", "TestErrorThrowing.py", markers=["ZeroDivisionError"]),
    script("script_trace_output", "TestScriptTraceOutput.py"),
    script("script_return_types", "return_types.py", source="own"),
    script("script_return_big_int", "return_big_int.py", source="own"),
    script(
        "script_return_dataframes",
        "return_dataframe.py",
        source="own",
        table="$table",
        values=True,
    ),
    script(
        "script_return_unsupported",
        "return_unsupported.py",
        source="own",
        markers=["is not currently supported"],
    ),
    script("script_single_namespace", "single_namespace.py", source="own"),
    script(
        "script_token_parameter",
        "token_parameter.py",
        source="own",
        token="a value the DataFlow passed",
    ),
    # notebooks
    notebook("nb_strings", "TestExecuteNotebook.ipynb", input1="hello", input2="world"),
    notebook("nb_bools_ints", "TestExecuteNotebook.ipynb", input1=True, input2=7),
    notebook("nb_null", "TestExecuteNotebook.ipynb", input1=None, input2=None),
    notebook("nb_implicit_auth", "TestImplicitAuth.ipynb", inputId="$app_id"),
    notebook("nb_manual_session", "TestImplicitManualSession.ipynb", inputId="$app_id"),
    notebook("nb_return_file_txt", "TestExecuteNotebookFileReferenceReturn.ipynb"),
    notebook("nb_return_file_csv", "TestExecuteNotebookCsvFileReferenceReturn.ipynb"),
    notebook(
        "nb_send_file_reference",
        "TestExecuteNotebookSendFileReference.ipynb",
        input1="$file_ref",
    ),
    notebook("nb_module_import", "TestModuleImport.ipynb", extra="test_module"),
    notebook("nb_no_return_values", "TestNoReturnValues.ipynb"),
    notebook(
        "nb_error",
        "TestTraceOutput.ipynb",
        markers=["very-unique-exception-qoeasdffdsa3971223097403asdffdsatttt23848"],
    ),
    # DataFrames returned from a notebook: the column types the C# tests cover, on a two-column table (a text, b integer)
    *[
        notebook(
            f"nb_pandas_{label}",
            "TestPandasDataFrameReturn1.ipynb",
            table="$table",
            python_types=types,
            index_cols="",
        )
        for label, types in [
            ("str_int8", "str;np.int8"),
            ("str_uint8", "str;np.uint8"),
            ("str_Int16", "str;pd.Int16Dtype()"),
            ("str_Int64", "str;pd.Int64Dtype()"),
            ("str_float32", "str;np.float32"),
            ("str_Float64", "str;pd.Float64Dtype()"),
            ("str_bool", "str;bool"),
            ("str_boolean", "str;pd.BooleanDtype()"),
            ("StringDtype_int", "pd.StringDtype();int"),
            ("str_datetime", "str;datetime64[ns]"),
            ("str_timedelta", "str;timedelta64[ns]"),
        ]
    ],
    notebook(
        "nb_pandas_row_index",
        "TestPandasDataFrameReturn1.ipynb",
        table="$table",
        python_types="str;int",
        index_cols="a",
    ),
    notebook(
        "nb_pandas_row_multi_index",
        "TestPandasDataFrameReturn1.ipynb",
        table="$table",
        python_types="str;int",
        index_cols="a;b",
    ),
    notebook(
        "nb_pandas_col_multi_index",
        "TestPandasDataFrameReturn2.ipynb",
        test="col-multi-index",
        values=False,
    ),
    notebook(
        "nb_pandas_duplicate_names",
        "TestPandasDataFrameReturn2.ipynb",
        test="duplicate-col-names",
    ),
    notebook(
        "nb_pandas_no_columns", "TestPandasDataFrameReturn2.ipynb", test="no-cols"
    ),
]


def scrub(text):
    text = re.sub(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "<guid>",
        str(text),
    )
    return re.sub(r"(?<=/)\d{3,}(?=/|$)", "<id>", text)


def normalize(value):
    """The returned JSON with what differs on every run (GUIDs, run ids) replaced."""
    if isinstance(value, dict):
        return {
            k: (
                "<id>"
                if k in ("Id", "ResultId", "AppId")
                and isinstance(v, int)
                and not isinstance(v, bool)
                else normalize(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return scrub(value) if isinstance(value, str) else value


def inputs_for(item, fixtures):
    placeholders = {
        "$table": fixtures["table"],
        "$file_ref": fixtures["file_ref"],
        "$app_id": fixtures["app_id"],
    }
    entries = [
        {
            "__type": KVP,
            "key": key,
            "value": (
                placeholders.get(value, value) if isinstance(value, str) else value
            ),
        }
        for key, value in item["params"].items()
    ]
    entries.append(
        {"__type": KVP, "key": "_execution_handle", "value": fixtures["handle"]}
    )
    return entries


def records_for(item, process, run_dir):
    from composapy._wire import codec

    records = []

    def add(name, value):
        records.append({"name": name, "value": canonicalize(value)})

    add("exit_code", process.returncode)
    outputs = run_dir / "outputs.serialized"
    add("outputs_file_written", outputs.exists())
    for marker in item["markers"]:
        add(f"stderr_contains[{marker[:40]}]", marker in process.stderr)
    add(
        "stdout_digit_lines",
        [
            line.strip()
            for line in process.stdout.splitlines()
            if line.strip().isdigit()
        ],
    )
    if not outputs.exists():
        return records

    raw = outputs.read_bytes()
    text = raw.decode("utf-8-sig")
    add("outputs_file_has_bom", raw.startswith(b"\xef\xbb\xbf"))
    add("outputs_file_is_compact_json", ", " not in text and '": ' not in text)
    entries = json.loads(text)
    add("output_keys", [entry["key"] for entry in entries])
    add("entry_member_order", [list(entry) for entry in entries])
    for entry in entries:
        key, value = entry["key"], entry["value"]
        add(f"output.{key}", normalize(value))
        if isinstance(value, dict):
            add(f"output.{key}.member_order", list(value))
            if item["values"] and str(value.get("__type", "")).startswith("Table:"):
                try:
                    frame = codec.decode(json.dumps(value)).to_pandas()
                except Exception as error:
                    frame = {
                        "$error": {"type": type(error).__name__, "message": str(error)}
                    }
                add(f"output.{key}.dataframe", frame)
    return records


def run_case(variant, item, fixtures, token):
    python = run_parity.ENVS / variant / "Scripts" / "python.exe"
    root = run_parity.WORK / "wrapper" / variant / item["name"]
    shutil.rmtree(root, ignore_errors=True)
    run_dir = (
        root / "runs" / "r1"
    )  # nb_wrap runs a notebook from run_dir.parent.parent, as DataLab does
    run_dir.mkdir(parents=True)
    target = root / item["file"]
    shutil.copy((DATA if item["source"] == "data" else OWN) / item["file"], target)
    if item["extra"]:
        shutil.copytree(DATA / item["extra"], root / item["extra"])
    inputs = run_dir / "inputs.serialized"
    inputs.write_text(json.dumps(inputs_for(item, fixtures)), encoding="utf-8")

    module = (
        "composapy.notebook.nb_wrap"
        if item["kind"] == "notebook"
        else "composapy.notebook.script_wrap"
    )
    env = {
        **os.environ,
        "APPLICATION_URI": os.environ["APPLICATION_URI"],
        "COMPOSAPY_INI_DIR": str(root),
        "PYTHONIOENCODING": "utf-8",
    }
    env["PATH"] = (
        str(python.parent) + os.pathsep + env.get("PATH", "")
    )  # DataLab puts the environment's Scripts first, so a
    env["JUPYTER_PATH"] = str(
        python.parent.parent / "share" / "jupyter"
    )  # kernel's bare `python` is this environment's
    env.pop("DATALAB_DLL_DIR", None)
    if variant == "baseline":
        env["DATALAB_DLL_DIR"] = str(run_parity.DLL_DIR)
    command = [
        str(python),
        "-m",
        module,
        str(target).replace("\\", "/"),
        str(inputs).replace("\\", "/"),
        token,
    ]
    started = time.perf_counter()
    try:
        process = subprocess.run(
            command,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1200,
        )
        for stream, text in (
            ("stdout.txt", process.stdout),
            ("stderr.txt", process.stderr),
        ):  # for reading a failure; not compared
            (root / stream).write_text(text.replace(token, "<token>"), encoding="utf-8")
        records = records_for(item, process, run_dir)
    except subprocess.TimeoutExpired:
        records = [
            {
                "name": "exit_code",
                "value": {
                    "$error": {
                        "type": "TimeoutExpired",
                        "message": "no result in 1200 seconds",
                    }
                },
            }
        ]
    finally:
        for name in (
            "temp.ipynb",
            "result.ipynb",
        ):  # the wrapper writes the token into these
            (run_dir / name).unlink(missing_ok=True)
    return {
        "variant": variant,
        "script": f"wrapper_{item['name']}",
        "records": records,
        "error": None,
        "seconds": round(time.perf_counter() - started, 3),
    }


def main(argv):
    args = argv[1:]
    only = None
    if "--only" in args:
        only = args[args.index("--only") + 1]
        args = [a for a in args if a not in ("--only", only)]
    selected = [c for c in CASES if not args or c["name"] in args]
    from dotenv import load_dotenv

    for env_file in (
        run_parity.ROOT / "tests" / ".test.env",
        run_parity.ROOT / ".local.env",
    ):
        load_dotenv(env_file)
    import wrapper_fixtures

    session = run_parity.make_session()
    token = run_parity.make_token(session)
    for variant in ("baseline", "candidate"):
        if only not in (None, variant):
            continue
        fixtures = wrapper_fixtures.create(session)
        try:
            out = run_parity.RESULTS / variant
            out.mkdir(parents=True, exist_ok=True)
            for item in selected:
                result = run_case(variant, item, fixtures, token)
                (out / f"{result['script']}.json").write_text(
                    json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                code = next(
                    (r["value"] for r in result["records"] if r["name"] == "exit_code"),
                    None,
                )
                print(
                    f"[{variant}] {item['name']}: exit {code}, {len(result['records'])} records ({result['seconds']} s)",
                    flush=True,
                )
        finally:
            wrapper_fixtures.delete(session, fixtures)


if __name__ == "__main__":
    main(sys.argv)
