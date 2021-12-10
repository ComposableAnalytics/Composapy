from __future__ import annotations
import pytest
import pandas as pd
import os

if os.getenv("IS_UNPACKAGED"):
    from src.composapy.dataflow.api import DataFlow
    from src.composapy.dataflow.models import DataFlowObject

else:
    from composapy.dataflow.api import DataFlow
    from composapy.dataflow.models import DataFlowObject


@pytest.mark.parametrize("dataflow_object", ["calculator_test.json"], indirect=True)
def test_run_dataflow_get_output(dataflow_object: DataFlowObject):
    dataflow_run = dataflow_object.run()

    modules = dataflow_run.modules
    assert len(modules) == 5
    assert modules[0].result.value == 3.0
    assert modules[1].result.value == 5.0
    assert (
        modules.first_with_name("String Formatter 2").result.value
        == "This is a bad format"
    )


@pytest.mark.parametrize("dataflow_object", ["tablecreator.json"], indirect=True)
def test_convert_table_to_pandas(dataflow_object: DataFlowObject, dataflow: DataFlow):
    dataflow_run = dataflow_object.run()

    table = dataflow_run.modules.first_with_name("Table Creator").result.value
    df = dataflow.convert_table_to_dataframe(table)

    assert type(df) == type(pd.DataFrame())


@pytest.mark.parametrize(
    "dataflow_object", ["convert_table_to_pandas_dtypes.json"], indirect=True
)
def test_convert_table_to_pandas_dtypes(
    dataflow_object: DataFlowObject, dataflow: DataFlow
):
    dataflow_run = dataflow_object.run()

    modules = dataflow_run.modules
    table = modules.first_with_name("Sql Query").result.value
    df = dataflow.convert_table_to_dataframe(table)

    assert type(df) == type(pd.DataFrame())
    assert df.dtypes["SystemDateTimeOffset"] == "datetime64[ns]"


@pytest.mark.parametrize(
    "dataflow_object", ["external_input_table.json"], indirect=True
)
@pytest.mark.parametrize(
    "dataflow_object_extra", ["convert_table_to_pandas_dtypes.json"], indirect=True
)
def test_external_input_table(
    dataflow_object: DataFlowObject, dataflow_object_extra: DataFlowObject
):
    # lazily create a new table contract by running a dataflow that has a table result
    table = (
        dataflow_object_extra.run().modules.first_with_name("Sql Query").result.value
    )

    dataflow_run = dataflow_object.run(external_inputs={"TableInput": table})

    assert list(dataflow_run.modules.first().result.value.Headers) == list(
        table.Headers
    )
    assert dataflow_run.modules.first().result.value.SqlQuery == table.SqlQuery
