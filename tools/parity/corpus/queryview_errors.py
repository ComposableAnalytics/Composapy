"""Queries and arguments that must fail, and fail the same way: errors, validation, timeouts, a missing Key."""

from composapy.key.api import Key
from composapy.queryview.api import QueryView

driver = QueryView.driver(Key.get(name=fixtures["key_name"]))

attempt(
    "invalid_column",
    lambda: driver.run("select column_does_not_exist from syndromic_events"),
)
attempt(
    "syntax_error_without_validation",
    lambda: driver.run(
        "select top 5 * from syndromic_events where", validate_query=False
    ),
)
attempt(
    "syntax_error_with_validation",
    lambda: driver.run(
        "select top 5 * from syndromic_events where", validate_query=True
    ),
)
attempt(
    "validation_ignores_warnings",
    lambda: len(
        driver.run(
            "select top 5 * into #t from syndromic_events; select * from #t",
            validate_query=True,
        )
    ),
)
attempt(
    "validate_query_not_a_bool",
    lambda: driver.run("select 1", validate_query="not a bool"),
)
attempt(
    "timeout_expired",
    lambda: driver.run(
        "waitfor delay '00:00:07' select top 100 * from syndromic_events", timeout=5
    ),
)
attempt("timeout_negative", lambda: driver.run("select 1", timeout=-7))
attempt("timeout_not_a_number", lambda: driver.run("select 1", timeout="soon"))
attempt("empty_query", lambda: driver.run(""))
attempt("query_not_text", lambda: driver.run(5))
attempt("two_result_sets", lambda: driver.run("select 1 as a; select 2 as b"))
attempt("incorrect_syntax", lambda: driver.run("select!!!! * from syndromic_events"))


def no_key():
    bare = QueryView.driver()
    bare.contract.DbConnectionId = None
    bare._key = None
    return bare.run("select top 100 from syndromic_events")


attempt("no_key_connected", no_key)
attempt(
    "driver_with_timeout_argument",
    lambda: QueryView.driver(
        Key.get(name=fixtures["key_name"]), timeout=5
    ).get_driver_timeout(),
)
attempt(
    "driver_with_invalid_timeout",
    lambda: QueryView.driver(Key.get(name=fixtures["key_name"]), timeout=-1),
)
attempt(
    "driver_with_validate_query",
    lambda: QueryView.driver(
        Key.get(name=fixtures["key_name"]), validate_query=True
    ).validate_query,
)
