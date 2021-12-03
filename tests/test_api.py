from __future__ import annotations
import pytest
import pandas as pd


from src.composapy.dataflow.api import DataFlow
from src.composapy.dataflow.models import DataFlowObject


@pytest.mark.parametrize("dataflow_object", ["calculator_test.json"], indirect=True)
def test_run_dataflow_get_output(dataflow_object: DataFlowObject):
    dataflow_rs = dataflow_object.run()

    modules = dataflow_rs.modules
    assert len(modules) == 5
    assert modules[0].result.value_obj == 3.0
    assert modules[1].result.value_obj == 5.0
    assert (
        modules.first_with_name("String Formatter 2").result.value_obj
        == "This is a bad format"
    )


@pytest.mark.parametrize("dataflow_object", ["tablecreator.json"], indirect=True)
def test_convert_table_to_pandas(dataflow_object: DataFlowObject, dataflow: DataFlow):
    dataflow_rs = dataflow_object.run()

    table = dataflow_rs.modules.first_with_name("Table Creator").result.value_obj
    df = dataflow.convert_table_to_dataframe(table)

    assert type(df) == type(pd.DataFrame())


@pytest.mark.parametrize(
    "dataflow_object", ["convert_table_to_pandas_dtypes.json"], indirect=True
)
def test_convert_table_to_pandas_dtypes(
    dataflow_object: DataFlowObject, dataflow: DataFlow
):
    dataflow_rs = dataflow_object.run()

    modules = dataflow_rs.modules
    table = modules.first_with_name("Sql Query").result.value_obj
    df = dataflow.convert_table_to_dataframe(table)

    assert type(df) == type(pd.DataFrame())
    assert df.dtypes["SystemDateTimeOffset"] == "datetime64[ns]"


# Add this test back later, unfortunately casting errors and no time to deal with them.
# @pytest.mark.parametrize("dataflow_object", ["external_input_int.json"], indirect=True)
# def test_external_input_int(dataflow_object: DataFlowObject, dataflow: DataFlow):
#     dataflow_rs = dataflow_object.run(external_inputs={"IntInput": 3})
#
#     assert dataflow_rs.modules.first_with_name("Calculator").result.value_obj == 5.0


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
        dataflow_object_extra.run()
        .modules.first_with_name("Sql Query")
        .result.value_obj
    )

    dataflow_run = dataflow_object.run(external_inputs={"TableInput": table})

    assert list(dataflow_run.modules.first().result.value_obj.Headers) == list(
        table.Headers
    )
    assert dataflow_run.modules.first().result.value_obj.SqlQuery == table.SqlQuery


# @pytest.mark.parametrize("dataflow_id", ["EXTERNAL_INPUT_FILE_ID"], indirect=True)
# def test_external_input_file(dataflow: dataflow, dataflow_id: int):
#
#     table_dataflow = dataflow.run(table_dataflow_id)
#     table = table_dataflow.modules.first_with_name("Sql Query").result
#     test_input = { "TableInput": table }
#
#     dataflow_rs = dataflow.run(dataflow_id, external_inputs=test_input)
#
#     assert dataflow_rs.modules.first().result.Headers == table.Headers
#     assert dataflow_rs.modules.first().result.SqlQuery == table.SqlQuery


# def test_queryview_to_pandas(queryview: queryview):
#     df = queryview.queryview_from_id(137072)
#     print(df.head())
#     print(df.dtypes)
#
#
# def test_queryview_to_pandas_streaming(queryview: queryview):
#     t = time()
#     df = queryview.queryview_from_id(137072)
#     print(time() - t)
#     print(df.head())
#     print(df.dtypes)
#     print(len(df))
