"""Create a DataFlow from a file, run it, and read its modules and results."""

from composapy.dataflow.api import DataFlow

flow = DataFlow.create(file_path=fixture("calculator_test.json"))
run = flow.run()
modules = run.modules

record("module_count", len(modules))
record("module_names", [m.name for m in modules])
record("first_value", modules[0].result.value)
record("second_value", modules[1].result.value)
record("formatter_value", modules.first_with_name("String Formatter 2").result.value)
attempt("module_types", lambda: [m.type for m in modules])
attempt("first_input_names", lambda: [i.name for i in modules[0].inputs])
attempt("first_result_name", lambda: modules[0].result.name)
attempt("modules_get_by_name", lambda: modules.get(name="String Formatter 2").name)
attempt(
    "modules_filter_by_name", lambda: len(modules.filter(name="String Formatter 2"))
)
attempt("module_missing_name", lambda: modules.get(name="no such module"))
