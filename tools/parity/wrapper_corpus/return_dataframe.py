import pandas as pd

return_values = {
    "ints": pd.DataFrame({"a": [1, 2, 3]}),
    "mixed": pd.DataFrame(
        {"i": [1, 2], "f": [1.5, 2.5], "s": ["x", None], "b": [True, False]}
    ),
    "nullable": pd.DataFrame({"n": pd.array([1, None], dtype="Int64")}),
    "datetimes": pd.DataFrame(
        {"d": pd.to_datetime(["2021-10-01 12:34:56", "2021-10-02 00:00:00"])}
    ),
    "table_passed_through": table,
}
