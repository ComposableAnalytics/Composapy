import pandas as pd
from pathlib import Path

from composapy._wire import codec
from composapy.contracts.table import Table
from composapy.contracts.execution_handle import ExecutionHandle
from composapy.contracts.file_reference import (
    FileReference,
    CsvFileReference,
    ImageReference,
)
from composapy.dataflow.io import upload_files_to_runs_dir
from composapy.patch.table import to_table
from composapy._wire.objects import ContractObject


class TypeNotSupportedError(Exception):
    pass


KEY_VALUE_PAIR_TYPE = "KeyValuePairOfstringanyType:#System.Collections.Generic"

SUPPORTED_TYPES = (
    str,
    int,
    bool,
    FileReference,
    CsvFileReference,
    ImageReference,
    Table,
    pd.DataFrame,
    float,
)


def _plain(value, execution_handle):
    return value


def _float(value, execution_handle):
    # .NET wrote an integral double without ".0" (3.0 as 3), which the C# side reads as an Int32.
    return int(value) if value.is_integer() and abs(value) < 1e16 else value


def is_file_ref(file_ref: FileReference, execution_handle: ExecutionHandle):
    if file_ref.LocalFile:
        return upload_files_to_runs_dir(execution_handle, file_ref.LocalFile)
    return file_ref


def is_table(table, *args):
    return table


marshall_actions = {
    None: _plain,
    str: _plain,
    int: _plain,
    bool: _plain,
    float: _float,
    FileReference: is_file_ref,
    CsvFileReference: is_file_ref,
    ImageReference: is_file_ref,
    Table: is_table,
    pd.DataFrame: lambda x, y: to_table(x, y),
}


def serialize_return_values(execution_handle, return_values, output_path):
    for value in return_values.values():
        if value is not None and type(value) not in SUPPORTED_TYPES:
            raise TypeNotSupportedError(f"'{type(value)}' is not currently supported.")

    entries = []
    for key, value in return_values.items():
        marshalled = marshall_actions[None if value is None else type(value)](
            value, execution_handle
        )
        entries.append(
            ContractObject(
                [("__type", KEY_VALUE_PAIR_TYPE), ("key", key), ("value", marshalled)]
            )
        )
    Path(output_path).write_text(codec.encode(entries, compact=True), encoding="utf-8")
