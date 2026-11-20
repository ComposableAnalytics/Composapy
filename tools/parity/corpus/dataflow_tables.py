"""Tables from DataFlow results: reading them, converting them, and passing one into another DataFlow."""

from composapy.dataflow.api import DataFlow


def describe(table):
    return {
        "type": type(table).__name__,
        "headers": list(table.Headers),
        "columns": [(c.Name, c.Type) for c in table.Columns],
        "has_sql_query": bool(table.SqlQuery),
    }


creator = DataFlow.create(file_path=fixture("tablecreator.json"))
run = creator.run()
table = attempt(
    "tablecreator.table",
    lambda: run.modules.first_with_name("Table Creator").result.value,
    show=describe,
)
if table is not None:
    record("tablecreator.describe", describe(table))
    attempt("tablecreator.to_pandas", lambda: table.to_pandas())
    attempt(
        "tablecreator.to_pandas_twice_equal",
        lambda: table.to_pandas().equals(table.to_pandas()),
    )
    attempt(
        "tablecreator.repr_html_is_text", lambda: isinstance(table._repr_html_(), str)
    )
    attempt("tablecreator.headers_type", lambda: type(table.Headers).__name__)

first = DataFlow.create(file_path=fixture("datetimeoffset_table_column_dtypes.json"))
source = first.run().modules.get(name="Column Type Converter").result.value
record("converter.describe", describe(source))
attempt("converter.to_pandas", lambda: source.to_pandas())

passer = DataFlow.create(file_path=fixture("external_input_table.json"))
passed = attempt(
    "pass_a_table.run",
    lambda: passer.run(external_inputs={"TableInput": source})
    .modules.first()
    .result.value,
    show=describe,
)
if passed is not None:
    record("pass_a_table.describe", describe(passed))
    record("pass_a_table.same_headers", list(passed.Headers) == list(source.Headers))
    record("pass_a_table.same_sql_query", passed.SqlQuery == source.SqlQuery)
    attempt("pass_a_table.to_pandas", lambda: passed.to_pandas())

for name in (
    "table_module_input.json",
    "table_output_to_input.json",
    "convert_table_to_pandas_dtypes.json",
    "empty.json",
):
    label = name.split(".")[0]

    def run_all(n=name):
        result = DataFlow.create(file_path=fixture(n)).run()
        return [(m.name, type(m.result.value).__name__) for m in result.modules]

    attempt(f"{label}.module_results", run_all)

attempt(
    "to_pandas_without_a_session",
    lambda: __import__(
        "composapy.session", fromlist=["Session"]
    ).Session.clear_registration()
    or table.to_pandas(),
)
