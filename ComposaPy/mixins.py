import System
import pandas as pd


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

    def convert_table_to_pandas(self, table):
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


# table_column_dict = table.Columns.Dictionary
# for key in table.Columns.Dictionary.Keys:
#    column = table_column_dict[key]
#    if column.Type == "DATETIMEOFFSET":
#        dtypes_dict[column.Name] = 'datetime64'
