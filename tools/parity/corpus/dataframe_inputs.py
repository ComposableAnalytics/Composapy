"""Pass pandas DataFrames into a DataFlow's table input, and read the table that comes back as a DataFrame."""

import datetime
import decimal

import numpy as np
import pandas as pd

from composapy.dataflow.api import DataFlow

flow = DataFlow.create(file_path=fixture("external_input_table.json"))


def round_trip(df):
    run = flow.run(external_inputs={"TableInput": df})
    table = run.modules.first().result.value
    return {
        "columns": [(c.Name, c.Type) for c in table.Columns],
        "headers": list(table.Headers),
        "df": table.to_pandas(),
    }


# each case is an expression, built inside its own attempt so that a case pandas cannot build is recorded and the rest run
CASES = {
    "ints": 'pd.DataFrame({"a": [1, 2, 3]})',
    "mixed": 'pd.DataFrame({"i": [1, 2], "f": [1.5, 2.5], "s": ["x", "y"], "b": [True, False]})',
    "nullable": 'pd.DataFrame({"a": pd.array([1, None], dtype="Int64"), "s": ["x", None], "f": [1.0, np.nan], "b": pd.array([True, None], dtype="boolean")})',
    "int_sizes": 'pd.DataFrame({"i8": np.array([1, 2], dtype="int8"), "u8": np.array([1, 2], dtype="uint8"), "i16": np.array([1, 2], dtype="int16"), "i32": np.array([1, 2], dtype="int32"), "i64": np.array([1, 2], dtype="int64"), "u64": np.array([1, 2], dtype="uint64")})',
    "float_sizes": 'pd.DataFrame({"f16": np.array([1.5, 2.5], dtype="float16"), "f32": np.array([1.5, 2.5], dtype="float32"), "f64": np.array([1.5, 2.5], dtype="float64")})',
    "extremes": 'pd.DataFrame({"big": [2 ** 63 - 1, -2 ** 63], "float": [1.797e308, -1.797e308]})',
    "float_special": 'pd.DataFrame({"f": [float("inf"), float("-inf"), float("nan")]})',
    "naive_datetimes": 'pd.DataFrame({"d": pd.to_datetime(["2021-10-01 12:34:56", "2021-10-02 00:00:00"])})',
    "aware_datetimes": 'pd.DataFrame({"d": pd.to_datetime(["2021-10-01 12:34:56", "2021-10-02 00:00:00"]).tz_localize("UTC")})',
    "datetime_with_null": 'pd.DataFrame({"d": pd.to_datetime(["2021-10-01", None])})',
    "timedeltas": 'pd.DataFrame({"t": pd.to_timedelta(["1 days", "2 hours"])})',
    "python_dates": 'pd.DataFrame({"d": [datetime.date(2021, 10, 1), datetime.date(2021, 10, 2)]})',
    "strings_special": 'pd.DataFrame({"s": ["it\'s", \'a"b\', "café", "中文", "", "line\\nbreak", "tab\\tx", "back\\\\slash"]})',
    "long_string": 'pd.DataFrame({"s": ["x" * 5000]})',
    "decimals": 'pd.DataFrame({"d": [decimal.Decimal("1.50"), decimal.Decimal("-2.25")]})',
    "bytes": 'pd.DataFrame({"b": [b"\\x00\\x01", b"\\xff"]})',
    "object_mixed": 'pd.DataFrame({"o": [1, "a", 2.5, None]})',
    "categorical": 'pd.DataFrame({"c": pd.Categorical(["a", "b", "a"])})',
    "column_names_spaces_hyphens": 'pd.DataFrame({"a b": [1], "a-b": [2], "a.b": [3]})',
    "column_names_keywords": 'pd.DataFrame({"select": [1], "from": [2], "table": [3], "order": [4]})',
    "column_names_digits_first": 'pd.DataFrame({"1x": [1], "2": [2]})',
    "column_names_unicode": 'pd.DataFrame({"café": [1], "中文": [2]})',
    "column_names_punctuation": 'pd.DataFrame({"a[b]": [1], "a\'b": [2], \'a"b\': [3], "a%b": [4], "a#b": [5]})',
    "column_names_numbers": "pd.DataFrame({0: [1], 1: [2]})",
    "column_names_long": 'pd.DataFrame({"x" * 300: [1]})',
    "named_index": 'pd.DataFrame({"a": [1, 2]}, index=pd.Index([10, 20], name="key"))',
    "string_index": 'pd.DataFrame({"a": [1, 2]}, index=["x", "y"])',
    "multiindex_columns": 'pd.DataFrame([[1, 2]], columns=pd.MultiIndex.from_tuples([("a", "x"), ("a", "y")]))',
    "one_row": 'pd.DataFrame({"a": [1]})',
    "many_rows": 'pd.DataFrame({"a": range(20000), "b": ["row"] * 20000})',
    "wide": 'pd.DataFrame({f"c{i}": [i] for i in range(200)})',
    "empty_with_columns": 'pd.DataFrame({"a": pd.Series([], dtype="int64")})',
    "all_null_column": 'pd.DataFrame({"a": [None, None]})',
    "duplicate_column_names": 'pd.DataFrame([[1, 2]], columns=["a", "a"])',
    "no_columns": "pd.DataFrame()",
}

for label, expression in CASES.items():
    attempt(label, lambda e=expression: round_trip(eval(e)))

attempt("not_a_dataframe", lambda: flow.run(external_inputs={"TableInput": [1, 2, 3]}))
attempt(
    "series",
    lambda: flow.run(external_inputs={"TableInput": pd.Series([1, 2], name="s")}),
)
