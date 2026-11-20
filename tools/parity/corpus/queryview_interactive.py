"""The interactive (paged) driver and saved QueryViews run interactively: their results are HTML tables."""

from composapy.key.api import Key
from composapy.queryview.api import QueryView

key = Key.get(name=fixtures["key_name"])
driver = QueryView.driver(key, interactive=True)
record("driver_type", type(driver).__name__)
record("driver_repr", repr(driver))

result = attempt(
    "run_type",
    lambda: type(driver.run("select * from syndromic_events where age > 100")).__name__,
)
attempt(
    "run_is_html",
    lambda: "<!-- DataTables -->"
    in driver.run("select * from syndromic_events where age > 100")._repr_html_(),
)
attempt(
    "run_has_the_result_interface",
    lambda: [
        hasattr(driver.run("select 1 as a"), name)
        for name in ("_repr_html_", "to_pandas", "to_dataframe")
    ],
)
attempt(
    "incorrect_syntax",
    lambda: driver.run("select!!!! * from syndromic_events where age > 100"),
)
attempt(
    "invalid_column",
    lambda: driver.run("select top 100 *, FAKE_COL from syndromic_events"),
)
attempt(
    "saved_run_type",
    lambda: type(
        QueryView.run(fixtures["queryview_ids"]["qv_simple"], interactive=True)
    ).__name__,
)
attempt(
    "saved_run_is_html",
    lambda: "<!-- DataTables -->"
    in QueryView.run(
        fixtures["queryview_ids"]["qv_simple"], interactive=True
    )._repr_html_(),
)
attempt(
    "saved_run_error",
    lambda: QueryView.run(fixtures["queryview_ids"]["qv_error"], interactive=True),
)
