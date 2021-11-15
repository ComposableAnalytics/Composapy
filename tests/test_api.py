import pytest
import os
from pathlib import Path
import pandas as pd
from time import time

from ComposaPy.DataFlow.api import DataFlow
from ComposaPy.QueryView.api import QueryView
from ComposaPy.session import Session

from System.Collections.Generic import List
from CompAnalytics.Contracts.Tables import Table, TableColumnCollection

TEST_API_KEY = os.getenv("TEST_API_KEY")
TEST_USERNAME = os.getenv("TEST_USERNAME")
TEST_PASSWORD = os.getenv("TEST_PASSWORD")
ROOT_PATH_COMPOSABLE = os.getenv("ROOT_PATH_COMPOSABLE")
ROOT_PATH_PYTHONNET = os.getenv("ROOT_PATH_PYTHONNET")


@pytest.fixture
def session():
    return Session(TEST_USERNAME, TEST_PASSWORD)

@pytest.fixture
def dataflow(session: Session) -> DataFlow:
    return DataFlow(session)

@pytest.fixture
def queryview(session: Session) -> QueryView:
    return QueryView(session)


@pytest.fixture
def dataflow_id(request) -> int:
    from dotenv import dotenv_values
    return int(dotenv_values(".test.env").get(request.param))


def test_run_dataflow_get_output(dataflow: DataFlow):
    app_id = dataflow.import_app_from_json(
        str(Path(ROOT_PATH_COMPOSABLE, "UnitTests", "TestData", "CalculatorTest.json"))
    )
    dataflow_rs = dataflow.run(app_id)
    modules = dataflow_rs.modules

    assert len(modules) == 5
    assert modules[0].result == 3.0
    assert modules[1].result == 5.0

    assert modules.first_with_name("String Formatter 2").result == "This is a bad format"


def test_convert_table_to_pandas(dataflow: DataFlow):
    app_id = dataflow.import_app_from_json(
        str(Path(ROOT_PATH_PYTHONNET, "Tests", "TestFiles", "tablecreator.json"))
    )

    dataflow_rs = dataflow.run(app_id)
    dataflow.app_service.DeleteApplication(app_id)
    table = dataflow_rs.modules.first_with_name("Table Creator").result
    df = dataflow.convert_table_to_df(table)

    assert type(df) == type(pd.DataFrame())


@pytest.mark.parametrize("dataflow_id", ["CONVERT_TABLE_TO_PANDAS_DTYPES_ID"], indirect=True)
def test_convert_table_to_pandas_dtypes(dataflow: DataFlow, dataflow_id: int):
    dataflow_rs = dataflow.run(dataflow_id)
    modules = dataflow_rs.modules
    table = modules.first_with_name("Sql Query").result
    df = dataflow.convert_table_to_df(table)

    assert type(df) == type(pd.DataFrame())
    assert df.dtypes["SystemDateTimeOffset"] == "datetime64[ns]"


@pytest.mark.parametrize("dataflow_id", ["EXTERNAL_INPUT_INT_ID"], indirect=True)
def test_external_input_int(dataflow: DataFlow, dataflow_id: int):
    test_input = { "IntInput": 3 }

    dataflow_rs = dataflow.run(dataflow_id, external_inputs=test_input)

    assert dataflow_rs.modules.first_with_name("Calculator").result == 5.0


@pytest.mark.parametrize("dataflow_id", ["EXTERNAL_INPUT_TABLE_ID"], indirect=True)
def test_external_input_table(dataflow: DataFlow, dataflow_id: int):
    # easiest way to create  a table is to just get it from another test dataflow
    from dotenv import dotenv_values
    table_dataflow_id = int(dotenv_values(".test.env").get("CONVERT_TABLE_TO_PANDAS_DTYPES_ID"))
    table_dataflow = dataflow.run(table_dataflow_id)
    table = table_dataflow.modules.first_with_name("Sql Query").result
    test_input = { "TableInput": table }

    dataflow_rs = dataflow.run(dataflow_id, external_inputs=test_input)

    assert dataflow_rs.modules.first().result.Headers == table.Headers
    assert dataflow_rs.modules.first().result.SqlQuery == table.SqlQuery


# def test_all_external_inputs_pw(self):
#     comp_session = ca.ComposableSession(user,pw)
#     path_to_my_csv = r'C:\Composable\Product\UnitTests\TestData\DupColumns.csv'
#     dict_of_inputs = {'IntInput': 3, 'FileInput': path_to_my_csv, 'TableInput': pd.DataFrame({'a':[1]})}
#     dataflow_id = 7552
#     run_id = comp_session.run_dataflow_with_inputs(dataflow_id,dict_of_inputs)
#     print(run_id)
#     csv_test = Path(ROOT_PATH_COMPOSABLE, "UnitTests", "TestData", "DupColumns.csv")


# def test_queryview_to_pandas(queryview: QueryView):
#     df = queryview.queryview_from_id(137072)
#     print(df.head())
#     print(df.dtypes)
#
#
# def test_queryview_to_pandas_streaming(queryview: QueryView):
#     t = time()
#     df = queryview.queryview_from_id(137072)
#     print(time() - t)
#     print(df.head())
#     print(df.dtypes)
#     print(len(df))
