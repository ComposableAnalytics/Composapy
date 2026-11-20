"""Read a saved Key by name and by id, and look at what a script can read from it."""

from composapy.key.api import Key

by_name = Key.get(name=fixtures["key_name"])
by_id = Key.get(key_id=fixtures["key_id"])

record("by_name.name", by_name.name)
record("by_name.id_is_the_fixture", by_name.id == fixtures["key_id"])
record("by_id.name", by_id.name)
record("same_id", by_name.id == by_id.id)
record("repr", repr(by_name))
attempt("str", lambda: str(by_name))
attempt("type", lambda: by_name.type)
for attribute in (
    "Host",
    "Port",
    "Username",
    "Database",
    "ConnectionParameters",
    "UseMultipleActiveResultSets",
):
    attempt(f"attribute.{attribute}", lambda a=attribute: getattr(by_name, a))
attempt(
    "has_a_password", lambda: bool(getattr(by_name, "Password"))
)  # the value itself is not kept
attempt("attribute_missing", lambda: getattr(by_name, "NoSuchSetting"))
attempt(
    "get_by_name_and_id_together",
    lambda: Key.get(name=fixtures["key_name"], key_id=fixtures["key_id"]).name,
)
attempt("get_without_arguments", lambda: Key.get())
attempt("get_missing_id", lambda: Key.get(key_id=0))
attempt("get_missing_name", lambda: Key.get(name="ZzzNoSuchKeyZzz"))
attempt("get_positional_id", lambda: Key.get(fixtures["key_id"]).name)
