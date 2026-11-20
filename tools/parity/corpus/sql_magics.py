"""The README's %sql line magic and %%sql cell magic, run through a real IPython shell, and the interactive table display."""

import contextlib
import io

from IPython.core.interactiveshell import InteractiveShell

from composapy.key.api import Key

Key.get(name=fixtures["key_name"]).register()
shell = InteractiveShell.instance()
shell.run_cell(
    "import composapy.magics", store_history=False
)  # what the loader does inside a notebook


def run(source):
    """What running the cell gives: the value it returned, what it printed, the variables it left, or the error."""
    captured = io.StringIO()
    shell.user_ns.pop("captured_df", None)
    with contextlib.redirect_stdout(captured):
        result = shell.run_cell(source, store_history=False)
    error = result.error_in_exec or result.error_before_exec
    warnings = [
        line for line in captured.getvalue().splitlines() if line.startswith("WARNING")
    ]  # the rest is IPython's traceback and object addresses
    outcome = {
        "warnings": warnings,
        "variable_captured": "captured_df" in shell.user_ns,
    }
    if error is not None:
        outcome["error"] = [type(error).__name__, str(error)]
    else:
        value = result.result
        outcome["value"] = (
            value
            if value is None or hasattr(value, "to_dict")
            else type(value).__name__
        )
        outcome["is_html"] = (
            "<!-- DataTables -->" in value._repr_html_()
            if hasattr(value, "_repr_html_") and not hasattr(value, "to_dict")
            else None
        )
    return outcome


QUERY = "select top 3 * from syndromic_events order by 1"
CASES = {
    "line": f"%sql {QUERY}",
    "line_scalar": "%sql select 1 as a",
    "line_empty": "%sql",
    "line_error": "%sql select!!!! * from syndromic_events",
    "cell": f"%%sql\n{QUERY}",
    "cell_multiline": "%%sql\nselect top 3\n    *\nfrom\n    syndromic_events\nwhere\n    age is not null\norder by 1",
    "cell_timeout": f"%%sql -t 30\n{QUERY}",
    "cell_timeout_text": f"%%sql -t x\n{QUERY}",
    "cell_variable": f"%%sql captured_df\n{QUERY}",
    "cell_variable_silenced": f"%%sql -s captured_df\n{QUERY}",
    "cell_variable_not_an_identifier": f"%%sql 1bad\n{QUERY}",
    "cell_variable_a_keyword": f"%%sql class\n{QUERY}",
    "cell_silenced": f"%%sql -s\n{QUERY}",
    "cell_precompile": f"%%sql -p\n{QUERY}",
    "cell_precompile_error": "%%sql -p\nselect!!!! * from syndromic_events",
    "cell_interactive": f"%%sql -i\n{QUERY}",
    "cell_interactive_with_variable": f"%%sql -i captured_df\n{QUERY}",
    "cell_all_flags": f"%%sql -t 30 -p -s captured_df\n{QUERY}",
    "cell_unknown_flag": f"%%sql -z\n{QUERY}",
    "cell_error": "%%sql\nselect!!!! * from syndromic_events",
}
for label, source in CASES.items():
    attempt(label, lambda s=source: run(s))

attempt(
    "magics_are_registered",
    lambda: sorted(
        m
        for m in ("sql",)
        if m in shell.magics_manager.magics["line"]
        and m in shell.magics_manager.magics["cell"]
    ),
)

# the README's last cell: a Table result shows as an interactive table when the option is on
import composapy.interactive.options as iopts
from composapy.dataflow.api import DataFlow

table = (
    DataFlow.create(file_path=fixture("tablecreator.json"))
    .run()
    .modules.first_with_name("Table Creator")
    .result.value
)
attempt(
    "table_html_default_is_a_dataframe",
    lambda: "<!-- DataTables -->" in table._repr_html_(),
)
iopts.SHOW_INTERACTIVE_TABLES = True
attempt("table_html_interactive", lambda: "<!-- DataTables -->" in table._repr_html_())
attempt("table_html_interactive_is_text", lambda: isinstance(table._repr_html_(), str))
iopts.SHOW_INTERACTIVE_TABLES = False
