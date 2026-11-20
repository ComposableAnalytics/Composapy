"""The same wrong calls under both variants: each must fail, and fail the same way."""

from composapy.dataflow.api import DataFlow
from composapy.key.api import Key
from composapy.queryview.api import QueryView
from composapy.session import get_session

attempt("dataflow_run_missing_id", lambda: DataFlow.run(0))
attempt("dataflow_get_missing_id", lambda: DataFlow.get(0))
attempt(
    "dataflow_create_missing_file",
    lambda: DataFlow.create(file_path="C:/no/such/file.json"),
)
attempt("key_get_missing_name", lambda: Key.get(name="a key that does not exist"))
attempt("key_get_missing_id", lambda: Key.get(id=0))
attempt("key_search_no_match", lambda: Key.search("a key that does not exist"))
attempt("queryview_run_missing_id", lambda: QueryView.run(0))
attempt("queryview_driver_without_key", lambda: QueryView.driver().run("select 1"))
record("session_uri_matches", get_session().uri.endswith("/"))
