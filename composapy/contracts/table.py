from composapy._wire import codec
from composapy._wire.objects import ContractObject, KeyedList, register
from composapy.decorators import session_required
from composapy.session import get_session
from composapy.exceptions import ServiceFault
import composapy.interactive.options as iopts

from typing import Dict
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype as is_datetime
import re
from datetime import datetime, timedelta
import numpy as np
import json

TYPE = "Table:#CompAnalytics.Contracts.Tables"
COLUMN_TYPE = "TableColumn:#CompAnalytics.Contracts.Tables"

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

_COLUMN_TYPES = {
    np.int8: "INT",
    np.uint8: "INT",
    np.int16: "INT",
    np.uint16: "INT",
    np.int32: "INTEGER",
    np.uint32: "INTEGER",
    np.int64: "BIGINT",
    np.uint64: "UNSIGNED BIG INT",
    np.float16: "FLOAT",
    np.float32: "FLOAT",
    np.float64: "DOUBLE",
    np.bool_: "BOOLEAN",
    str: "VARCHAR",
    np.str_: "VARCHAR",
    np.object_: "VARCHAR",
    np.datetime64: "DATETIMEOFFSET",
    np.timedelta64: "DURATION",
}


class Table(ContractObject):

    def __init__(self, *args, **members):
        if len(args) == 1 and isinstance(args[0], str):
            super().__init__(
                codec.decode(args[0])
            )  # an old pickle hands us the JSON text
        else:
            super().__init__(
                *args, **members
            )  # the decoder hands us pairs; code hands us keywords

        if isinstance(self.get("Columns"), list):
            self["Columns"] = TableColumnCollection(self["Columns"])

    def __deepcopy__(self, memo):
        return self

    def __reduce__(self):
        return (self.__class__, (codec.encode(self),))

    @session_required
    def to_pandas(self):
        try:
            table_results = get_session().table_service.GetResultFromTable(
                self, 0, 0x7FFFFFFF
            )
        except ServiceFault as e:
            if "String was not recognized as a valid DateTime" in str(e):
                # helpful error message
                raise ValueError(
                    "Error converting table to pandas DataFrame: "
                    "One or more columns contain invalid datetime values. "
                    "Please ensure all datetime columns are in a valid format. Please preprocess to an appropriate datetime format."
                )
            else:
                raise
        headers = table_results.Headers
        results = table_results.Results
        df = pd.DataFrame(results, columns=headers)

        dtypes_dict = _make_pandas_dtypes_dict(self.Columns)
        integer_keys = [
            key for key, dtype in dtypes_dict.items() if dtype in ("Int64", "UInt64")
        ]
        if integer_keys:
            # pandas turns a column with a null beside integers into float64
            raw = pd.DataFrame(results, columns=headers, dtype=object)
            for key in integer_keys:
                df[key] = raw[key]
        for key in dtypes_dict.keys():
            if dtypes_dict[key] == "float64":
                df[key] = pd.to_numeric(df[key])
            elif is_datetime(dtypes_dict[key]):
                df[key] = df[key].apply(parse_datetime_string)

                # A column with no rows has no datetime dtype yet, so there is no .dt to ask
                if not df[key].empty and df[key].dt.tz is not None:
                    df[key] = df[key].dt.tz_localize(
                        None
                    )  # Drop timezone information as dtype is tz-naive

        return df.astype(dtypes_dict)

    def _repr_html_(self):
        """Used to display table contracts as pandas dataframes or interactive DataTables inside of notebooks."""
        if iopts.SHOW_INTERACTIVE_TABLES:
            from composapy.interactive.itable import (
                ITableResult,
                IDataSource,
            )  # imported here, as itable imports session and decorators

            cols = [c.Name for c in self.Columns]
            return ITableResult(cols, IDataSource.TABLE, self)._repr_html_()
        return self.to_pandas()._repr_html_()


def _to_utc(timestamp):
    """Text with an offset (a DATETIMEOFFSET value, or ISO text with Z or +hh:mm) names an instant: convert it to UTC.
    Text without one is taken to be UTC already. to_pandas then makes the column naive, so its values are UTC.
    """
    if timestamp.tz is not None:
        return timestamp.tz_convert("UTC")
    return timestamp.tz_localize("UTC")


def parse_datetime_string(x):
    if x is None or (
        not isinstance(x, (list, tuple, dict, set, np.ndarray)) and pd.isna(x)
    ):
        return pd.NaT

    if isinstance(x, datetime):
        # A DateTime (not a DateTimeOffset) arrives with an offset the server added, which is not part of the value:
        # its wall-clock time is the value, so the offset is added back to the instant
        ts = pd.Timestamp(x)
        if ts.tzinfo is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC") + (x.utcoffset() or timedelta(0))

    if isinstance(x, (int, float)):
        try:
            parsed_datetime = pd.to_datetime(
                x, unit="s", utc=True
            )  # Interpreted as unix time; by default UTC
            return parsed_datetime
        except Exception as e:
            return pd.NaT

    if isinstance(x, str):
        match = re.match(r"DateTime\((\d+)\)", x)
        if match:
            unixtime = int(match.group(1))
            dt = pd.to_datetime(
                unixtime, unit="s", utc=True
            )  # Interpreted as unix time; by default UTC
            return dt

        # Parse '/Date(<milliseconds><timezone>)/' format
        # handled in codec

        # Trying some common date formats
        date_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
            "%d-%b-%Y",
            "%d-%b-%Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",  # ISO 8601 UTC
            "%Y-%m-%dT%H:%M:%S%z",  # ISO 8601 with timezone
            "%a, %d %b %Y %H:%M:%S %Z",  # RFC 1123
        ]
        for fmt in date_formats:
            try:
                parsed_datetime = pd.to_datetime(x, format=fmt)
                if pd.isna(
                    parsed_datetime
                ):  # pandas 1.x answers NaT for "", "NaT" and "nan"
                    return pd.NaT
                return _to_utc(parsed_datetime)
            except ValueError:
                continue
        try:
            parsed_datetime = pd.to_datetime(x)
            if pd.isna(parsed_datetime):
                return pd.NaT
            return _to_utc(parsed_datetime)
        except Exception as e:
            print(
                f"Error parsing datetime: {e}. Please ensure datetime is in an appropriate format. Note that it will incorrectly parse if day and month are both numerical and day preceeds month."
            )
            return pd.NaT
    else:
        print(f"Unsupported type: {type(x)}")
        return pd.NaT


def _make_pandas_dtypes_dict(table_columns) -> Dict[any, str]:
    dtypes_dict = dict()
    for column in table_columns:
        dtypes_dict[column.Name] = MAP_STRING_TYPES_TO_PANDAS_TYPES.get(
            column.Type, "object"
        )
    return dtypes_dict


def _make_pandas_dtypes_from_list_of_column_defs(list_of_column_defs) -> Dict:
    dtypes_dict = dict()
    for column_def in list_of_column_defs:
        dtypes_dict[column_def.Name] = MAP_CS_TYPES_TO_PANDAS_TYPES[column_def.Type]
    return dtypes_dict


def _has_default_range_index(df):
    """Checks if df has a default row index (i.e., a RangeIndex over the inclusive interval [0, len(df) - 1])"""
    index_vals_are_default_seq = np.all(np.arange(0, len(df)) == df.index)
    is_range_index = type(df.index) == pd.RangeIndex
    return index_vals_are_default_seq and is_range_index


def _column_type(dtype) -> str:
    try:
        return _COLUMN_TYPES[dtype.type]
    except KeyError:
        raise NotImplementedError(
            f"Dataframes with column type {dtype.type} are not supported yet in the table conversion."
        ) from None


def _put_back_infinities(df, rows):
    # to_json writes an infinity as null, which would lose the value; set each one back into the rows as a float
    for position, dtype in enumerate(df.dtypes):
        if not issubclass(dtype.type, np.floating):
            continue
        values = df.iloc[:, position].to_numpy(dtype="float64", na_value=np.nan)
        for row in np.flatnonzero(np.isinf(values)):
            rows[row][position] = float(values[row])


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
        column_names = ["_".join(str(name) for name in names) for names in df.columns]
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
    column_types = [_column_type(t) for t in df.dtypes]
    clean_column_names = sanitize_all(column_names)
    columns = TableColumnCollection()
    for i in range(0, len(column_names)):
        columns.Add(
            TableColumn(
                clean_column_names[column_names[i]],
                column_types[i],
            )
        )

    rows = json.loads(df.to_json(orient="values", date_format="iso"))
    _put_back_infinities(df, rows)

    df_json_obj = {
        "ExecutionHandle": execution_handle,
        "Columns": columns,
        "Rows": rows,
    }

    # Need to include the external input module handles in the stream when converting a df for an external table input
    if external_input_handles:
        df_json_obj = {**external_input_handles, **df_json_obj}

    body = codec.encode(df_json_obj)

    return get_session().table_service.CreateTable(body)


class TablePickleBehavior(Table):
    pass


class TableColumn(ContractObject):
    def __init__(self, *args, **members):
        if len(args) == 2 and all(
            isinstance(a, str) for a in args
        ):  # TableColumn("a", "INTEGER")
            super().__init__(
                [("__type", COLUMN_TYPE), ("Name", args[0]), ("Type", args[1])]
            )
        else:
            super().__init__(*args, **members)


class TableColumnCollection(KeyedList):
    def __getitem__(self, key):
        if isinstance(key, str):
            for column in self:
                if column.Name.lower() == key.lower():
                    return column
            raise KeyError(key)
        return list.__getitem__(self, key)


class ColumnNameSanitizer:
    """Port of CompAnalytics.Utils.ColumnNameSanitizer."""

    def __init__(self, duplicate_format="{0}_{1}", duplicate_start_index=2):
        self._seen = {}  # lowercased name -> duplicates handed out so far
        self._format = duplicate_format
        self._start = duplicate_start_index - 1

    def sanitize_name(self, index, name):
        if name is None or not str(name).strip():
            name = f"col{index}"
        name = re.sub(r"\s+", " ", name).strip()  # runs of whitespace become one space
        key = name.lower()
        if key in self._seen:  # a duplicate, ignoring case
            count = self._seen[key]
            while True:  # loop until the new name is unused
                count += 1
                candidate = self._format.format(name, count)
                if candidate.lower() not in self._seen:
                    break
            self._seen[key] = count
            self._seen[candidate.lower()] = (
                self._start
            )  # in case a later real column is called that
            return candidate
        self._seen[key] = self._start
        return name


def sanitize_all(names, duplicate_format="{0}_{1}"):
    """Maps each original name to its sanitized name, like the C# SanitizeAll."""
    sanitizer = ColumnNameSanitizer(duplicate_format)
    return {name: sanitizer.sanitize_name(i, name) for i, name in enumerate(names)}


register(TYPE, Table)
register(COLUMN_TYPE, TableColumn)
