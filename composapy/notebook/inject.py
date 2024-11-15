import pandas as pd
from typing import Dict

import System
from System import Object
from System.Collections.Generic import List, KeyValuePair
from CompAnalytics.Core import ContractSerializer
from CompAnalytics.Contracts import (
    FileReference,
    CsvFileReference,
    ImageReference,
    ExecutionHandle,
)
from CompAnalytics.Contracts.Tables import Table

from composapy.dataflow.io import upload_files_to_runs_dir
from composapy.patch.table import to_table


class TypeNotSupportedError(Exception):
    pass


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


def is_file_ref(file_ref: FileReference, execution_handle: ExecutionHandle):
    if file_ref.LocalFile:
        return upload_files_to_runs_dir(execution_handle, file_ref.LocalFile)
    return file_ref


def is_table(table, *args):
    return table


marshall_actions = {
    str: lambda x, y: System.String(x),
    int: lambda x, y: System.Int32(x),
    bool: lambda x, y: System.Boolean(x),
    None: lambda x, y: None,
    FileReference: is_file_ref,
    CsvFileReference: is_file_ref,
    ImageReference: is_file_ref,
    Table: is_table,
    pd.DataFrame: lambda x, y: to_table(x, y),
    float: lambda x, y: System.Double(x),
}


def serialize_return_values(
    execution_handle: ExecutionHandle, return_values: Dict[str, any], output_path: str
) -> None:
    clr_return_values = List[KeyValuePair[str, Object]]()
    for n, (k, v) in enumerate(return_values.items()):
        if v is not None and type(v) not in SUPPORTED_TYPES:
            raise TypeNotSupportedError(f"'{type(v)}' is not currently supported.")

        type_value = v if v is None else type(v)
        clr_value = marshall_actions[type_value](v, execution_handle)
        clr_return_values.Add(KeyValuePair[str, Object](k, clr_value))

    ContractSerializer.SerializeToFile(clr_return_values, output_path)
