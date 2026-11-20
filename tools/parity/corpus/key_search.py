"""Search Keys by name."""

from composapy.key.api import Key

found = Key.search(fixtures["key_name"])
record("count", len(found))
record("names", [k.name for k in found])
record("ids_include_the_fixture", fixtures["key_id"] in [k.id for k in found])
record("repr", [repr(k) for k in found])
attempt("type_of_result", lambda: type(found).__name__)
attempt("partial_name", lambda: [k.name for k in Key.search("ParityHealth")])
attempt("no_match", lambda: Key.search("ZzzNoSuchKeyZzz"))
attempt("empty_text", lambda: len(Key.search("")))
attempt("syntax_error", lambda: Key.search("a -b not"))
attempt(
    "paged_first",
    lambda: [
        k.name for k in Key.search("ParityHealth", index_start=0, number_results=1)
    ],
)
attempt(
    "paged_past_the_end",
    lambda: [
        k.name for k in Key.search("ParityHealth", index_start=50, number_results=10)
    ],
)
attempt(
    "number_results_zero",
    lambda: [k.name for k in Key.search("ParityHealth", number_results=0)],
)
attempt(
    "negative_start",
    lambda: [k.name for k in Key.search("ParityHealth", index_start=-1)],
)
