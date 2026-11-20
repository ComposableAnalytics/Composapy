"""Run a DataFlow that makes a table of each column type, and convert each table to a DataFrame."""

from composapy.dataflow.api import DataFlow

flow = DataFlow.create(file_path=fixture("table_column_dtypes.json"))

CASES = [
    ("Boolean", ["True", "False"]),
    ("Byte", ["0", "255"]),
    ("Unsigned Long", ["0", "9223372036854774784"]),
    ("Short", ["-32768", "32767"]),
    ("Long", ["-9223372036854774784", "9223372036854774784"]),
    ("DatetimeOffset", ["01/17/2022 06:11:30 PM -05:00"]),
    ("Datetime", ["10/01/2021 00:00:00", "10/02/2021 00:00:00"]),
    ("Datetime", ["2021-09-30T23:00:00-0500", "2021-10-01T23:00:00-0500"]),
]

for index, (column_type, data) in enumerate(CASES):

    def convert():
        run = flow.run(
            external_inputs={"ColumnType": column_type, "ColumnData": list_input(data)}
        )
        return run.modules.first_with_name(
            "Column Type Converter"
        ).result.value.to_pandas()

    attempt(f"{index}_{column_type}", convert)
