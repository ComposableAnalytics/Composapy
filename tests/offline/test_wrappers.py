"""Offline tests for composapy.notebook.script_wrap and composapy.notebook.nb_wrap.

The wrapper is run the way DataLab runs it, as `python -m composapy.notebook.script_wrap <script> <inputs> [token]`
in a fresh process, against inputs files in the format of Appendix A.5. The notebook wrapper is in test_nb_wrap.py.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from composapy.notebook.inject import KEY_VALUE_PAIR_TYPE

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
URI = "http://example.test/CompApp/"
HANDLE_JSON = {
    "__type": "ExecutionHandle:#CompAnalytics.Contracts",
    "AppId": None,
    "HandleId": "b509b089-1b5c-4c09-8a4b-0dd2d1a1c2aa",
    "Id": 671892,
}
TABLE_JSON = {
    "__type": "Table:#CompAnalytics.Contracts.Tables",
    "Columns": [
        {
            "__type": "TableColumn:#CompAnalytics.Contracts.Tables",
            "Name": "a",
            "Type": "BIGINT",
        }
    ],
    "Headers": ["a"],
    "RootExecutionHandle": HANDLE_JSON,
    "SqlQuery": "SELECT * FROM [t] WHERE a = 'x\\y' AND b = \"q\"",
    "TableName": "t",
}
FILE_JSON = {
    "__type": "FileReference:#CompAnalytics.Contracts",
    "Uri": '/CompApp/runs/x/it\'s "a" \\ b.txt',
}


def inputs_file(tmp_path, **values):
    entries = [
        {"__type": KEY_VALUE_PAIR_TYPE, "key": k, "value": v} for k, v in values.items()
    ]
    path = tmp_path / "inputs.serialized"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def run_script(tmp_path, source, values=None, *extra_args, raw=None):
    """Runs a script through script_wrap; returns the finished process and the decoded outputs.serialized (or None)."""
    script = tmp_path / "user_script.py"
    script.write_bytes(raw if raw is not None else source.encode("utf-8"))
    inputs = inputs_file(tmp_path, **(values or {}))
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("DATALAB_DLL_DIR", "DATALAB_DLL_DIR_EXCLUDE", "_execution_handle")
    }
    env.update(
        APPLICATION_URI=URI, COMPOSAPY_INI_DIR=str(tmp_path)
    )  # no saved session is picked up
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "composapy.notebook.script_wrap",
            str(script),
            str(inputs),
            *extra_args,
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    outputs = tmp_path / "outputs.serialized"
    return result, (
        json.loads(outputs.read_text(encoding="utf-8")) if outputs.exists() else None
    )


def returned(outputs):
    return {item["key"]: item["value"] for item in outputs}


# ----------------------------------------------------------------------------------------------
# script_wrap: the arguments and the session
# ----------------------------------------------------------------------------------------------


def test_the_appendix_a5_example_runs_and_writes_its_output(tmp_path):
    result, outputs = run_script(
        tmp_path,
        "return_values = {'sum': test1 + 2}",
        {"test1": 1, "_execution_handle": HANDLE_JSON},
    )
    assert result.returncode == 0, result.stderr
    assert outputs == [
        {
            "__type": "KeyValuePairOfstringanyType:#System.Collections.Generic",
            "key": "sum",
            "value": 3,
        }
    ]


CHECK_SESSION = (
    "from composapy.session import get_session\nsession = get_session(raise_exception=False)\n"
    "return_values = {'registered': session is not None, 'uri': session.uri if session else ''}"
)


def test_without_a_token_argument_the_script_runs_and_no_session_is_registered(
    tmp_path,
):
    result, outputs = run_script(
        tmp_path, CHECK_SESSION
    )  # two arguments, as the launcher passes a null token
    assert result.returncode == 0, result.stderr
    assert returned(outputs) == {"registered": False, "uri": ""}


def test_an_empty_token_argument_registers_no_session(tmp_path):
    result, outputs = run_script(tmp_path, CHECK_SESSION, None, "")
    assert result.returncode == 0, result.stderr
    assert returned(outputs)["registered"] is False


def test_a_token_argument_registers_a_token_session_for_the_application_uri(tmp_path):
    result, outputs = run_script(tmp_path, CHECK_SESSION, None, "token-for-tests")
    assert result.returncode == 0, result.stderr
    assert returned(outputs) == {"registered": True, "uri": URI}


def test_the_script_cannot_see_the_token_as_a_variable(tmp_path):
    # the 0.13.3 build in static/wheels prepended token = '<token>' to every script
    source = "return_values = {'seen': 'token' in globals()}"
    result, outputs = run_script(tmp_path, source, None, "token-for-tests")
    assert returned(outputs) == {"seen": False}


def test_an_input_named_token_is_not_overwritten(tmp_path):
    result, outputs = run_script(
        tmp_path, "return_values = {'t': token}", {"token": "mine"}, "implicit"
    )
    assert returned(outputs) == {"t": "mine"}


# ----------------------------------------------------------------------------------------------
# script_wrap: how the script runs
# ----------------------------------------------------------------------------------------------


def test_a_function_sees_the_scripts_own_imports_and_helpers(tmp_path):
    source = (
        "import math\n"
        "LIMIT = 2\n"
        "def helper(r):\n"
        "    return round(math.pi * r * r, LIMIT)\n"
        "def area(r):\n"
        "    return helper(r)\n"
        "return_values = {'a': area(1)}\n"
    )
    result, outputs = run_script(tmp_path, source)
    assert (
        result.returncode == 0
    ), result.stderr  # NameError when exec used separate globals and locals
    assert returned(outputs) == {"a": 3.14}


def test_the_parameters_are_variables_in_the_script(tmp_path):
    result, outputs = run_script(
        tmp_path,
        "return_values = {'x': a + b, 'name': s}",
        {"a": 1, "b": 2, "s": "text"},
    )
    assert returned(outputs) == {"x": 3, "name": "text"}


def test_a_script_with_a_byte_order_mark_runs(tmp_path):
    result, outputs = run_script(
        tmp_path,
        "",
        raw=b"\xef\xbb\xbf" + "return_values = {'s': 'café'}\n".encode("utf-8"),
    )
    assert result.returncode == 0, result.stderr
    assert returned(outputs) == {"s": "café"}


def test_a_traceback_names_the_users_file_and_its_own_line_number(tmp_path):
    result, outputs = run_script(tmp_path, "x = 1\n\nraise RuntimeError('boom')\n")
    assert result.returncode != 0 and outputs is None
    assert (
        "user_script.py" in result.stderr
        and "line 3" in result.stderr
        and "RuntimeError: boom" in result.stderr
    )


def test_the_execution_handle_is_in_the_environment_and_not_a_variable(tmp_path):
    source = "import os\nreturn_values = {'env': os.environ['_execution_handle'], 'var': '_execution_handle' in globals()}"
    result, outputs = run_script(tmp_path, source, {"_execution_handle": HANDLE_JSON})
    assert result.returncode == 0, result.stderr
    assert json.loads(returned(outputs)["env"]) == HANDLE_JSON
    assert returned(outputs)["var"] is False


def test_contract_parameters_arrive_as_typed_objects(tmp_path):
    source = "return_values = {'t': type(tbl).__name__, 'f': type(ref).__name__, 'q': tbl.SqlQuery}"
    result, outputs = run_script(
        tmp_path, source, {"tbl": TABLE_JSON, "ref": FILE_JSON}
    )
    assert result.returncode == 0, result.stderr
    assert returned(outputs) == {
        "t": "Table",
        "f": "FileReference",
        "q": TABLE_JSON["SqlQuery"],
    }


def test_a_script_that_returns_a_parameter_table_writes_it_back_unchanged(tmp_path):
    result, outputs = run_script(
        tmp_path, "return_values = {'t': tbl}", {"tbl": TABLE_JSON}
    )
    assert result.returncode == 0, result.stderr
    assert returned(outputs) == {"t": TABLE_JSON}


# ----------------------------------------------------------------------------------------------
# script_wrap: what goes wrong
# ----------------------------------------------------------------------------------------------


def test_a_script_without_return_values_fails_as_before(tmp_path):
    result, outputs = run_script(tmp_path, "x = 1")
    assert (
        result.returncode != 0 and "return_values" in result.stderr and outputs is None
    )


def test_an_unsupported_return_value_fails_and_writes_nothing(tmp_path):
    result, outputs = run_script(
        tmp_path, "return_values = {'v': [1, 2]}", {"_execution_handle": HANDLE_JSON}
    )
    assert result.returncode != 0 and "is not currently supported" in result.stderr
    assert outputs is None
