from __future__ import annotations
import pytest
import os
from pathlib import Path
import pandas as pd

from dotenv import load_dotenv

load_dotenv(".test.env")

from src.composapy.loader import load_init

load_init()


#  from src.composapy.queryview.api import QueryView
from src.composapy.dataflow.api import DataFlow
from src.composapy.dataflow.models import DataFlowObject
from src.composapy.session import Session


@pytest.fixture
def session():
    return Session(os.getenv("TEST_USERNAME"), os.getenv("TEST_PASSWORD"))


@pytest.fixture
def dataflow(session: Session) -> DataFlow:
    return DataFlow(session)


@pytest.fixture
def dataflow_object(dataflow: DataFlow, request) -> DataFlowObject:
    return dataflow.create(
        file_path=str(Path(os.path.dirname(Path(__file__)), "TestFiles", request.param))
    )


# used when a fixture needs another copy of parameterized fixture
dataflow_object_extra = dataflow_object


@pytest.fixture
def queryview(session: Session) -> queryview:
    return queryview(session)


@pytest.mark.parametrize("dataflow_object", ["calculator_test.json"], indirect=True)
def test_run_dataflow_get_output(dataflow_object: DataFlowObject):
    dataflow_rs = dataflow_object.run()

    modules = dataflow_rs.modules
    assert len(modules) == 5
    assert modules[0].result == 3.0
    assert modules[1].result == 5.0
    assert (
        modules.first_with_name("String Formatter 2").result == "This is a bad format"
    )


@pytest.mark.parametrize("dataflow_object", ["tablecreator.json"], indirect=True)
def test_convert_table_to_pandas(dataflow_object: DataFlowObject, dataflow: DataFlow):
    dataflow_rs = dataflow_object.run()

    table = dataflow_rs.modules.first_with_name("Table Creator").result
    df = dataflow.convert_table_to_df(table)

    assert type(df) == type(pd.DataFrame())


@pytest.mark.parametrize(
    "dataflow_object", ["convert_table_to_pandas_dtypes.json"], indirect=True
)
def test_convert_table_to_pandas_dtypes(
    dataflow_object: DataFlowObject, dataflow: DataFlow
):
    dataflow_rs = dataflow_object.run()

    modules = dataflow_rs.modules
    table = modules.first_with_name("Sql Query").result
    df = dataflow.convert_table_to_df(table)

    assert type(df) == type(pd.DataFrame())
    assert df.dtypes["SystemDateTimeOffset"] == "datetime64[ns]"


@pytest.mark.parametrize("dataflow_object", ["external_input_int.json"], indirect=True)
def test_external_input_int(dataflow_object: DataFlowObject, dataflow: DataFlow):
    dataflow_rs = dataflow_object.run(external_inputs={"IntInput": 3})

    assert dataflow_rs.modules.first_with_name("Calculator").result == 5.0


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
    table = dataflow_object_extra.run().modules.first_with_name("Sql Query").result

    dataflow_rs = dataflow_object.run(external_inputs={"TableInput": table})

    assert dataflow_rs.modules.first().result.Headers == table.Headers
    assert dataflow_rs.modules.first().result.SqlQuery == table.SqlQuery


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
