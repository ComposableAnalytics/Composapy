"""Offline tests for the DataLab worker script, Product\\CompAnalytics.DataLabService\\static\\worker.py.

The script is loaded by path, once per module, and its functions are called directly. No DataLab service, named pipe,
or network is involved: a run's reply is captured instead of written to a pipe, the pipe server is driven with fake
win32 pipe functions, and a composapy session is only ever built, never used. mlflow is not a dependency of the test
environment, so the model registration code runs against a small stand-in module.

worker.py treats the process's working directory as the DataLab's code folder, so every test runs in an empty one.
"""

import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import types
from pathlib import Path

import pandas as pd
import pytest
import pywintypes

from composapy._wire import codec
from composapy.auth import AuthMode
from composapy.contracts import Table
from composapy.key.models import KeyObject, get_key_object
from composapy.session import Session, get_session

TESTS_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = TESTS_DIR.parent
WORKER_PATH = (
    ROOT_DIR.parent.parent
    / "Product"
    / "CompAnalytics.DataLabService"
    / "static"
    / "worker.py"
)

pytestmark = pytest.mark.skipif(
    not WORKER_PATH.is_file(), reason="the product source tree is not present"
)

URI = "http://example.test/CompApp/"
HANDLE = {
    "__type": "ExecutionHandle:#CompAnalytics.Contracts",
    "AppId": None,
    "HandleId": "be733cc6-df15-4cd6-8f37-73d1c8def3f7",
    "Id": 685692,
}
TABLE_JSON = json.dumps(
    {
        "__type": "Table:#CompAnalytics.Contracts.Tables",
        "Columns": [],
        "Headers": [],
        "RootExecutionHandle": HANDLE,
        "SqlQuery": "SELECT * FROM [t]",
        "TableName": "t",
    }
)


# ----------------------------------------------------------------------------------------------
# Fixtures and helpers
# ----------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _worker_module():
    spec = importlib.util.spec_from_file_location("worker", WORKER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def code_dir(tmp_path, monkeypatch):
    """An empty folder that is the process's working directory, which worker.py treats as the DataLab's code."""
    folder = tmp_path / "code"
    folder.mkdir()
    monkeypatch.chdir(folder)
    return folder


@pytest.fixture
def worker(_worker_module, code_dir, tmp_path, monkeypatch):
    """The worker module with its per-process state reset, run in an empty code folder."""
    monkeypatch.setenv("APPLICATION_URI", URI)
    monkeypatch.setattr(_worker_module, "_model_dependency_paths", {})
    monkeypatch.setattr(_worker_module, "_running_request_id", None)
    monkeypatch.setattr(_worker_module, "_pending_model_registrations", [])
    # an entrypoint may add to the import path or import a module of its own
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield _worker_module
    for name, module in list(sys.modules.items()):
        location = getattr(module, "__file__", None)
        if location and str(tmp_path) in str(location):
            del sys.modules[name]


@pytest.fixture
def no_exit(monkeypatch):
    """worker.py ends the process when a cancel does not take. A test must never do that to pytest."""
    calls = []
    monkeypatch.setattr(os, "_exit", lambda code: calls.append(code))
    yield calls
    assert calls == [], "the worker tried to end the process"


class Runner:
    """Runs entrypoints through run_entrypoint and keeps the replies, as dictionaries.

    By default the reply is captured where run_entrypoint hands it to _send_reply. With on_wire=True the real _send_reply
    runs and the frame it would have written to the pipe is captured and decoded instead.
    """

    def __init__(self, worker, code_dir, monkeypatch, on_wire=False):
        self.worker = worker
        self.code_dir = code_dir
        self.replies = []
        if on_wire:
            monkeypatch.setattr(
                worker,
                "_write_frame",
                lambda payload, pipe: self.replies.append(
                    json.loads(payload.decode("utf-8"))
                ),
            )
        else:
            monkeypatch.setattr(
                worker,
                "_send_reply",
                lambda response, pipe: self.replies.append(response),
            )

    def write(self, source, name="entry.py"):
        path = self.code_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        return path

    def run(
        self,
        source=None,
        entrypoint="entry.py",
        parameters=None,
        request_id="req-1",
        token="token-A",
        handle=None,
        models=None,
    ):
        if source is not None:
            self.write(source, entrypoint)
        count = len(self.replies)
        self.worker.run_entrypoint(
            entrypoint,
            {} if parameters is None else parameters,
            request_id,
            token,
            handle,
            {} if models is None else models,
            None,
        )
        assert len(self.replies) == count + 1, "a run must be answered exactly once"
        return self.replies[-1]


@pytest.fixture
def runner(worker, code_dir, monkeypatch):
    return Runner(worker, code_dir, monkeypatch)


@pytest.fixture
def wire_runner(worker, code_dir, monkeypatch):
    return Runner(worker, code_dir, monkeypatch, on_wire=True)


def _stage_model_dir(root, name="staged"):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "MLmodel").write_text("flavors: {}", encoding="utf-8")
    return folder


@pytest.fixture
def fake_mlflow(monkeypatch, tmp_path):
    """A stand-in for mlflow, which the test environment does not have. Records what each flavor was asked to save.

    The flavors: sklearn and xgboost take (model, path), pyfunc takes (path, python_model=...) as in mlflow. Staged
    models go to a folder under tmp_path, which is also where tempfile.gettempdir() now points.
    """
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    saved = []

    def flavor(name, loads_as=None):
        module = types.ModuleType(f"mlflow.{name}")

        def write(path):
            os.makedirs(path)
            Path(path, "MLmodel").write_text(name, encoding="utf-8")

        if name == "pyfunc":

            def save_model(path, python_model=None):
                saved.append((name, path, python_model))
                write(path)

        else:

            def save_model(model, path):
                saved.append((name, path, model))
                write(path)

        module.save_model = save_model
        module.load_model = lambda path: ("loaded by " + name, path)
        return module

    mlflow = types.ModuleType("mlflow")
    mlflow.sklearn = flavor("sklearn")
    mlflow.xgboost = flavor("xgboost")
    mlflow.pyfunc = flavor("pyfunc")
    mlflow.saved = saved

    models = types.ModuleType("mlflow.models")

    class Model:
        flavors_by_path = {}

        def __init__(self, flavors):
            self.flavors = flavors

        @classmethod
        def load(cls, path):
            return cls(cls.flavors_by_path[path])

    models.Model = Model
    mlflow.models = models
    monkeypatch.setitem(sys.modules, "mlflow", mlflow)
    monkeypatch.setitem(sys.modules, "mlflow.models", models)
    return mlflow


# ----------------------------------------------------------------------------------------------
# reset_session: a run only ever sees the session and key of the user it runs for
# ----------------------------------------------------------------------------------------------


def test_reset_session_registers_a_token_session_for_the_caller(worker):
    worker.reset_session("token-A")

    session = get_session()
    assert session.auth_mode is AuthMode.TOKEN
    assert session.connection_settings.Uri == URI
    assert session._client.session.headers["Authorization"] == "token-A"


def test_a_second_caller_gets_their_own_session_and_the_first_is_closed(
    worker, monkeypatch
):
    worker.reset_session("token-A")
    first = get_session()
    closed = []
    monkeypatch.setattr(first, "close", lambda: closed.append(first))

    worker.reset_session("token-B")

    second = get_session()
    assert second is not first
    assert second._client.session.headers["Authorization"] == "token-B"
    assert closed == [first]


def test_reset_session_clears_the_key_the_previous_caller_registered(worker):
    worker.reset_session("token-A")
    KeyObject(types.SimpleNamespace(Value=None, Name="A's key")).register()
    assert get_key_object(raise_exception=False) is not None

    worker.reset_session("token-B")

    assert get_key_object(raise_exception=False) is None


def test_reset_session_with_no_registered_session_or_key_just_registers(worker):
    assert get_session(raise_exception=False) is None

    worker.reset_session("token-A")

    assert get_session()._client.session.headers["Authorization"] == "token-A"
    assert get_key_object(raise_exception=False) is None


def test_two_runs_for_two_users_share_nothing_through_the_entrypoint(runner):
    # the first entrypoint registers a key, as a notebook cell reading a Key would
    source_a = """
        from composapy.key.models import KeyObject, get_key_object
        from composapy.session import get_session
        KeyObject(type("Contract", (), {"Value": None, "Name": "A's key"})()).register()
        return_values = {
            "token": get_session()._client.session.headers["Authorization"],
            "key": get_key_object().contract.Name,
        }
    """
    source_b = """
        from composapy.key.models import get_key_object
        from composapy.session import get_session
        return_values = {
            "token": get_session()._client.session.headers["Authorization"],
            "key": get_key_object(raise_exception=False),
        }
    """

    first = runner.run(source_a, request_id="r1", token="token-A")
    second = runner.run(source_b, request_id="r2", token="token-B")

    assert first["Result"] == {"token": "token-A", "key": "A's key"}
    assert second["Result"] == {"token": "token-B", "key": None}


def test_a_session_the_entrypoint_registered_itself_is_replaced_for_the_next_run(
    runner,
):
    own_session = """
        from composapy.auth import AuthMode
        from composapy.session import Session
        Session(uri="http://elsewhere.test/App/", auth_mode=AuthMode.TOKEN, credentials="stolen").register()
    """
    read_session = """
        from composapy.session import get_session
        session = get_session()
        return_values = {"uri": session.connection_settings.Uri, "token": session._client.session.headers["Authorization"]}
    """

    runner.run(own_session, request_id="r1", token="token-A")
    reply = runner.run(read_session, request_id="r2", token="token-B")

    assert reply["Result"] == {"uri": URI, "token": "token-B"}


def test_a_run_with_no_caller_token_is_answered_with_exit_code_2_and_never_runs(
    runner, code_dir
):
    reply = runner.run(
        f"open({str(code_dir / 'ran')!r}, 'w').close()\n",
        token=None,
    )

    assert reply["Type"] == "error"
    assert reply["ExitCode"] == 2
    assert reply["RequestId"] == "req-1"
    assert "no caller token" in reply["ErrorMessage"]
    assert not (code_dir / "ran").exists()


def test_a_run_without_an_application_uri_is_answered_with_exit_code_2(
    runner, monkeypatch
):
    monkeypatch.delenv("APPLICATION_URI")

    reply = runner.run("return_values = {}\n")

    assert reply["Type"] == "error"
    assert reply["ExitCode"] == 2
    assert "UriNotConfiguredError" in reply["ErrorMessage"]


def test_a_run_that_fails_to_reset_the_session_clears_the_running_request(
    worker, runner
):
    worker._begin_request("req-1")

    runner.run("return_values = {}\n", token=None)

    assert worker._running_request_id is None


@pytest.mark.parametrize("token", ["", "   ", None, 5])
def test_a_caller_token_that_is_empty_or_not_text_is_refused_before_any_session_is_made(
    worker, token
):
    # Session only requires a str for AuthMode.TOKEN, so an empty token would register a session whose requests carry an
    # empty Authorization header
    before = get_session(raise_exception=False)

    with pytest.raises(ValueError, match="no caller token"):
        worker.reset_session(token)

    assert get_session(raise_exception=False) is before


def test_a_run_with_an_empty_caller_token_is_answered_with_exit_code_2(runner):
    reply = runner.run("return_values = {'ran': True}\n", token="")

    assert reply["Type"] == "error" and reply["ExitCode"] == 2
    assert "no caller token" in reply["ErrorMessage"]


# ----------------------------------------------------------------------------------------------
# run_entrypoint / _run
# ----------------------------------------------------------------------------------------------


def test_a_run_returns_return_values_with_exit_code_0(runner):
    reply = runner.run(
        """
        return_values = {"answer": 40 + 2, "name": "x", "nested": {"a": [1, 2]}}
        """
    )

    assert reply == {
        "Type": "result",
        "RequestId": "req-1",
        "Result": {"answer": 42, "name": "x", "nested": {"a": [1, 2]}},
        "ExitCode": 0,
    }


def test_a_run_without_return_values_has_an_empty_result(runner):
    reply = runner.run("x = 1\n")

    assert reply["Type"] == "result"
    assert reply["Result"] == {}
    assert reply["ExitCode"] == 0
    assert "RegisteredModels" not in reply


def test_a_parameter_passed_as_none_is_a_defined_variable_set_to_none(runner):
    reply = runner.run(
        """
        return_values = {"is_none": value is None, "other": other}
        """,
        parameters={"value": None, "other": 5},
    )

    assert reply["Type"] == "result"
    assert reply["Result"] == {"is_none": True, "other": 5}


def test_the_callers_parameters_are_not_changed_by_the_run(runner):
    parameters = {"x": 1}

    runner.run("x = 2\nreturn_values = {}\n", parameters=parameters)

    assert parameters == {"x": 1}


def test_the_entrypoint_has_register_model_and_load_model_in_scope(runner):
    reply = runner.run(
        """
        return_values = {
            "register": register_model.__name__,
            "load": load_model.__name__,
        }
        """
    )

    assert reply["Result"] == {"register": "register_model", "load": "load_model"}


def test_names_defined_at_the_top_of_the_entrypoint_are_visible_inside_its_functions(
    runner,
):
    # the entrypoint runs with one dict for globals and locals, as a script would
    reply = runner.run(
        """
        base = 10
        def add(n):
            return base + n
        return_values = {"sum": add(5)}
        """
    )

    assert reply["Result"] == {"sum": 15}


def test_pinned_an_entrypoint_does_not_run_as_main_and_has_no_file_and_needs_a_decision(
    runner,
):
    # exec() gets a namespace without __name__ or __file__. __name__ then resolves to the builtins module's name, so
    # an "if __name__ == '__main__':" block is silently skipped, and __file__ is a NameError.
    reply = runner.run(
        """
        ran_as_main = __name__ == "__main__"
        return_values = {"name": __name__, "as_main": ran_as_main}
        """
    )
    assert reply["Result"] == {"name": "builtins", "as_main": False}

    reply = runner.run("return_values = {'file': __file__}\n", request_id="req-2")
    assert reply["Type"] == "error"
    assert "NameError" in reply["ErrorMessage"]


def test_an_entrypoint_in_a_subfolder_of_the_code_folder_runs(runner):
    reply = runner.run(
        "return_values = {'ok': True}\n", entrypoint="sub/folder/entry.py"
    )

    assert reply["Result"] == {"ok": True}


def test_an_absolute_entrypoint_inside_the_code_folder_runs(runner, code_dir):
    path = runner.write("return_values = {'ok': True}\n", "entry.py")

    reply = runner.run(entrypoint=str(path))

    assert reply["Result"] == {"ok": True}


def test_an_entrypoint_with_a_byte_order_mark_runs(runner, code_dir):
    (code_dir / "entry.py").write_bytes(b"\xef\xbb\xbfreturn_values = {'ok': True}\n")

    assert runner.run()["Result"] == {"ok": True}


def test_an_entrypoint_that_raises_is_answered_with_its_traceback_and_exit_code_1(
    runner,
):
    reply = runner.run(
        """
        def fail():
            raise ValueError("boom")
        fail()
        """
    )

    assert reply["Type"] == "error"
    assert reply["ExitCode"] == 1
    assert reply["RequestId"] == "req-1"
    assert "ValueError: boom" in reply["ErrorMessage"]
    assert "entry.py" in reply["ErrorMessage"]


def test_a_syntax_error_in_the_entrypoint_is_answered_as_an_error(runner):
    reply = runner.run("def broken(:\n    pass\n")

    assert reply["Type"] == "error"
    assert reply["ExitCode"] == 1
    assert "SyntaxError" in reply["ErrorMessage"]
    assert "entry.py" in reply["ErrorMessage"]


def test_a_missing_entrypoint_is_answered_as_an_error(runner):
    reply = runner.run(entrypoint="nothing_here.py")

    assert reply["Type"] == "error"
    assert reply["ExitCode"] == 1
    assert "FileNotFoundError" in reply["ErrorMessage"]


def test_sys_exit_inside_the_entrypoint_is_reported_as_an_error(runner):
    reply = runner.run("import sys\nsys.exit(3)\n")

    assert reply["Type"] == "error"
    assert reply["ExitCode"] == 1
    assert "sys.exit(3)" in reply["ErrorMessage"]
    assert "return_values" in reply["ErrorMessage"]


def test_sys_exit_with_no_code_or_a_message_is_reported_with_that_code(runner):
    assert "sys.exit(None)" in runner.run("import sys\nsys.exit()\n")["ErrorMessage"]
    assert "sys.exit('bye')" in runner.run("raise SystemExit('bye')\n")["ErrorMessage"]


def test_sys_exit_is_answered_even_when_the_entrypoint_staged_a_model(
    runner, worker, fake_mlflow
):
    reply = runner.run(
        """
        import sys
        register_model(object(), "m", "sklearn")
        sys.exit(0)
        """
    )

    assert reply["Type"] == "error"
    assert worker._pending_model_registrations == []
    assert not Path(fake_mlflow.saved[0][1]).exists()


def test_a_cancel_that_lands_inside_the_entrypoint_is_an_error_reply(runner, worker):
    reply = runner.run(
        "raise WorkerCancelled()\n",
        parameters={"WorkerCancelled": worker.WorkerCancelled},
    )

    assert reply["Type"] == "error"
    assert "WorkerCancelled" in reply["ErrorMessage"]


@pytest.mark.parametrize("name", ["KeyboardInterrupt", "WorkerCancelled"])
def test_anything_that_escapes_run_is_still_answered(runner, worker, monkeypatch, name):
    # a cancel can land outside _run's own try block, and then it is not an Exception _run could answer for itself
    exception = (
        KeyboardInterrupt if name == "KeyboardInterrupt" else worker.WorkerCancelled
    )

    def interrupted(*args):
        raise exception()

    monkeypatch.setattr(worker, "_run", interrupted)
    worker._begin_request("req-1")
    worker._pending_model_registrations.append({"Name": "m", "LocalPath": "nowhere"})

    reply = runner.run(entrypoint="whatever.py")

    assert reply["Type"] == "error"
    assert reply["ExitCode"] == 1
    assert exception.__name__ in reply["ErrorMessage"]
    assert worker._pending_model_registrations == []
    assert worker._running_request_id is None


def test_a_return_value_that_is_not_json_is_answered_with_the_offending_names(
    wire_runner,
):
    import numpy as np

    reply = wire_runner.run(
        """
        import numpy as np
        return_values = {"fine": 1, "count": np.int64(3), "other": {1, 2}}
        """
    )

    assert reply["Type"] == "error"
    assert reply["ExitCode"] == 1
    assert reply["RequestId"] == "req-1"
    message = reply["ErrorMessage"]
    assert "could not be sent back as JSON" in message
    assert "'count' (numpy.int64)" in message
    assert "'other' (builtins.set)" in message
    assert "'fine'" not in message
    assert np is not None


def test_a_return_value_that_cannot_be_blamed_on_one_key_gets_the_general_message(
    wire_runner,
):
    # every value is serialisable on its own; the dictionary's keys are what json refuses
    reply = wire_runner.run("return_values = {(1, 2): 'x'}\n")

    assert reply["Type"] == "error"
    assert reply["ErrorMessage"].startswith(
        "The entrypoint's return_values could not be sent back as JSON ("
    )
    assert "'" not in reply["ErrorMessage"].split("(", 1)[0].split("values", 1)[1]


def test_a_return_value_that_is_not_json_discards_the_models_the_run_staged(
    wire_runner, worker, fake_mlflow
):
    reply = wire_runner.run(
        """
        register_model(object(), "m", "sklearn")
        return_values = {"bad": object()}
        """
    )

    assert reply["Type"] == "error"
    staged = Path(fake_mlflow.saved[0][1])
    assert not staged.exists()
    assert "RegisteredModels" not in reply


def test_pinned_return_values_that_is_not_a_dictionary_is_answered_with_an_attribute_error(
    runner,
):
    # serialize_table_results calls .items() on whatever the entrypoint called return_values. The run fails, with
    # the reason an AttributeError's text rather than a message about return_values.
    reply = runner.run("return_values = [1, 2, 3]\n")

    assert reply["Type"] == "error"
    assert "AttributeError" in reply["ErrorMessage"]
    assert "items" in reply["ErrorMessage"]


def test_a_dataframe_in_return_values_is_serialised_as_a_table_with_the_handle(
    runner, worker, monkeypatch
):
    calls = []

    def fake_to_table(df, execution_handle):
        calls.append((df, execution_handle))
        return {"table": list(df.columns)}

    monkeypatch.setattr(worker, "to_table", fake_to_table)
    monkeypatch.setattr(
        worker.ContractSerializer,
        "Serialize",
        staticmethod(lambda value: json.dumps(value)),
    )

    reply = runner.run(
        """
        import pandas as pd
        return_values = {"df": pd.DataFrame({"a": [1]}), "n": 1}
        """,
        handle=HANDLE,
    )

    assert reply["Result"] == {"df": json.dumps({"table": ["a"]}), "n": 1}
    assert calls[0][1] == HANDLE


def test_the_running_request_is_cleared_after_every_kind_of_run(runner, worker):
    for index, source in enumerate(
        ["return_values = {}\n", "raise ValueError()\n", "import sys\nsys.exit(1)\n"]
    ):
        worker._begin_request("req-1")
        runner.run(source, request_id="req-1")
        assert worker._running_request_id is None, index


# --- the entrypoint has to be inside the DataLab's code folder -------------------------------


@pytest.mark.parametrize(
    "entrypoint",
    [
        "../outside.py",
        "sub/../../outside.py",
        "..\\outside.py",
        ".",
        "",
        "../code-evil/entry.py",
    ],
)
def test_an_entrypoint_outside_the_code_folder_is_refused(runner, code_dir, entrypoint):
    source = "open('ran', 'w').close()\nreturn_values = {}\n"
    (code_dir.parent / "outside.py").write_text(source, encoding="utf-8")
    (code_dir.parent / "code-evil").mkdir()
    (code_dir.parent / "code-evil" / "entry.py").write_text(source, encoding="utf-8")

    reply = runner.run(entrypoint=entrypoint)

    assert reply["Type"] == "error"
    assert reply["ExitCode"] == 1
    assert (
        "is not inside the DataLab's code folder, so it was not run."
        in reply["ErrorMessage"]
    )
    assert f"Entrypoint '{entrypoint}'" in reply["ErrorMessage"]
    assert not (code_dir / "ran").exists()
    assert not (code_dir.parent / "ran").exists()


def test_an_absolute_entrypoint_outside_the_code_folder_is_refused(runner, tmp_path):
    outside = tmp_path / "elsewhere.py"
    outside.write_text("return_values = {'ran': True}\n", encoding="utf-8")

    reply = runner.run(entrypoint=str(outside))

    assert reply["Type"] == "error"
    assert "is not inside the DataLab's code folder" in reply["ErrorMessage"]


def test_an_entrypoint_on_another_drive_is_refused(runner):
    other = (
        "Z:\\code\\entry.py" if not os.getcwd().upper().startswith("Z") else "Y:\\x.py"
    )

    reply = runner.run(entrypoint=other)

    assert reply["Type"] == "error"
    assert "is not inside the DataLab's code folder" in reply["ErrorMessage"]


def test_an_entrypoint_inside_the_code_folder_is_matched_ignoring_case(
    runner, code_dir
):
    runner.write("return_values = {'ok': True}\n", "Entry.py")

    reply = runner.run(entrypoint=str(code_dir).upper() + "\\ENTRY.PY")

    assert reply["Result"] == {"ok": True}


def test_an_entrypoint_reached_through_a_junction_out_of_the_code_folder_is_refused(
    runner, code_dir, tmp_path
):
    # The check compares real paths, so a junction inside the code folder that points outside it does not get past
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "entry.py").write_text(
        "return_values = {'ran': True}\n", encoding="utf-8"
    )
    made = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(code_dir / "link"), str(outside)],
        capture_output=True,
    )
    if made.returncode != 0:
        pytest.skip("a directory junction could not be created here")

    reply = runner.run(entrypoint="link/entry.py")

    assert reply["Type"] == "error"
    assert "not inside the DataLab's code folder" in reply["ErrorMessage"]
    assert "Result" not in reply


def test_an_entrypoint_reached_through_a_junction_that_stays_inside_the_code_folder_runs(
    runner, code_dir
):
    inside = code_dir / "real"
    inside.mkdir()
    (inside / "entry.py").write_text(
        "return_values = {'ran': True}\n", encoding="utf-8"
    )
    made = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(code_dir / "alias"), str(inside)],
        capture_output=True,
    )
    if made.returncode != 0:
        pytest.skip("a directory junction could not be created here")

    reply = runner.run(entrypoint="alias/entry.py")

    assert reply["Result"] == {"ran": True}


# ----------------------------------------------------------------------------------------------
# Table parameters and results
# ----------------------------------------------------------------------------------------------


def test_a_table_wrapper_parameter_becomes_a_table(worker):
    resolved = worker.resolve_table_parameters({"t": {"__DlaeTable": TABLE_JSON}})

    assert isinstance(resolved["t"], Table)
    assert resolved["t"].TableName == "t"


def test_plain_parameters_pass_through_unchanged(worker):
    parameters = {
        "none": None,
        "number": 1.5,
        "text": "x",
        "flag": True,
        "items": [1, {"__DlaeTable": TABLE_JSON}],
        "mapping": {"a": 1},
    }

    resolved = worker.resolve_table_parameters(parameters)

    assert resolved == parameters
    assert resolved["mapping"] is parameters["mapping"]
    assert resolved["items"] is parameters["items"]


def test_a_dictionary_nested_inside_another_is_never_resolved(worker):
    inner = {"__DlaeTable": TABLE_JSON}
    parameters = {"outer": {"inner": inner}}

    resolved = worker.resolve_table_parameters(parameters)

    assert resolved["outer"]["inner"] is inner


def test_resolving_does_not_change_the_dictionary_it_is_given(worker):
    parameters = {"t": {"__DlaeTable": TABLE_JSON}, "x": 1}

    worker.resolve_table_parameters(parameters)

    assert parameters["t"] == {"__DlaeTable": TABLE_JSON}


def test_a_table_parameter_reaches_the_entrypoint_as_a_table(runner):
    reply = runner.run(
        """
        return_values = {"type": type(t).__name__, "name": t.TableName, "x": x}
        """,
        parameters={"t": {"__DlaeTable": TABLE_JSON}, "x": None},
    )

    assert reply["Result"] == {"type": "Table", "name": "t", "x": None}


def test_a_table_wrapper_with_text_that_is_not_a_table_fails_the_run(runner):
    reply = runner.run(
        "return_values = {}\n", parameters={"t": {"__DlaeTable": "not json"}}
    )

    assert reply["Type"] == "error"
    assert reply["ExitCode"] == 1


class FakeTableService:
    """Answers CreateTable with a table, as the real service does."""

    def __init__(self):
        self.bodies = []

    def CreateTable(self, body):
        self.bodies.append(body)
        return codec.decode(TABLE_JSON)


@pytest.fixture
def table_service():
    session = Session(uri=URI, auth_mode=AuthMode.TOKEN, credentials="token-for-tests")
    session.register()
    service = FakeTableService()
    session.services["TableService"] = service
    return service


def test_a_dataframe_result_becomes_a_serialised_table(worker, table_service):
    df = pd.DataFrame({"a": [1, 2]})

    result = worker.serialize_table_results({"df": df, "n": 3}, HANDLE)

    assert isinstance(result["df"], str)
    assert json.loads(result["df"])["__type"] == "Table:#CompAnalytics.Contracts.Tables"
    assert result["n"] == 3
    assert len(table_service.bodies) == 1
    assert json.loads(table_service.bodies[0])["Rows"] == [[1], [2]]


def test_results_that_are_not_dataframes_are_left_alone(worker, table_service):
    other = object()
    result = {"text": "x", "none": None, "list": [pd.DataFrame()], "other": other}

    returned = worker.serialize_table_results(result, HANDLE)

    assert returned is result
    assert returned["other"] is other
    assert isinstance(returned["list"][0], pd.DataFrame)
    assert table_service.bodies == []


def test_serialising_an_empty_result_does_nothing(worker):
    assert worker.serialize_table_results({}, None) == {}


# ----------------------------------------------------------------------------------------------
# Model registration helpers
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "model",
        "my model v2",
        "a.b",
        "a b.c",
        "model-1_final (2)",
        ".hidden",
        "Ünïcödé",
        " leading space",
        "x" * 256,
        "😀" * 100,
    ],
)
def test_a_name_that_works_as_a_folder_name_is_accepted(worker, name):
    worker._check_model_name(name)


@pytest.mark.parametrize("name", ["", " ", "   ", "\t", None, 5, b"model", ["model"]])
def test_a_missing_or_blank_name_is_refused(worker, name):
    with pytest.raises(ValueError, match="A model needs a name."):
        worker._check_model_name(name)


def test_a_name_over_256_characters_is_refused(worker):
    worker._check_model_name("x" * 256)
    with pytest.raises(ValueError, match="at most 256 characters"):
        worker._check_model_name("x" * 257)


@pytest.mark.parametrize("character", list('\\/:*?"<>|'))
def test_each_character_that_cannot_be_in_a_folder_name_is_refused(worker, character):
    with pytest.raises(ValueError, match="isn't allowed in a folder name") as error:
        worker._check_model_name(f"a{character}b")

    assert "a" + character + "b" in str(error.value)


@pytest.mark.parametrize("code", [0, 1, 9, 10, 13, 27, 31])
def test_a_control_character_in_a_name_is_refused(worker, code):
    with pytest.raises(ValueError, match="isn't allowed in a folder name"):
        worker._check_model_name("a" + chr(code) + "b")


@pytest.mark.parametrize(
    "name", [".", "..", "...", "name.", "name..", "name ", "name. ", "name .", "a b "]
)
def test_a_name_of_dots_or_ending_in_a_dot_or_space_is_refused(worker, name):
    with pytest.raises(ValueError, match="made of dots or end with a dot or a space"):
        worker._check_model_name(name)


def test_a_name_the_launcher_would_refuse_for_its_length_is_refused_here_too(worker):
    # 200 emoji are 200 code points but 400 UTF-16 units: this check passes it, the launcher rejects it after training
    name = "😀" * 200
    assert len(name.encode("utf-16-le")) // 2 > 256

    with pytest.raises(ValueError):
        worker._check_model_name(name)


def test_register_model_refuses_a_bad_name_before_it_needs_mlflow(worker, monkeypatch):
    monkeypatch.setitem(sys.modules, "mlflow", None)

    with pytest.raises(ValueError, match="A model needs a name."):
        worker.register_model(object(), "", "sklearn")
    with pytest.raises(ValueError, match="folder name"):
        worker.register_model(object(), "a/b", "sklearn")

    assert worker._pending_model_registrations == []


def test_register_model_says_so_when_mlflow_is_not_installed(worker, monkeypatch):
    monkeypatch.setitem(sys.modules, "mlflow", None)

    with pytest.raises(ImportError):
        worker.register_model(object(), "m", "sklearn")

    assert worker._pending_model_registrations == []


def test_register_model_refuses_a_flavor_mlflow_does_not_have(worker, fake_mlflow):
    with pytest.raises(
        ValueError, match="'nonsense' is not a recognized MLflow flavor"
    ):
        worker.register_model(object(), "m", "nonsense")

    assert worker._pending_model_registrations == []
    assert fake_mlflow.saved == []


def test_pinned_a_flavor_that_is_not_a_string_is_a_type_error_and_needs_a_decision(
    worker, fake_mlflow
):
    # getattr(mlflow, None) raises TypeError, which is not the AttributeError the friendly message is written for
    with pytest.raises(TypeError):
        worker.register_model(object(), "m", None)


def test_register_model_stages_the_model_and_records_it(worker, fake_mlflow, tmp_path):
    model = object()

    worker.register_model(model, "my model", "sklearn")

    ((flavor, path, saved_model),) = fake_mlflow.saved
    assert (flavor, saved_model) == ("sklearn", model)
    assert Path(path).parent == tmp_path / "temp" / "dlae_model_registrations"
    assert Path(path).is_dir()
    assert worker._pending_model_registrations == [
        {"Name": "my model", "LocalPath": path}
    ]


def test_register_model_with_pyfunc_passes_the_model_as_the_python_model(
    worker, fake_mlflow
):
    model = object()

    worker.register_model(model, "custom", "pyfunc")

    ((flavor, path, saved_model),) = fake_mlflow.saved
    assert (flavor, saved_model) == ("pyfunc", model)
    assert worker._pending_model_registrations[0]["Name"] == "custom"


def test_each_registration_gets_a_folder_of_its_own(worker, fake_mlflow):
    worker.register_model(object(), "m", "sklearn")
    worker.register_model(object(), "m", "sklearn")

    first, second = worker._pending_model_registrations
    assert first["Name"] == second["Name"] == "m"
    assert first["LocalPath"] != second["LocalPath"]


def test_a_model_that_fails_to_save_leaves_no_partial_folder_behind(
    worker, fake_mlflow, monkeypatch
):
    # Nothing is recorded for the failed registration, so nothing else would ever remove what mlflow had written so far
    def partial_save(model, path):
        os.makedirs(path)
        raise RuntimeError("disk full")

    monkeypatch.setattr(fake_mlflow.sklearn, "save_model", partial_save)

    with pytest.raises(RuntimeError, match="disk full"):
        worker.register_model(object(), "m", "sklearn")

    registrations = Path(tempfile.gettempdir()) / "dlae_model_registrations"
    assert not registrations.exists() or list(registrations.iterdir()) == []
    assert worker._pending_model_registrations == []


def test_take_hands_over_the_registrations_and_empties_the_list(worker, tmp_path):
    first = _stage_model_dir(tmp_path, "one")
    worker._pending_model_registrations.append({"Name": "one", "LocalPath": str(first)})

    taken = worker.take_pending_model_registrations()

    assert taken == [{"Name": "one", "LocalPath": str(first)}]
    assert worker._pending_model_registrations == []
    assert first.is_dir(), "taking a registration must not delete what it points at"
    assert worker.take_pending_model_registrations() == []


def test_discard_pending_deletes_the_folders_and_empties_the_list(worker, tmp_path):
    folders = [_stage_model_dir(tmp_path, name) for name in ("one", "two")]
    for folder in folders:
        worker._pending_model_registrations.append(
            {"Name": folder.name, "LocalPath": str(folder)}
        )

    worker.discard_pending_model_registrations()

    assert worker._pending_model_registrations == []
    assert not any(folder.exists() for folder in folders)


def test_discarding_registrations_whose_folder_is_already_gone_is_not_an_error(
    worker, tmp_path
):
    worker._pending_model_registrations.append(
        {"Name": "gone", "LocalPath": str(tmp_path / "never made")}
    )

    worker.discard_pending_model_registrations()
    worker._discard_registrations([{"Name": "gone", "LocalPath": str(tmp_path / "x")}])
    worker._discard_registrations(None)
    worker._discard_registrations([])

    assert worker._pending_model_registrations == []


def test_a_run_that_registered_a_model_hands_it_over_in_the_reply(
    runner, worker, fake_mlflow
):
    reply = runner.run(
        """
        register_model("trained", "m", "sklearn")
        return_values = {"ok": True}
        """
    )

    path = fake_mlflow.saved[0][1]
    assert reply["Type"] == "result"
    assert reply["RegisteredModels"] == [{"Name": "m", "LocalPath": path}]
    assert Path(
        path
    ).is_dir(), "the launcher copies it from here, so it must still exist"
    assert worker._pending_model_registrations == []


def test_the_registrations_of_a_run_that_failed_are_discarded_not_handed_on(
    runner, worker, fake_mlflow
):
    failed = runner.run(
        """
        register_model("trained", "m", "sklearn")
        raise RuntimeError("after registering")
        """,
        request_id="r1",
    )
    after = runner.run("return_values = {}\n", request_id="r2")

    assert failed["Type"] == "error"
    assert "RegisteredModels" not in failed
    assert not Path(fake_mlflow.saved[0][1]).exists()
    assert after["Type"] == "result"
    assert "RegisteredModels" not in after
    assert worker._pending_model_registrations == []


def test_a_registration_left_pending_is_not_carried_into_the_next_run(
    runner, worker, tmp_path
):
    stale = _stage_model_dir(tmp_path, "stale")
    worker._pending_model_registrations.append(
        {"Name": "stale", "LocalPath": str(stale)}
    )

    reply = runner.run("return_values = {}\n")

    assert reply["Type"] == "result"
    assert "RegisteredModels" not in reply
    assert not stale.exists()


def test_a_run_that_failed_before_the_entrypoint_discards_a_stale_registration_too(
    runner, worker, tmp_path
):
    stale = _stage_model_dir(tmp_path, "stale")
    worker._pending_model_registrations.append(
        {"Name": "stale", "LocalPath": str(stale)}
    )

    reply = runner.run("return_values = {}\n", token=None)

    assert reply["Type"] == "error"
    assert not stale.exists()


def test_a_second_run_only_gets_its_own_registrations(runner, fake_mlflow):
    first = runner.run('register_model("a", "first", "sklearn")\n', request_id="r1")
    second = runner.run('register_model("b", "second", "xgboost")\n', request_id="r2")

    assert [m["Name"] for m in first["RegisteredModels"]] == ["first"]
    assert [m["Name"] for m in second["RegisteredModels"]] == ["second"]


def test_load_model_returns_the_native_flavor_the_model_was_saved_with(
    worker, fake_mlflow, monkeypatch
):
    fake_mlflow.models.Model.flavors_by_path = {
        "C:/models/m": {"python_function": {}, "sklearn": {}}
    }
    monkeypatch.setattr(worker, "_model_dependency_paths", {"m": "C:/models/m"})

    assert worker.load_model("m") == ("loaded by sklearn", "C:/models/m")


def test_load_model_falls_back_to_pyfunc_when_there_is_no_native_flavor(
    worker, fake_mlflow, monkeypatch
):
    fake_mlflow.models.Model.flavors_by_path = {"p": {"python_function": {}}}
    monkeypatch.setattr(worker, "_model_dependency_paths", {"m": "p"})

    assert worker.load_model("m") == ("loaded by pyfunc", "p")


def test_load_model_refuses_a_model_that_was_not_declared(worker, fake_mlflow):
    with pytest.raises(ValueError, match="No model dependency named 'other'"):
        worker.load_model("other")


def test_a_run_reads_the_model_paths_it_was_dispatched_with(runner, fake_mlflow):
    fake_mlflow.models.Model.flavors_by_path = {"C:/m/1": {"xgboost": {}}}

    declared = runner.run(
        "return_values = {'model': list(load_model('m'))}\n",
        models={"m": "C:/m/1"},
    )
    undeclared = runner.run("load_model('m')\n", request_id="r2", models={})

    assert declared["Result"] == {"model": ["loaded by xgboost", "C:/m/1"]}
    assert undeclared["Type"] == "error"
    assert "No model dependency named 'm'" in undeclared["ErrorMessage"]


# ----------------------------------------------------------------------------------------------
# Sending the reply
# ----------------------------------------------------------------------------------------------


def test_write_frame_sends_a_little_endian_length_then_the_payload_and_flushes(
    worker, monkeypatch
):
    events = []
    monkeypatch.setattr(
        worker.win32file,
        "WriteFile",
        lambda pipe, data: events.append(("write", pipe, data)),
    )
    monkeypatch.setattr(
        worker.win32file,
        "FlushFileBuffers",
        lambda pipe: events.append(("flush", pipe)),
    )

    worker._write_frame(b"hello", "PIPE")

    assert events == [
        ("write", "PIPE", struct.pack("<I", 5)),
        ("write", "PIPE", b"hello"),
        ("flush", "PIPE"),
    ]


def test_send_message_sends_the_message_as_json(worker, monkeypatch):
    frames = []
    monkeypatch.setattr(
        worker, "_write_frame", lambda payload, pipe: frames.append((payload, pipe))
    )

    worker.send_message({"Type": "pong"}, "PIPE")

    assert frames == [(b'{"Type": "pong"}', "PIPE")]


def test_a_reply_that_cannot_be_written_is_swallowed_and_its_models_are_discarded(
    worker, tmp_path, monkeypatch, capsys
):
    staged = _stage_model_dir(tmp_path, "staged")

    def broken(payload, pipe):
        raise OSError("pipe closed")

    monkeypatch.setattr(worker, "_write_frame", broken)

    worker._send_reply(
        {
            "Type": "result",
            "RequestId": "r9",
            "Result": {},
            "RegisteredModels": [{"Name": "m", "LocalPath": str(staged)}],
        },
        "PIPE",
    )

    assert not staged.exists()
    assert (
        "Could not send the reply to request r9: pipe closed" in capsys.readouterr().out
    )


def test_a_reply_that_is_not_json_is_replaced_by_an_error_for_the_same_request(
    worker, monkeypatch
):
    frames = []
    monkeypatch.setattr(
        worker, "_write_frame", lambda payload, pipe: frames.append(json.loads(payload))
    )

    worker._send_reply(
        {"Type": "result", "RequestId": "r5", "Result": {"x": object()}, "ExitCode": 0},
        "PIPE",
    )

    assert len(frames) == 1
    assert frames[0]["Type"] == "error"
    assert frames[0]["RequestId"] == "r5"
    assert frames[0]["ExitCode"] == 1
    assert "'x' (builtins.object)" in frames[0]["ErrorMessage"]


def test_the_description_of_an_unserialisable_result(worker):
    described = worker._describe_unserializable(
        {"a": 1, "b": {1}, "c": object()}, ValueError("nope")
    )

    assert "'b' (builtins.set), 'c' (builtins.object)" in described
    assert "(nope)" in described
    assert "'a'" not in described
    assert worker._describe_unserializable([1], ValueError("nope")) == (
        "The entrypoint's return_values could not be sent back as JSON (nope)."
    )


# ----------------------------------------------------------------------------------------------
# Cancel handling
# ----------------------------------------------------------------------------------------------


def test_end_request_only_clears_the_request_it_is_given(worker):
    worker._begin_request("r1")

    worker._end_request("r2")
    assert worker._running_request_id == "r1"

    worker._end_request("r1")
    assert worker._running_request_id is None

    worker._end_request("r1")
    assert worker._running_request_id is None


def test_a_new_request_replaces_the_one_before_it(worker):
    worker._begin_request("r1")
    worker._begin_request("r2")

    worker._end_request("r1")

    assert worker._running_request_id == "r2"


class _FakeThread:
    """A thread that cannot be stopped: a cancel for it has to end the process."""

    ident = 0

    def __init__(self):
        self.joined_with = None

    def is_alive(self):
        return True

    def join(self, timeout=None):
        self.joined_with = timeout


@pytest.fixture
def live_thread():
    stop = threading.Event()
    thread = threading.Thread(target=stop.wait, daemon=True)
    thread.start()
    yield thread
    stop.set()
    thread.join(5)


@pytest.mark.parametrize(
    "request_id, running",
    [("other", "r1"), ("r1", None), (None, "r1"), (None, None), ("r1", "r1 ")],
)
def test_a_cancel_for_a_request_that_is_not_running_is_ignored(
    worker, live_thread, no_exit, capsys, request_id, running
):
    worker._begin_request(running)

    worker._cancel_request(request_id, live_thread)

    assert (
        f"ignoring cancel for request {request_id}, which is not running"
        in capsys.readouterr().out
    )
    assert live_thread.is_alive()


def test_a_cancel_with_no_thread_is_ignored(worker, no_exit, capsys):
    worker._begin_request("r1")

    worker._cancel_request("r1", None)

    assert "ignoring cancel for request r1" in capsys.readouterr().out


def test_a_cancel_for_a_thread_that_has_already_ended_is_ignored(
    worker, no_exit, capsys
):
    thread = threading.Thread(target=lambda: None)
    thread.start()
    thread.join()
    worker._begin_request("r1")

    worker._cancel_request("r1", thread)

    assert "ignoring cancel for request r1" in capsys.readouterr().out


def test_a_cancel_for_the_running_request_interrupts_its_thread(worker, no_exit):
    started = threading.Event()
    outcome = []

    def spin():
        try:
            started.set()
            while True:
                time.sleep(0.01)
        except worker.WorkerCancelled:
            outcome.append("cancelled")

    thread = threading.Thread(target=spin, daemon=True)
    worker._begin_request("r1")
    thread.start()
    assert started.wait(5)

    worker._cancel_request("r1", thread)

    assert outcome == ["cancelled"]
    assert not thread.is_alive()


def test_a_cancel_that_does_not_take_ends_the_process(worker, monkeypatch):
    exits = []
    monkeypatch.setattr(os, "_exit", lambda code: exits.append(code))
    thread = _FakeThread()
    worker._begin_request("r1")

    worker._cancel_request("r1", thread)

    assert thread.joined_with == 15.0
    assert exits == [1]


def test_a_cancelled_run_is_answered_with_an_error_and_the_worker_is_free_again(
    runner, worker, no_exit, monkeypatch
):
    started = threading.Event()
    sent = threading.Event()
    replies = []
    monkeypatch.setattr(
        worker,
        "_send_reply",
        lambda response, pipe: (replies.append(response), sent.set()),
    )
    thread = threading.Thread(
        target=worker.run_entrypoint,
        args=(
            "entry.py",
            {"started": started},
            "r1",
            "token-A",
            None,
            {},
            None,
        ),
        daemon=True,
    )
    runner.write(
        """
        import time
        started.set()
        while True:
            time.sleep(0.01)
        """
    )
    worker._begin_request("r1")
    thread.start()
    assert started.wait(10)

    worker._cancel_request("r1", thread)

    assert sent.wait(10)
    (reply,) = replies
    assert reply["Type"] == "error"
    assert reply["RequestId"] == "r1"
    assert "WorkerCancelled" in reply["ErrorMessage"]
    assert worker._running_request_id is None
    assert not thread.is_alive()


def test_a_stale_cancel_does_not_interrupt_the_run_that_follows(
    worker, no_exit, live_thread
):
    # the cancel was for r1, which has ended; r2 is what the worker is running now
    worker._begin_request("r1")
    worker._end_request("r1")
    worker._begin_request("r2")

    worker._cancel_request("r1", live_thread)

    assert live_thread.is_alive()
    assert worker._running_request_id == "r2"


# ----------------------------------------------------------------------------------------------
# The pipe server, with the win32 pipe functions faked
# ----------------------------------------------------------------------------------------------


def _frames(*messages):
    data = b""
    for message in messages:
        payload = (
            message
            if isinstance(message, bytes)
            else json.dumps(message).encode("utf-8")
        )
        data += struct.pack("<I", len(payload)) + payload
    return data


class FakePipe:
    """Stands in for the win32 pipe calls. Reading past the end of the incoming data returns nothing, which ends the
    server's loop the way a client that disconnected would."""

    def __init__(self, worker, monkeypatch, incoming):
        self.incoming = incoming
        self.written = []
        self.calls = []
        monkeypatch.setattr(worker, "_pipe_security_attributes", lambda: "SECURITY")
        pipe = worker.win32pipe
        file = worker.win32file
        monkeypatch.setattr(pipe, "CreateNamedPipe", self.create)
        monkeypatch.setattr(
            pipe,
            "ConnectNamedPipe",
            lambda handle, overlapped: self.calls.append("connect"),
        )
        monkeypatch.setattr(
            pipe, "PeekNamedPipe", lambda handle, size: (b"", 1 << 20, 0)
        )
        monkeypatch.setattr(
            pipe, "DisconnectNamedPipe", lambda handle: self.calls.append("disconnect")
        )
        monkeypatch.setattr(file, "ReadFile", self.read)
        monkeypatch.setattr(
            file, "WriteFile", lambda handle, data: self.written.append(data)
        )
        monkeypatch.setattr(file, "FlushFileBuffers", lambda handle: None)
        monkeypatch.setattr(
            file, "CloseHandle", lambda handle: self.calls.append("close")
        )

    def create(self, *args):
        self.calls.append(("create", args))
        return "PIPE"

    def read(self, handle, count):
        chunk, self.incoming = self.incoming[:count], self.incoming[count:]
        return 0, chunk

    def replies(self):
        decoded = []
        data = b"".join(self.written)
        while data:
            (length,) = struct.unpack("<I", data[:4])
            decoded.append(json.loads(data[4 : 4 + length]))
            data = data[4 + length :]
        return decoded


def test_a_ping_is_answered_with_a_pong_and_the_pipe_is_closed_at_the_end(
    worker, monkeypatch
):
    pipe = FakePipe(worker, monkeypatch, _frames({"Type": "ping"}, {"Type": "ping"}))

    worker.win_pipe_server("\\\\.\\pipe\\test")

    assert pipe.replies() == [{"Type": "pong"}, {"Type": "pong"}]
    assert pipe.calls[0][0] == "create"
    assert pipe.calls[0][1][0] == "\\\\.\\pipe\\test"
    assert pipe.calls[-2:] == ["disconnect", "close"]


def test_the_pipe_is_created_as_the_first_instance_for_one_client(worker, monkeypatch):
    pipe = FakePipe(worker, monkeypatch, b"")

    worker.win_pipe_server("\\\\.\\pipe\\test")

    _, (name, open_mode, pipe_mode, instances, out_size, in_size, timeout, security) = (
        pipe.calls[0]
    )
    assert open_mode & worker.FILE_FLAG_FIRST_PIPE_INSTANCE
    assert open_mode & worker.win32pipe.PIPE_ACCESS_DUPLEX
    assert instances == 1
    assert security == "SECURITY"


def test_a_pipe_name_that_is_already_in_use_ends_the_worker(
    worker, monkeypatch, capsys
):
    FakePipe(worker, monkeypatch, b"")

    def taken(*args):
        raise pywintypes.error(5, "CreateNamedPipe", "Access is denied.")

    monkeypatch.setattr(worker.win32pipe, "CreateNamedPipe", taken)

    with pytest.raises(SystemExit) as stopped:
        worker.win_pipe_server("\\\\.\\pipe\\test")

    assert stopped.value.code == 1
    assert "Could not create the pipe" in capsys.readouterr().out


def test_an_execute_message_starts_the_run_on_its_own_thread(worker, monkeypatch):
    seen = []
    ran = threading.Event()

    def fake_run(*args):
        seen.append((args, threading.current_thread()))
        ran.set()

    monkeypatch.setattr(worker, "run_entrypoint", fake_run)
    pipe = FakePipe(
        worker,
        monkeypatch,
        _frames(
            {
                "Type": "execute",
                "RequestId": "r1",
                "Entrypoint": "entry.py",
                "Parameters": {"x": None},
                "CallerToken": "token-A",
                "Handle": HANDLE,
                "ModelDependencyPaths": None,
            }
        ),
    )

    worker.win_pipe_server("\\\\.\\pipe\\test")

    assert ran.wait(5)
    ((args, thread),) = seen
    assert args == ("entry.py", {"x": None}, "r1", "token-A", HANDLE, {}, "PIPE")
    assert thread is not threading.main_thread()
    assert worker._running_request_id == "r1"
    assert pipe.replies() == []


def test_an_execute_message_without_a_token_handle_or_models_uses_defaults(
    worker, monkeypatch
):
    seen = []
    ran = threading.Event()
    monkeypatch.setattr(
        worker, "run_entrypoint", lambda *args: (seen.append(args), ran.set())
    )
    FakePipe(
        worker,
        monkeypatch,
        _frames(
            {
                "Type": "execute",
                "RequestId": "r1",
                "Entrypoint": "e.py",
                "Parameters": {},
            }
        ),
    )

    worker.win_pipe_server("\\\\.\\pipe\\test")

    assert ran.wait(5)
    assert seen == [("e.py", {}, "r1", None, None, {}, "PIPE")]


def test_a_cancel_message_is_handed_the_request_and_the_thread_that_is_running(
    worker, monkeypatch
):
    cancels = []
    release = threading.Event()
    monkeypatch.setattr(worker, "run_entrypoint", lambda *args: release.wait(5))
    monkeypatch.setattr(
        worker,
        "_cancel_request",
        lambda request_id, thread: cancels.append((request_id, thread)),
    )
    FakePipe(
        worker,
        monkeypatch,
        _frames(
            {"Type": "cancel", "RequestId": "early"},
            {
                "Type": "execute",
                "RequestId": "r1",
                "Entrypoint": "e.py",
                "Parameters": {},
            },
            {"Type": "cancel", "RequestId": "r1"},
            {"Type": "cancel"},
        ),
    )

    worker.win_pipe_server("\\\\.\\pipe\\test")
    release.set()

    assert [request_id for request_id, _ in cancels] == ["early", "r1", None]
    assert cancels[0][1] is None
    assert isinstance(cancels[1][1], threading.Thread)
    assert cancels[2][1] is cancels[1][1]


def test_a_message_of_an_unknown_type_is_ignored_and_the_loop_goes_on(
    worker, monkeypatch
):
    pipe = FakePipe(worker, monkeypatch, _frames({"Type": "mystery"}, {"Type": "ping"}))

    worker.win_pipe_server("\\\\.\\pipe\\test")

    assert pipe.replies() == [{"Type": "pong"}]


@pytest.mark.parametrize("payload", [b"{not json", b"\xff\xfe\xfa"])
def test_a_payload_that_cannot_be_read_ends_the_loop(worker, monkeypatch, payload):
    pipe = FakePipe(worker, monkeypatch, _frames(payload, {"Type": "ping"}))

    worker.win_pipe_server("\\\\.\\pipe\\test")

    assert pipe.replies() == []
    assert pipe.calls[-2:] == ["disconnect", "close"]


def test_a_message_with_no_type_ends_the_loop_and_still_closes_the_pipe(
    worker, monkeypatch
):
    pipe = FakePipe(worker, monkeypatch, _frames({"nothing": 1}, {"Type": "ping"}))

    worker.win_pipe_server("\\\\.\\pipe\\test")

    assert pipe.replies() == []
    assert pipe.calls[-2:] == ["disconnect", "close"]


def test_wait_until_readable_polls_until_enough_bytes_are_waiting(worker, monkeypatch):
    available = iter([0, 2, 3, 4, 100])
    sleeps = []
    monkeypatch.setattr(
        worker.win32pipe, "PeekNamedPipe", lambda pipe, size: (b"", next(available), 0)
    )
    monkeypatch.setattr(worker.time, "sleep", sleeps.append)

    worker._wait_until_readable("PIPE", 4, poll_interval=0.5)

    assert sleeps == [0.5, 0.5, 0.5]


def test_the_pipe_is_open_to_the_worker_account_and_the_launcher_only(
    worker, monkeypatch
):
    monkeypatch.setenv("DATALAB_LAUNCHER_SID", "S-1-5-18")

    attributes = worker._pipe_security_attributes()

    dacl = attributes.SECURITY_DESCRIPTOR.GetSecurityDescriptorDacl()
    assert dacl.GetAceCount() == 2


def test_the_pipe_cannot_be_secured_without_the_launcher_sid(worker, monkeypatch):
    monkeypatch.delenv("DATALAB_LAUNCHER_SID", raising=False)

    with pytest.raises(KeyError, match="DATALAB_LAUNCHER_SID"):
        worker._pipe_security_attributes()
