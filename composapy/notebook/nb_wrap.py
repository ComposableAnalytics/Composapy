import sys
import papermill as pm
import nbformat
from pathlib import Path

import composapy.notebook.translators
from composapy._wire import codec
from composapy.notebook.nbr_globals import RETURN_VALUES_KEYWORD, EXECUTION_HANDLE_VAR


def execute_notebook(
    input_nb_path: str, serialized_params_path: str, token: str
) -> nbformat.NotebookNode:
    run_directory = Path(serialized_params_path).parent
    serialized_return_values_path = Path(run_directory, "outputs.serialized")
    temp_nb_path = Path(run_directory, "temp.ipynb")
    result_nb_path = Path(run_directory, "result.ipynb")

    with open(serialized_params_path, "r", encoding="utf-8-sig") as _file:
        entries = codec.decode(_file.read())

    parameters = {entry.key: entry.value for entry in entries}

    _nb = nbformat.read(input_nb_path, as_version=4)
    _inject_notebook(_nb, serialized_return_values_path, token)

    # write temporary file to execute notebook
    with open(temp_nb_path, "w", encoding="utf-8") as _file:
        nbformat.write(_nb, _file)

    # used as current working directory when running notebook
    root_notebook_working_dir = run_directory.parent.parent

    notebook = pm.execute_notebook(
        temp_nb_path,
        result_nb_path,
        parameters=parameters,
        cwd=root_notebook_working_dir,
    )
    return notebook


def _inject_notebook(
    nb: nbformat.NotebookNode, serialized_return_values_path: Path, token: str
) -> None:
    _inject_missing_parameters_cell(nb)
    _inject_package_loading(nb)
    _inject_return_values_serialization(nb, serialized_return_values_path)
    if token:
        _inject_implicit_auth(nb, token)


def _inject_missing_parameters_cell(nb):
    for cell in nb.cells:
        # if cell with parameters tag already exists, no need to add new cell
        if cell.metadata.get("tags") and "parameters" in cell.metadata.tags:
            return

    params_cell = nbformat.v4.new_code_cell(source="")
    params_cell.metadata["tags"] = ["parameters"]
    nb.cells.insert(0, params_cell)


def _inject_package_loading(nb: nbformat.NotebookNode):
    code = f"""\
import composapy
from composapy.contracts import ContractSerializer, FileReference, ExecutionHandle, Table
{RETURN_VALUES_KEYWORD} = {{}}
"""

    new_cell = nbformat.v4.new_code_cell(source=code)
    nb.cells.insert(0, new_cell)


def _inject_return_values_serialization(
    nb: nbformat.NotebookNode, serialized_return_values_path: Path
) -> None:
    code = f"""\
from composapy.notebook import inject
inject.serialize_return_values(
    {EXECUTION_HANDLE_VAR},
    {RETURN_VALUES_KEYWORD},
    {serialized_return_values_path.as_posix()!r}
)
"""

    new_cell = nbformat.v4.new_code_cell(source=code)
    nb.cells.append(new_cell)


def _inject_implicit_auth(nb: nbformat.NotebookNode, token: str):
    code = f"""\
from composapy.session import Session 
from composapy.auth import AuthMode 
session = Session(auth_mode=AuthMode.TOKEN, credentials={token!r}) 
session.register() 
"""

    new_cell = nbformat.v4.new_code_cell(source=code)
    nb.cells.insert(0, new_cell)


if __name__ == "__main__":
    args = sys.argv
    input_nb_path = args[1]
    serialized_params_path = args[2]
    token = args[3] if len(args) > 3 else None

    execute_notebook(input_nb_path, serialized_params_path, token)
