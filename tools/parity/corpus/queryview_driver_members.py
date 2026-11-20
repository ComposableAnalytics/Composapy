"""The query driver's own members: connect, connection_info, and the timeout accessors."""

from composapy.key.api import Key
from composapy.queryview.api import QueryView

key = Key.get(name=fixtures["key_name"])
driver = QueryView.driver()
attempt("key_before_connect", lambda: driver.key)
attempt("repr_before_connect", lambda: repr(driver))
attempt("connect", lambda: driver.connect(key))
attempt("key_after_connect", lambda: driver.key.name)
attempt("repr_after_connect", lambda: repr(driver))
attempt("connect_not_a_key", lambda: driver.connect("a key"))
attempt("connect_none", lambda: driver.connect(None))
attempt("connection_info_names", lambda: sorted(driver.connection_info))
attempt("connection_info_name", lambda: driver.connection_info["name"])
attempt(
    "connection_info_has_password_text",
    lambda: bool(driver.connection_info.get("Password")),
)

attempt("default_timeout", lambda: driver.get_driver_timeout())
attempt(
    "set_timeout",
    lambda: (driver.set_driver_timeout(7), driver.get_driver_timeout())[1],
)
for label, value in [
    ("zero", 0),
    ("negative", -1),
    ("float", 2.5),
    ("text", "5"),
    ("none", None),
    ("bool", True),
    ("huge", 2**40),
]:
    attempt(
        f"set_timeout.{label}",
        lambda v=value: (driver.set_driver_timeout(v), driver.get_driver_timeout())[1],
    )
attempt("timeout_applies_to_a_query", lambda: len(driver.run("select 1 as a")))
attempt(
    "driver_with_key_and_timeout",
    lambda: (lambda d: [d.key.name, d.get_driver_timeout()])(
        QueryView.driver(key, timeout=9)
    ),
)
attempt(
    "driver_interactive_flag",
    lambda: type(QueryView.driver(key, interactive=True)).__name__,
)
attempt(
    "validate_query_property",
    lambda: [
        QueryView.driver(key, validate_query=True).validate_query,
        QueryView.driver(key).validate_query,
    ],
)
