"""The DataFlow API round trip: save, get, run by id, run status, and the single-item module and input properties."""

from composapy.dataflow.api import DataFlow
from composapy.session import get_session

flow = DataFlow.create(file_path=fixture("calculator_test.json"))
record("unsaved_id", flow.id)
record("unsaved_repr", repr(flow))
saved = attempt(
    "save", lambda: flow.save(), show=lambda f: [type(f).__name__, f.id is not None]
)
if saved is not None:
    saved_id = saved.id
    record("saved_repr_matches_id", repr(saved) == f"DataFlowObject(id={saved_id})")
    attempt(
        "get",
        lambda: DataFlow.get(saved_id),
        show=lambda f: [type(f).__name__, f.id == saved_id, len(f.modules)],
    )
    run = attempt(
        "run_by_id",
        lambda: DataFlow.run(saved_id),
        show=lambda r: [type(r).__name__, scrub(repr(r))],
    )
    if run is not None:
        attempt("run_module_names", lambda: [m.name for m in run.modules])
        attempt(
            "get_run",
            lambda: DataFlow.get_run(run.id),
            show=lambda r: [type(r).__name__, r.id == run.id],
        )
        attempt("run_app_id_is_the_saved_id", lambda: run.app_id == saved_id)
        attempt(
            "run_status", lambda: DataFlow.run_status(run.id), show=lambda s: scrub(s)
        )
        attempt(
            "wait_for_run_execution",
            lambda: DataFlow.wait_for_run_execution(run.id),
            show=lambda w: {k: scrub(v) for k, v in dict(w).items()},
        )
        attempt("run_module_property_with_several", lambda: run.module)
    attempt(
        "run_with_external_inputs_not_a_dict",
        lambda: DataFlow.run(saved_id, external_inputs="x"),
        show=lambda r: type(r).__name__,
    )
    attempt("save_twice_keeps_the_id", lambda: flow.save().id == saved_id)
    attempt(
        "delete_the_saved_app",
        lambda: get_session().app_service.DeleteApplication(saved_id),
    )

attempt("get_missing", lambda: DataFlow.get(0), show=lambda f: type(f).__name__)
attempt("get_run_missing", lambda: DataFlow.get_run(0))
attempt("run_status_missing", lambda: DataFlow.run_status(0))
attempt("wait_missing", lambda: DataFlow.wait_for_run_execution(0))
attempt("get_not_an_id", lambda: DataFlow.get("x"))

attempt("module_property_with_several", lambda: flow.module)
single = DataFlow.create(file_path=fixture("tablecreator.json"))
attempt("single.module", lambda: single.module.name)
attempt("single.module.input_with_several", lambda: single.module.input)
attempt("single.module.inputs", lambda: [i.name for i in single.module.inputs])
attempt("single.module.results", lambda: [r.name for r in single.module.results])
attempt("single.module.result_with_none", lambda: single.module.result)

modules = flow.modules
attempt("modules.len", lambda: len(modules))
attempt("modules.first", lambda: modules.first().name)
attempt("modules.names", lambda: [m.name for m in modules])
attempt("modules.get_unique", lambda: modules.get(name="String Input").name)
attempt("modules.get_duplicate", lambda: modules.get(name="Calculator"))
attempt("modules.get_missing", lambda: modules.get(name="no such module"))
attempt("modules.filter", lambda: [m.name for m in modules.filter(name="Calculator")])
attempt("modules.first_with_name", lambda: modules.first_with_name("Calculator").name)
attempt(
    "modules.first_with_name_missing", lambda: modules.first_with_name("no such module")
)
attempt("modules.index_and_slice", lambda: [modules[0].name, modules[-1].name])
attempt("modules.repr_scrubbed", lambda: scrub(repr(modules[0])))
attempt(
    "inputs.by_name_and_repr",
    lambda: [(i.name, i.type, scrub(repr(i))) for i in modules[2].inputs],
)
attempt("results.repr", lambda: [scrub(repr(r)) for r in modules[2].results])
