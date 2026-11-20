"""Run queries that return each SQL type, with a null in every column, and read the DataFrames."""

from composapy.key.api import Key
from composapy.queryview.api import QueryView

driver = QueryView.driver(Key.get(name=fixtures["key_name"]))
record("driver_repr", repr(driver))
record("driver_timeout", driver.get_driver_timeout())
record("driver_validate_query", driver.validate_query)
record("driver_key_name", driver.key.name)


def typed(sql_type, low, high):
    return f"""
        select cast(r.x as {sql_type}) as x from (
            select {low} as x union all select {high} as x union all select null as x
        ) as r"""


for sql_type, low, high in [
    ("tinyint", 0, 255),
    ("smallint", -32768, 32767),
    ("int", -2147483648, 2147483647),
    ("bigint", -9223372036854775808, 9223372036854775807),
    ("real", -3.402e38, 3.402e38),
    ("float", -1.797e308, 1.797e308),
    ("decimal(10,2)", "-12345.67", "12345.67"),
    ("money", "-1.5", "1.5"),
]:
    attempt(
        f"number.{sql_type}",
        lambda s=sql_type, a=low, b=high: driver.run(typed(s, a, b)),
    )

for sql_type in ("text", "varchar(20)", "nvarchar(20)", "char(5)"):
    attempt(
        f"string.{sql_type}", lambda s=sql_type: driver.run(typed(s, "'yes'", "'no'"))
    )

attempt("bit", lambda: driver.run(typed("bit", "'true'", "'false'")))
attempt(
    "bit_without_null",
    lambda: driver.run("select cast(1 as bit) as x union all select cast(0 as bit)"),
)
for sql_type, low, high in [
    ("datetime", "'2021-10-01 12:34:56'", "'1900-01-01'"),
    ("datetime2", "'2021-10-01 12:34:56.1234567'", "'0001-01-01'"),
    ("smalldatetime", "'2021-10-01 12:34:00'", "'1900-01-01'"),
    ("date", "'2021-10-01'", "'0001-01-01'"),
    ("datetimeoffset", "'2021-10-01 12:34:56 -05:00'", "'2021-10-01 12:34:56 +05:30'"),
    ("time", "'12:34:56'", "'00:00:00'"),
]:
    attempt(
        f"datetime.{sql_type}",
        lambda s=sql_type, a=low, b=high: driver.run(typed(s, a, b)),
    )

attempt(
    "guid",
    lambda: driver.run(
        "select cast('6f9619ff-8b86-d011-b42d-00c04fc964ff' as uniqueidentifier) as x union all select null"
    ),
)
attempt(
    "binary",
    lambda: driver.run(
        "select cast(0x0102 as varbinary(10)) as x union all select null"
    ),
)
attempt(
    "several_columns",
    lambda: driver.run(
        "select 1 as a, 'x' as b, cast(null as int) as c, cast('2021-10-01' as date) as d"
    ),
)
attempt(
    "empty_result",
    lambda: driver.run("select top 100 * from syndromic_events where zip_code = -2"),
)
attempt(
    "empty_result_columns",
    lambda: list(
        driver.run("select top 100 * from syndromic_events where zip_code = -2").columns
    ),
)
attempt(
    "empty_result_dtypes",
    lambda: {
        str(c): str(t)
        for c, t in driver.run(
            "select top 100 * from syndromic_events where zip_code = -2"
        ).dtypes.items()
    },
)
attempt(
    "table_shape", lambda: driver.run("select top 100 * from syndromic_events").shape
)
attempt(
    "table_columns",
    lambda: list(driver.run("select top 100 * from syndromic_events").columns),
)
attempt(
    "table_dtypes",
    lambda: {
        str(c): str(t)
        for c, t in driver.run("select top 100 * from syndromic_events").dtypes.items()
    },
)
