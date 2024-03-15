import json
import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype as is_datetime
from typing import Dict

from CompAnalytics.Contracts import ExecutionHandle
from CompAnalytics.Contracts.Tables import Table, TableColumn, TableColumnCollection
from CompAnalytics.Core import ContractSerializer
from CompAnalytics.Tables import TableOperations
from CompAnalytics.Utils import ColumnNameSanitizer
import System
from System.Collections.Generic import List

from composapy.decorators import session_required
from composapy.session import get_session


import json_fix  # used to patch json with fake magic method __json__


# patching json package using json-fix
# json-fix : https://pypi.org/project/json-fix/
def _json(self):
    return json.loads(ContractSerializer.Serialize(self))


Table.__json__ = _json
ExecutionHandle.__json__ = _json
TableColumnCollection.__json__ = _json


# patching copy.deepycopy
# python docs : https://docs.python.org/3/library/copy.html#copy.deepcopy
def deep_copy(self, memo):
    """Only use for things which don't actually need to be copied."""
    return self


Table.__deepcopy__ = deep_copy


# monkey patching Table for pickling
# python docs : https://docs.python.org/3/library/pickle.html#object.__reduce_ex__
# composable docs : https://dev.composable.ai/api/CompAnalytics.Contracts.Tables.Table.html
def reduce_ex(self, protocol):
    """Called when using pickle.dumps(table_to_pickle)."""
    return (self.__class__, (ContractSerializer.Serialize(self),))


Table.__reduce_ex__ = reduce_ex


class TablePickleBehavior(Table):
    """This is used for changing the behavior of pickling/depickling for Table."""

    def __new__(self, *args, **kwargs):
        """Called when using pickle.loads(picked_table)."""
        return ContractSerializer.Deserialize[Table](args[0])


# Used for QueryView result to Pandas Dataframe conversion
MAP_CS_TYPES_TO_PANDAS_TYPES = {
    "System.String": "object",
    "System.Int64": "Int64",  # alias for pd.Int64DType(), a nullable int64
    "System.Int32": "Int32",
    "System.Int16": "Int16",
    "System.Byte": "UInt8",
    "System.Double": "float64",
    "System.Decimal": "float64",
    "System.Single": "float32",
    "System.Boolean": "boolean",
    "System.Guid": "object",
    "System.DateTime": "datetime64[ns]",
    "System.DateTimeOffset": "datetime64[ns]",
}

# Used for Composable table to Pandas Dataframe conversion
MAP_STRING_TYPES_TO_PANDAS_TYPES = {
    "CHAR": "object",
    "INTEGER": "Int64",
    "INT": "Int64",
    "BIGINT": "Int64",
    "INT64": "Int64",
    "UNSIGNED BIG INT": "UInt64",
    "VARCHAR": "object",
    "STRING": "object",
    "TEXT": "object",
    "FLOAT": "float64",
    "DOUBLE": "float64",
    "REAL": "float64",
    "BOOLEAN": "boolean",
    "DATETIME": "datetime64[ns]",
    "DATETIMEOFFSET": "datetime64[ns]",
    "BLOB": "object",
    "OBJECT": "object",
    "GUID": "object",
}


# Used for Pandas Dataframe to Composable table conversion
def _as_csharp_type_str(type_: any) -> str:
    """Maps a Python/numpy/pandas type to its corresponding C# type."""
    if type_ in (np.int8, pd.Int8Dtype):
        return "System.SByte"
    elif type_ in (np.uint8, pd.UInt8Dtype):
        return "System.Byte"
    elif type_ in (np.int16, pd.Int16Dtype):
        return "System.Int16"
    elif type_ in (np.uint16, pd.UInt16Dtype):
        return "System.UInt16"
    elif type_ in (np.int32, pd.Int32Dtype):
        return "System.Int32"
    elif type_ in (np.uint32, pd.UInt32Dtype):
        return "System.UInt32"
    elif type_ in (np.int64, pd.Int64Dtype):
        return "System.Int64"
    elif type_ in (np.uint64, pd.UInt64Dtype):
        return "System.UInt64"
    elif type_ in (np.float16,):
        return "System.Single"
    elif type_ in (np.float32, pd.Float32Dtype):
        return "System.Single"
    elif type_ in (np.float64, pd.Float64Dtype):
        return "System.Double"
    elif type_ in (np.bool_, pd.BooleanDtype):
        return "System.Boolean"
    elif type_ in (np.str_, str, pd.StringDtype):
        return "System.String"
    elif type_ in (np.datetime64,):
        return "System.DateTimeOffset"
    elif type_ in (np.timedelta64,):
        return "System.TimeSpan"
    elif type_ == np.object_:
        return "System.String"
    else:
        raise NotImplementedError(
            f"Dataframes with column type {type_} are not supported yet in the table conversion."
        )


def _has_default_range_index(df):
    """Checks if df has a default row index (i.e., a RangeIndex over the inclusive interval [0, len(df) - 1])"""
    index_vals_are_default_seq = np.all(np.arange(0, len(df)) == df.index)
    is_range_index = type(df.index) == pd.RangeIndex
    return index_vals_are_default_seq and is_range_index


def _init_cs_list(type_, data, f=lambda x: x):
    """
    Creates a C# list of a given type and initializes with data from the given Python iterable,
    applying the given transformation function. If f is unspecified, the identity function is used.
    Note: The output type of the transform function must be of type type_
    """
    cs_list = List[type_]()
    for val in data:
        cs_list.Add(f(val))
    return cs_list


@session_required
def to_table(df, execution_handle, external_input_handles=None):
    """Creates a Composable table for the given pandas dataframe and returns the table contract."""
    if df.empty and df.shape[1] == 0:
        raise ValueError(
            "DataFrame must have at least one column to be converted into a Composable table."
        )

    if not _has_default_range_index(df):
        df = df.reset_index(drop=False)

    # flatten column multi-index labels, if present
    if isinstance(df.columns[0], tuple):
        column_names = ["_".join(names) for names in df.columns]
    else:
        column_names = [str(col) for col in df.columns]

    if len(set(column_names)) != len(column_names):
        dups = set(
            [f"'{name}'" for name in column_names if column_names.count(name) > 1]
        )
        raise ValueError(
            f"Cannot create table from DataFrame with duplicate column name(s): "
            + ", ".join(dups)
        )

    # Sanitize table names and create a TableColumnCollection to avoid passing around parallel lists
    column_cs_types = [_as_csharp_type_str(t.type) for t in df.dtypes]
    clean_column_names = ColumnNameSanitizer.SanitizeAll(
        _init_cs_list(System.String, column_names)
    )
    columns = TableColumnCollection()
    for i in range(0, len(column_names)):
        type_ = System.Type.GetType(column_cs_types[i])
        columns.Add(
            TableColumn(
                clean_column_names[column_names[i]],
                TableOperations.GetColumnType(type_),
            )
        )

    df_json_obj = {
        "ExecutionHandle": execution_handle,
        "Columns": columns,
        "Rows": json.loads(df.to_json(orient="values", date_format="iso")),
    }

    # Need to include the external input module handles in the stream when converting a df for an external table input
    if external_input_handles:
        df_json_obj = {**external_input_handles, **df_json_obj}

    df_json_stream = System.IO.MemoryStream(bytes(json.dumps(df_json_obj), "ascii"))

    return get_session().table_service.CreateTable(df_json_stream)


@session_required
def to_pandas(self) -> pd.DataFrame:
    """Converts a composapy table contract to a pandas dataframe."""
    table_results = get_session().table_service.GetResultFromTable(self, 0, 0x7FFFFFFF)
    headers = table_results.Headers
    results = table_results.Results
    df = pd.DataFrame(results, columns=headers)

    dtypes_dict = _make_pandas_dtypes_dict(self.Columns)
    for key in dtypes_dict.keys():
        if dtypes_dict[key] == "float64":
            df[key] = df[key].apply(lambda x: System.Convert.ToDouble(x))
        elif dtypes_dict[key] == "datetime64[ns]":
            df[key] = pd.to_datetime(df[key], utc=True).dt.tz_localize(None)

    return df.astype(dtypes_dict)


def _repr_html_(self):
    """Used to display table contracts as pandas dataframes inside of notebooks."""
    return self.to_pandas()._repr_html_()


def _make_pandas_dtypes_dict(table_columns) -> Dict[any, str]:
    dtypes_dict = dict()
    for key in table_columns.Dictionary.Keys:
        column = table_columns.Dictionary[key]
        column_dtype = "object"
        if column.Type in MAP_STRING_TYPES_TO_PANDAS_TYPES.keys():
            if (
                column.Type == "DATETIME"
            ):  # TODO: fix bug around DATETIME columns and remove this check
                raise NotImplementedError(
                    "DATETIME columns are not currently supported in the Composable Table-to-Pandas DataFrame conversion. Please use the DATETIMEOFFSET column type with a zero offset instead. DATETIME support will be added in a future version of Composapy."
                )
            column_dtype = MAP_STRING_TYPES_TO_PANDAS_TYPES[column.Type]
        dtypes_dict[column.Name] = column_dtype
    return dtypes_dict


def _make_pandas_dtypes_from_list_of_column_defs(list_of_column_defs) -> Dict:
    dtypes_dict = dict()
    for column_def in list_of_column_defs:
        dtypes_dict[column_def.Name] = MAP_CS_TYPES_TO_PANDAS_TYPES[column_def.Type]
    return dtypes_dict


Table.to_pandas = to_pandas
Table._repr_html_ = _repr_html_
