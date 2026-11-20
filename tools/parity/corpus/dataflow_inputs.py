"""Pass Python values as external inputs to a DataFlow and read what the run made of them."""

from composapy.dataflow.api import DataFlow

flow = DataFlow.create(file_path=fixture("external_input_int.json"))
record("module_names", [m.name for m in flow.modules])
record("input_names", [i.name for m in flow.modules for i in m.inputs])


def results(value):
    run = flow.run(external_inputs={"IntInput": int_input(value)})
    return [m.result.value for m in run.modules]


for label, value in [
    ("int_zero", 0),
    ("int_positive", 5),
    ("int_negative", -3),
    ("int_max32", 2147483647),
    ("int_over32", 2147483648),
    ("int_big", 2**40),
    ("int_huge", 2**70),
    ("float_whole", 5.0),
    ("float_fraction", 5.5),
    ("bool_true", True),
    ("text_number", "7"),
    ("text_words", "seven"),
    ("none", None),
    ("list", [1, 2]),
    ("dict", {"a": 1}),
]:
    attempt(f"IntInput.{label}", lambda v=value: results(v))

attempt(
    "input_name_does_not_exist",
    lambda: flow.run(external_inputs={"NoSuchInput": int_input(1)}),
)
attempt(
    "external_inputs_not_a_dict", lambda: flow.run(external_inputs=[("IntInput", 1)])
)
attempt("run_with_no_inputs", lambda: len(flow.run().modules))
attempt(
    "run_twice_gives_distinct_run_ids",
    lambda: flow.run(external_inputs={"IntInput": int_input(1)}).id
    != flow.run(external_inputs={"IntInput": int_input(1)}).id,
)

strings = DataFlow.create(file_path=fixture("table_column_dtypes.json"))
for label, value in [
    ("ascii", "Boolean"),
    ("quote", "it's"),
    ("unicode", "café 中文"),
    ("empty", ""),
    ("long", "x" * 5000),
]:
    attempt(
        f"ColumnType.{label}",
        lambda v=value: strings.run(
            external_inputs={"ColumnType": v, "ColumnData": list_input(["a"])}
        )
        .modules[0]
        .name,
    )
