"""Offline tests for composapy.notebook.nb_wrap's cell injection and the papermill translators.

Both run in this process. Running a notebook needs a kernel, which the C# suites cover.
"""

import ast
import builtins
import json
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

nbformat = pytest.importorskip("nbformat")
pytest.importorskip("papermill")

from composapy._wire import codec  # noqa: E402
from composapy.contracts import FileReference  # noqa: E402
from composapy.notebook import nb_wrap  # noqa: E402  (imports papermill)

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


def notebook(*sources, tagged=False):
    nb = nbformat.v4.new_notebook()
    for source in sources:
        cell = nbformat.v4.new_code_cell(source=source)
        if tagged:
            cell.metadata["tags"] = ["parameters"]
        nb.cells.append(cell)
    return nb


def sources(nb):
    return [cell.source for cell in nb.cells]


def test_with_a_token_the_cells_are_session_loading_parameters_user_code_and_serialization():
    nb = notebook("print(1)")
    nb_wrap._inject_notebook(nb, Path("/run/outputs.serialized"), "token-for-tests")
    first, loading, parameters, user, last = nb.cells
    assert "Session(" in first.source and "token-for-tests" in first.source
    assert (
        "from composapy.contracts import" in loading.source
        and "return_values = {}" in loading.source
    )
    assert parameters.metadata["tags"] == ["parameters"] and parameters.source == ""
    assert user.source == "print(1)"
    assert (
        "serialize_return_values" in last.source
        and "/run/outputs.serialized" in last.source
    )


@pytest.mark.parametrize("token", [None, ""])
def test_without_a_token_no_session_cell_is_added(token):
    nb = notebook("print(1)")
    nb_wrap._inject_notebook(nb, Path("/run/outputs.serialized"), token)
    assert not any("Session" in source for source in sources(nb))
    assert "from composapy.contracts import" in nb.cells[0].source


def test_a_parameters_cell_the_user_made_is_kept_and_none_is_added():
    nb = notebook("a = 1", tagged=True)
    nb_wrap._inject_notebook(nb, Path("/run/outputs.serialized"), None)
    assert sum("parameters" in cell.metadata.get("tags", []) for cell in nb.cells) == 1


def test_no_injected_cell_mentions_dotnet():
    nb = notebook("print(1)")
    nb_wrap._inject_notebook(nb, Path("/run/outputs.serialized"), "token-for-tests")
    text = "\n".join(sources(nb))
    assert "CompAnalytics" not in text and "System" not in text.replace("composapy", "")


@pytest.mark.parametrize("token", ["abc.def.ghi", "it's", 'a"b', "back\\slash", "café"])
def test_the_token_cell_is_valid_python_and_holds_the_token_exactly(token):
    nb = notebook()
    nb_wrap._inject_implicit_auth(nb, token)
    tree = ast.parse(nb.cells[0].source)  # '' around a repr was a syntax error
    call = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Session"
    )
    assert (
        ast.literal_eval(next(k.value for k in call.keywords if k.arg == "credentials"))
        == token
    )


def test_the_package_loading_cell_defines_the_names_the_translators_use():
    nb = notebook()
    nb_wrap._inject_package_loading(nb)
    namespace = {}
    exec(nb.cells[0].source, namespace)
    for name in (
        "ContractSerializer",
        "FileReference",
        "ExecutionHandle",
        "Table",
        "return_values",
    ):
        assert name in namespace


# ----------------------------------------------------------------------------------------------
# The papermill translators
# ----------------------------------------------------------------------------------------------


def translate_and_run(parameters, monkeypatch):
    import composapy.notebook.translators  # noqa: F401  (patches papermill)
    from papermill.translators import PythonTranslator

    # Set and then remove it, so the teardown removes whatever the translated code leaves in the environment
    monkeypatch.setenv("_execution_handle", "")
    monkeypatch.delenv("_execution_handle")
    nb = notebook()
    nb_wrap._inject_package_loading(nb)
    namespace = {}
    exec(nb.cells[0].source, namespace)
    code = PythonTranslator.codify(parameters, "Parameters")
    exec(code, namespace)
    return namespace


def test_contract_parameters_survive_quotes_and_backslashes(monkeypatch):
    values = {
        "tbl": codec.decode(json.dumps(TABLE_JSON)),
        "ref": codec.decode(json.dumps(FILE_JSON)),
        "handle": codec.decode(json.dumps(HANDLE_JSON)),
    }
    namespace = translate_and_run(values, monkeypatch)
    assert (
        namespace["tbl"] == values["tbl"] and type(namespace["tbl"]).__name__ == "Table"
    )
    assert (
        namespace["ref"] == values["ref"] and namespace["ref"].Uri == FILE_JSON["Uri"]
    )
    assert namespace["handle"] == values["handle"]
    assert json.loads(os.environ["_execution_handle"]) == HANDLE_JSON


def test_plain_parameters_still_translate(monkeypatch):
    namespace = translate_and_run(
        {"n": 3, "s": "it's", "b": True, "none": None, "f": 2.5}, monkeypatch
    )
    assert (
        namespace["n"],
        namespace["s"],
        namespace["b"],
        namespace["none"],
        namespace["f"],
    ) == (3, "it's", True, None, 2.5)


def test_every_file_reference_kind_reaches_the_notebook_as_its_own_class(monkeypatch):
    from composapy.contracts import file_reference

    kinds = [
        file_reference.CsvFileReference,
        file_reference.ImageReference,
        file_reference.KmlReference,
        file_reference.KmzReference,
        file_reference.StlReference,
        file_reference.Mp3Reference,
        file_reference.WavReference,
        file_reference.VideoReference,
        file_reference.AudioReference,
    ]
    values = {
        f"ref{i}": FileReference.Create(
            "C:\\data\\f.bin", f"/CompApp/runs/x/it's {i}.bin", as_type=kind
        )
        for i, kind in enumerate(kinds)
    }
    namespace = translate_and_run(values, monkeypatch)
    for i, kind in enumerate(kinds):
        received = namespace[f"ref{i}"]
        assert type(received) is kind and received == values[f"ref{i}"]
        # the local path stays on this side; the notebook gets the server's uri only
        assert received.LocalFile is None


def test_contract_values_inside_a_list_or_a_dict_parameter_are_translated_too(
    monkeypatch,
):
    ref = codec.decode(json.dumps(FILE_JSON))
    table = codec.decode(json.dumps(TABLE_JSON))
    namespace = translate_and_run(
        {"items": [ref, 1, table], "named": {"a": ref}}, monkeypatch
    )
    assert namespace["items"] == [ref, 1, table]
    assert type(namespace["items"][2]).__name__ == "Table"
    assert namespace["named"] == {"a": ref}


def test_pinned_parameters_named_like_the_injected_names_replace_them_without_unregistering_the_session():
    from papermill.translators import PythonTranslator

    from composapy.session import get_session

    nb = notebook("print(1)")
    nb_wrap._inject_notebook(nb, Path("/run/outputs.serialized"), "token-for-tests")
    token_cell, loading_cell = nb.cells[0], nb.cells[1]
    namespace = {}
    exec(token_cell.source, namespace)  # makes and registers a token session
    exec(loading_cell.source, namespace)
    registered = get_session()
    assert namespace["session"] is registered

    # papermill puts its parameters cell after those two
    exec(
        PythonTranslator.codify(
            {"session": "mine", "Session": 3, "AuthMode": None}, "Parameters"
        ),
        namespace,
    )
    # the parameter wins in the notebook's namespace, silently; composapy itself uses the registered session
    assert namespace["session"] == "mine" and namespace["Session"] == 3
    assert namespace["AuthMode"] is None
    assert get_session() is registered


# ----------------------------------------------------------------------------------------------
# execute_notebook and the __main__ path, with papermill stubbed so that nothing is executed
# ----------------------------------------------------------------------------------------------

KEY_VALUE_PAIR = "KeyValuePairOfstringanyType:#System.Collections.Generic"
BOM = b"\xef\xbb\xbf"


def parameters_bytes(values, bom=True):
    """The parameters file as the server writes it: a list of key-value entries, UTF-8, usually with a byte order mark."""
    entries = (
        [{"__type": KEY_VALUE_PAIR, "key": k, "value": v} for k, v in values.items()]
        if isinstance(values, dict)
        else values
    )
    return (BOM if bom else b"") + json.dumps(entries, ensure_ascii=False).encode(
        "utf-8"
    )


class FakePapermill:
    """Records what papermill would be given to run, including the notebook as it is on disk at that moment."""

    def __init__(self):
        self.calls = []
        self.result = SimpleNamespace(name="the executed notebook")

    def __call__(self, input_path, output_path, **kwargs):
        self.calls.append(
            SimpleNamespace(
                input=Path(input_path),
                output=Path(output_path),
                kwargs=kwargs,
                nb=nbformat.read(str(input_path), as_version=4),
            )
        )
        return self.result


@pytest.fixture
def papermill(monkeypatch):
    fake = FakePapermill()
    monkeypatch.setattr(nb_wrap.pm, "execute_notebook", fake)
    return fake


@pytest.fixture
def run(tmp_path):
    """An input notebook, and a run folder two levels below app/, which is where the notebook is to run."""
    app = tmp_path / "app"
    run_dir = app / "runs" / "r1"
    run_dir.mkdir(parents=True)
    notebook_path = tmp_path / "input.ipynb"
    nbformat.write(notebook("print('hi')"), str(notebook_path))
    params = run_dir / "params.serialized"
    params.write_bytes(parameters_bytes({"n": 3}))
    return SimpleNamespace(app=app, dir=run_dir, notebook=notebook_path, params=params)


def execute(run, token=None):
    return nb_wrap.execute_notebook(str(run.notebook), str(run.params), token)


def test_papermill_is_given_the_temp_notebook_a_result_path_and_the_working_directory(
    run, papermill
):
    execute(run)
    (call,) = papermill.calls
    assert call.input == run.dir / "temp.ipynb"
    assert call.output == run.dir / "result.ipynb"
    # the notebook runs in the folder two levels above the run folder, not in the run folder
    assert Path(call.kwargs["cwd"]) == run.app
    assert call.kwargs["parameters"] == {"n": 3}
    assert set(call.kwargs) == {"parameters", "cwd"}


def test_what_papermill_returns_is_returned(run, papermill):
    assert execute(run) is papermill.result


def test_the_serialization_cell_writes_outputs_serialized_beside_the_parameters_file(
    run, papermill
):
    execute(run)
    last = papermill.calls[0].nb.cells[-1].source
    assert "inject.serialize_return_values" in last
    literal = ast.parse(last).body[-1].value.args[2]
    assert ast.literal_eval(literal) == (run.dir / "outputs.serialized").as_posix()
    assert not (
        run.dir / "outputs.serialized"
    ).exists()  # papermill's job, not the wrapper's


def test_the_temp_notebook_stays_in_the_run_folder_and_the_input_is_not_changed(
    run, papermill
):
    before = run.notebook.read_bytes()
    execute(run)
    assert run.notebook.read_bytes() == before
    temp = nbformat.read(str(run.dir / "temp.ipynb"), as_version=4)
    # the package loading cell, the empty parameters cell, the notebook's own cell, and the serialization cell
    assert [cell.source for cell in temp.cells][1:-1] == ["", "print('hi')"]
    assert not (run.dir / "result.ipynb").exists()  # the stub did not write one


def test_the_temp_notebook_is_written_as_utf8(run, papermill):
    nbformat.write(notebook("print('café 中文')"), str(run.notebook))
    execute(run)
    raw = (run.dir / "temp.ipynb").read_bytes()
    assert "café 中文".encode("utf-8") in raw


@pytest.mark.parametrize("bom", [True, False])
def test_the_parameters_file_is_read_with_or_without_a_byte_order_mark(
    run, papermill, bom
):
    run.params.write_bytes(parameters_bytes({"n": 3, "s": "text"}, bom=bom))
    execute(run)
    assert papermill.calls[0].kwargs["parameters"] == {"n": 3, "s": "text"}


def test_the_parameters_keep_their_contract_types(run, papermill):
    run.params.write_bytes(
        parameters_bytes(
            {
                "tbl": TABLE_JSON,
                "ref": FILE_JSON,
                "_execution_handle": HANDLE_JSON,
            }
        )
    )
    execute(run)
    parameters = papermill.calls[0].kwargs["parameters"]
    assert [type(v).__name__ for v in parameters.values()] == [
        "Table",
        "FileReference",
        "ExecutionHandle",
    ]
    assert list(parameters) == ["tbl", "ref", "_execution_handle"]


def test_a_key_given_twice_keeps_its_last_value_and_no_entries_is_no_parameters(
    run, papermill
):
    run.params.write_bytes(parameters_bytes({}))
    run.params.write_bytes(
        parameters_bytes(
            [
                {"__type": KEY_VALUE_PAIR, "key": "n", "value": 1},
                {"__type": KEY_VALUE_PAIR, "key": "n", "value": 2},
            ]
        )
    )
    execute(run)
    run.params.write_bytes(parameters_bytes([]))
    execute(run)
    assert [c.kwargs["parameters"] for c in papermill.calls] == [{"n": 2}, {}]


def test_a_null_parameter_value_is_passed_on_as_none(run, papermill):
    run.params.write_bytes(parameters_bytes({"x": None}))
    execute(run)
    assert papermill.calls[0].kwargs["parameters"] == {"x": None}


def test_with_a_token_the_session_cell_is_first(run, papermill):
    execute(run, token="token-for-tests")
    first = papermill.calls[0].nb.cells[0].source
    assert "Session(" in first and "token-for-tests" in first


@pytest.mark.parametrize("token", [None, ""])
def test_without_a_token_no_session_cell_is_made(run, papermill, token):
    execute(run, token=token)
    assert not any("Session" in c.source for c in papermill.calls[0].nb.cells)


def test_a_missing_parameters_file_stops_before_anything_is_written(run, papermill):
    run.params.unlink()
    with pytest.raises(FileNotFoundError):
        execute(run)
    assert papermill.calls == [] and not (run.dir / "temp.ipynb").exists()


def test_a_missing_notebook_stops_before_anything_is_written(run, papermill):
    run.notebook.unlink()
    with pytest.raises(FileNotFoundError):
        execute(run)
    assert papermill.calls == [] and not (run.dir / "temp.ipynb").exists()


def test_a_parameters_file_that_is_not_json_stops_before_anything_is_written(
    run, papermill
):
    run.params.write_bytes(b"not json")
    with pytest.raises(ValueError):
        execute(run)
    assert papermill.calls == [] and not (run.dir / "temp.ipynb").exists()


@pytest.mark.parametrize("folder", ["with space", "café", "日本"])
def test_a_run_folder_whose_name_is_not_plain_still_gives_a_valid_serialization_cell(
    tmp_path, papermill, folder
):
    run_dir = tmp_path / folder / "runs" / "r1"
    run_dir.mkdir(parents=True)
    notebook_path = tmp_path / "input.ipynb"
    nbformat.write(notebook("x = 1"), str(notebook_path))
    params = run_dir / "params.serialized"
    params.write_bytes(parameters_bytes({}))
    nb_wrap.execute_notebook(str(notebook_path), str(params), None)
    (call,) = papermill.calls
    literal = ast.parse(call.nb.cells[-1].source).body[-1].value.args[2]
    assert ast.literal_eval(literal) == (run_dir / "outputs.serialized").as_posix()


def test_a_quote_in_the_run_folders_path_does_not_break_the_serialization_cell():
    nb = notebook("x = 1")
    nb_wrap._inject_return_values_serialization(
        nb, Path("/work/O'Brien/runs/r1/outputs.serialized")
    )
    tree = ast.parse(nb.cells[-1].source)  # SyntaxError: unterminated string literal
    literal = tree.body[-1].value.args[2]
    assert ast.literal_eval(literal) == "/work/O'Brien/runs/r1/outputs.serialized"


def test_a_parameter_with_a_character_that_cp1252_cannot_read_does_not_stop_the_run(
    run, papermill, monkeypatch
):
    # "Ý" is C3 9D in UTF-8, and 0x9D is one of the five bytes cp1252 leaves undefined. open() without an encoding on a
    # Windows machine with that code page is simulated, so the test does not depend on this machine's locale.
    real_open = builtins.open

    def open_as_on_windows(file, mode="r", *args, **kwargs):
        if "b" not in mode and kwargs.get("encoding") is None:
            kwargs["encoding"] = "cp1252"
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(nb_wrap, "open", open_as_on_windows, raising=False)
    run.params.write_bytes(parameters_bytes({"name": "Ý"}))
    execute(run)
    assert papermill.calls[0].kwargs["parameters"] == {"name": "Ý"}


def run_main(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["nb_wrap.py", *args])
    return runpy.run_path(nb_wrap.__file__, run_name="__main__")


def test_run_as_a_script_it_takes_the_notebook_the_parameters_file_and_a_token(
    run, papermill, monkeypatch
):
    run_main(monkeypatch, str(run.notebook), str(run.params), "token-for-tests")
    (call,) = papermill.calls
    assert call.input == run.dir / "temp.ipynb" and call.kwargs["parameters"] == {
        "n": 3
    }
    assert "token-for-tests" in call.nb.cells[0].source


def test_run_as_a_script_without_a_token_makes_no_session_cell(
    run, papermill, monkeypatch
):
    run_main(monkeypatch, str(run.notebook), str(run.params))
    assert not any("Session" in c.source for c in papermill.calls[0].nb.cells)


def test_run_as_a_script_ignores_arguments_after_the_token(run, papermill, monkeypatch):
    run_main(monkeypatch, str(run.notebook), str(run.params), "tok", "extra", "more")
    assert "tok" in papermill.calls[0].nb.cells[0].source


@pytest.mark.parametrize("arguments", [[], ["only-a-notebook.ipynb"]])
def test_pinned_run_as_a_script_with_too_few_arguments_is_an_index_error_without_a_usage_message(
    papermill, monkeypatch, arguments
):
    # Pinned, needs a decision: the caller sees "list index out of range", not what the arguments should be
    with pytest.raises(IndexError):
        run_main(monkeypatch, *arguments)
    assert papermill.calls == []


def test_importing_the_module_runs_nothing(papermill):
    runpy.run_path(nb_wrap.__file__, run_name="not_main")
    assert papermill.calls == []
