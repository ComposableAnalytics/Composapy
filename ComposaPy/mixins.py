import System
import pandas as pd


class ObjectSetMixin:
    """Used for object model sets which require element navigation tree utilities.
    """

    _target = None

    def __len__(self):
        return len(self._target)

    def __getitem__(self, index):
        return self._target[index]

    def __iter__(self):
        return iter(self._target)

    def first(self):
        """Returns first module in self._target.
        """
        return next(iter(self._target))

    def first_with_name(self, name):
        """Matches by first in self._target with given name.
        """
        return next(item for item in self._target if item.name == name)


class PandasMixin:
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
    session = None

    def convert_table_to_df(self, table):
        table_results = self.session._services["TableService"].GetResultFromTable(
            table, 0, 0x7FFFFFFF
        )
        headers = table_results.Headers
        results = table_results.Results
        df = pd.DataFrame(results)
        df.columns = headers

        dtypes_dict = self._make_pandas_dtypes_dict(table.Columns)
        for key in dtypes_dict.keys():
            if dtypes_dict[key] == "float64":
                df[key] = df[key].apply(lambda x: System.Decimal.ToDouble(x))

        return df.astype(dtypes_dict)

    def _make_pandas_dtypes_dict(self, table_columns):
        dtypes_dict = dict()
        for key in table_columns.Dictionary.Keys:
            column = table_columns.Dictionary[key]
            dtypes_dict[column.Name] = self.MAP_STRING_TYPES_TO_PANDAS_TYPES[
                column.Type
            ]
        return dtypes_dict

    def _make_pandas_dtypes_from_list_of_column_defs(self, list_of_column_defs):
        dtypes_dict = dict()
        for column_def in list_of_column_defs:
            dtypes_dict[column_def.Name] = self.MAP_CS_TYPES_TO_PANDAS_TYPES[
                column_def.Type
            ]
        return dtypes_dict
