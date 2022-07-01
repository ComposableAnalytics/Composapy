import sys
import papermill as pm
import nbformat
from pathlib import Path

from composapy import FileReferencePickleBehavior

from System import Object
from CompAnalytics.Core import ContractSerializer
from CompAnalytics.Contracts import FileReference
from System.Collections.Generic import List, KeyValuePair


RETURN_VALUES_KEYWORD = "return_values"


def execute_notebook(
    input_nb_path: str, serialized_params_path: str
) -> nbformat.NotebookNode:

    run_directory = Path(serialized_params_path).parent
    serialized_return_values_path = Path(run_directory, "outputs.serialized")
    temp_nb_path = Path(run_directory, "temp.ipynb")
    result_nb_path = Path(run_directory, "result.ipynb")

    with open(serialized_params_path, "r") as _file:
        serialized_json = _file.read()

    deserialized_list = ContractSerializer.Deserialize(
        serialized_json, List[KeyValuePair[str, Object]]
    )

    parameters = {}
    for parameter in deserialized_list:
        if isinstance(parameter.Value, FileReference):  #  update pickling behavior
            parameter.Value.__class__ = FileReferencePickleBehavior
        parameters[parameter.Key] = parameter.Value

    _nb = nbformat.read(input_nb_path, as_version=4)
    _inject_notebook(_nb, serialized_return_values_path)

    # write temporary file to execute notebook
    with open(temp_nb_path, "w") as _file:
        nbformat.write(_nb, _file)

    notebook = pm.execute_notebook(
        temp_nb_path,
        result_nb_path,
        parameters=parameters,
        cwd=run_directory,
    )
    return notebook


def _inject_notebook(
    nb: nbformat.NotebookNode, serialized_return_values_path: Path
) -> None:
    _inject_package_loading(nb)
    _inject_return_values_serialization(nb, serialized_return_values_path)


def _inject_package_loading(nb: nbformat.NotebookNode):
    code = f"""\
import composapy
from CompAnalytics.Core import ContractSerializer
from CompAnalytics.Contracts import FileReference
"""

    new_cell = nbformat.v4.new_code_cell(source=code)
    nb.cells.insert(0, new_cell)


def _inject_return_values_serialization(
    nb: nbformat.NotebookNode, serialized_return_values_path: Path
) -> None:
    code = f"""\
from composapy.notebook import inject
inject.serialize_return_values({RETURN_VALUES_KEYWORD}, '{serialized_return_values_path.as_posix()}')
"""

    new_cell = nbformat.v4.new_code_cell(source=code)
    nb.cells.append(new_cell)


if __name__ == "__main__":
    args = sys.argv
    input_nb_path = args[1]
    serialized_params_path = args[2]

    execute_notebook(input_nb_path, serialized_params_path)
