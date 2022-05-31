import sys
import papermill as pm
import nbformat
from pathlib import Path

#  from papermill import utils as pm_utils

from System import Object
from CompAnalytics.Core import ContractSerializer
from System.Collections.Generic import List, KeyValuePair


RETURN_VALUES = "return_values"


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

    parameters = dict()
    for parameter in deserialized_list:
        parameters[parameter.Key] = parameter.Value

    nb = nbformat.read(input_nb_path, as_version=4)

    _inject_notebook(nb, serialized_return_values_path)

    # write temporary file to execute notebook
    with open(temp_nb_path, "w") as _file:
        nbformat.write(nb, _file)

    notebook = pm.execute_notebook(
        temp_nb_path, result_nb_path, parameters=parameters, cwd=run_directory
    )
    return notebook


def _inject_notebook(
    nb: nbformat.NotebookNode, serialized_return_values_path: Path
) -> None:
    _inject_package_loading(nb)
    _inject_return_values_serialization(nb, serialized_return_values_path)


def _inject_package_loading(nb: nbformat.NotebookNode):
    code = "import composapy"

    new_cell = nbformat.v4.new_code_cell(source=code)
    nb.cells.insert(0, new_cell)


# def _inject_file_reference_patching(nb: nbformat.NotebookNode):
#     injected_cell_index = next(
#         (
#             idx
#             for idx, cell in enumerate(nb.cells)
#             if "injected-parameters" in cell.metadata.tags
#         ),
#         None,
#     )
#     if not injected_cell_index:
#         return
#
#     code = f"""\
# import papermill
# papermill.utils.any_tagged_cell
# from CompAnalytics.Contracts import FileRefPickleObject"""
#
#     before = nb.cells[:injected_cell_index]
#     after = nb.cells[injected_cell_index + 1 :]
#     nb.cells = before + [newcell] + after


def _inject_return_values_serialization(
    nb: nbformat.NotebookNode, serialized_return_values_path: Path
) -> None:
    code = f"""\
import System
from System import Object
from System.Collections.Generic import List, KeyValuePair
from CompAnalytics.Core import ContractSerializer
#  from CompAnalytics.Contracts import FileReference

class TypeNotSupportedError(Exception):
    pass

SUPPORTED_TYPES = (
    str,
    int,
#      FileReference,
)

def is_string(python_object):
    return System.String(python_object)

def is_int(python_object):
    return System.Int32(python_object)

def is_none(python_object):
    return None

#  def is_file_ref(python_object):
#      return python_object

#  marshall_actions = {{
#      str: is_string,
#      int: is_int,
#      None: is_none,
#      FileReference: is_file_ref,
#  }}

clr_return_values = List[KeyValuePair[str, Object]]()
for n, (k, v) in enumerate({RETURN_VALUES}.items()):
    if v is not None and type(v) not in SUPPORTED_TYPES:
        raise TypeNotSupportedError(f"{{type(v)}} is not currently supported.")
    
    clr_value = marshall_actions(type(v))
    # clr_value = _marshall_object(v)    
    clr_return_values.Add(KeyValuePair[str, Object](k, clr_value))

ContractSerializer.SerializeToFile(clr_return_values, '{serialized_return_values_path.as_posix()}')"""

    new_cell = nbformat.v4.new_code_cell(source=code)
    nb.cells.append(new_cell)


if __name__ == "__main__":
    args = sys.argv
    input_nb_path = args[1]
    serialized_params_path = args[2]

    execute_notebook(input_nb_path, serialized_params_path)
