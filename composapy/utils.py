from __future__ import annotations
import os
from pathlib import Path

from System import Uri
from CompAnalytics.Contracts import FileReference


def _urljoin(*args):
    """
    Joins given arguments into an url. Trailing but not leading slashes are
    stripped for each argument.
    """

    return "/".join(map(lambda x: str(x).rstrip("/"), args))


def _remove_suffix(input_string, suffix):
    """From the python docs, earlier versions of python does not have this."""
    if suffix and input_string.endswith(suffix):
        return input_string[: -len(suffix)]
    return input_string


def file_ref(path: str | Path) -> FileReference:
    """Returns a CompAnalytics.Contracts.FileReference object, which can then be passed
    as the external input of a DataFlow.

        .. highlight:: python
        .. code-block:: python

            from composapy import file_ref
            from composapy.dataflow.api import DataFlow
            _ref = file_ref("path/to/file.txt")
            dataflow_run = DataFlow.run(123456, external_inputs={"foo_ref": _ref})

    :param path: location of the file to make a file reference for

    :return: the FileReference contract
    """
    if isinstance(path, str):
        path = Path(path)

    uri = Uri(str(Path(path).absolute()))
    file_ref = FileReference.CreateWithAbsoluteUri(uri.LocalPath, uri)
    return file_ref


def get_config_path() -> Path:
    """If environment variable COMPOSAPY_INI_DIR exists, use that path. Otherwise,
    assume composapy.ini resides in the current working directory."""
    composapy_ini_dir = os.getenv("COMPOSAPY_INI_DIR", None)
    if composapy_ini_dir:
        return Path(composapy_ini_dir, "composapy.ini")
    return Path("composapy.ini")
