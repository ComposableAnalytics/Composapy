from typing import Dict
import pandas as pd

import System
from CompAnalytics.Contracts.Tables import Table

from composapy.session import get_session

MAP_CS_TYPES_TO_PANDAS_TYPES = {
    "System.String": "object",
    "System.Int64": "Int64",
    "System.Int32": "Int64",
    "System.Int16": "Int64",
    "System.Double": "float64",
    "System.Decimal": "float64",
    "System.Single": "float64",
    "System.Boolean": "bool",
    "System.Guid": "object",
}
MAP_STRING_TYPES_TO_PANDAS_TYPES = {
    "CHAR": "object",
    "INTEGER": "int64",
    "INT": "int64",
    "BIGINT": "int64",
    "INT64": "int64",
    "UNSIGNED BIG INT": "int64",
    "VARCHAR": "object",
    "STRING": "object",
    "TEXT": "object",
    "FLOAT": "float64",
    "DOUBLE": "float64",
    "REAL": "float64",
    "BOOLEAN": "bool",
    "DATETIME": "datetime64",
    "DATETIMEOFFSET": "datetime64",
    "BLOB": "object",
    "OBJECT": "object",
    "GUID": "object",
}


def _table_to_pandas(self) -> pd.DataFrame:
    """Converts a composapy table contract to a pandas dataframe."""
    session = get_session()

    table_results = session.table_service.GetResultFromTable(self, 0, 0x7FFFFFFF)
    headers = table_results.Headers
    results = table_results.Results
    df = pd.DataFrame(results, columns=headers)

    dtypes_dict = _make_pandas_dtypes_dict(self.Columns)
    for key in dtypes_dict.keys():
        if dtypes_dict[key] == "float64":
            df[key] = df[key].apply(lambda x: System.Decimal.ToDouble(x))

    return df.astype(dtypes_dict)


def _repr_html_(self):
    """Used to display table contracts as pandas dataframes inside of notebooks."""
    return self.to_pandas()._repr_html_()


def _make_pandas_dtypes_dict(table_columns) -> Dict[any, str]:
    dtypes_dict = dict()
    for key in table_columns.Dictionary.Keys:
        column = table_columns.Dictionary[key]
        dtypes_dict[column.Name] = MAP_STRING_TYPES_TO_PANDAS_TYPES[column.Type]
    return dtypes_dict


def _make_pandas_dtypes_from_list_of_column_defs(list_of_column_defs) -> Dict:
    dtypes_dict = dict()
    for column_def in list_of_column_defs:
        dtypes_dict[column_def.Name] = MAP_CS_TYPES_TO_PANDAS_TYPES[column_def.Type]
    return dtypes_dict


Table.to_pandas = _table_to_pandas
Table._repr_html_ = _repr_html_
