import pytest
import os

if os.getenv("IS_UNPACKAGED"):
    from src.composapy.dataflow.models import DataFlowObject
else:
    from composapy.dataflow.models import DataFlowObject


@pytest.mark.parametrize("dataflow_object", ["table_module_input.json"], indirect=True)
def test_dataflow_object_inputs_repr_html_(dataflow_object: DataFlowObject):
    # get the input named "Table" for the first module in dataflow object
    table_input = dataflow_object.modules.first().inputs.filter(name="Table")[0]

    assert isinstance(table_input._repr_html_(), str)


@pytest.mark.parametrize(
    "dataflow_object", ["table_output_to_input.json"], indirect=True
)
def test_dataflow_run_results_repr_html_(dataflow_object: DataFlowObject):
    # get the result of the first module returned from filtering by name "Table to JSON"
    table_input = dataflow_object.run().modules.filter(name="Sql Query")[0].result
    assert isinstance(table_input._repr_html_(), str)
