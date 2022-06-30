from __future__ import annotations
import pytest
import pandas as pd
import os
from pathlib import Path

from composapy.dataflow.models import DataFlowObject
from composapy.session import Session
from composapy.dataflow.api import DataFlow

from CompAnalytics import Contracts


@pytest.mark.parametrize(
    "dataflow_object",
    [("Windows", "calculator_test.json")],
    indirect=True,
)
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


@pytest.mark.parametrize(
    "dataflow_object",
    [("Windows", "tablecreator.json")],
    indirect=True,
)
def test_convert_table_to_pandas(dataflow_object: DataFlowObject):
    dataflow_run = dataflow_object.run()

    df = dataflow_run.modules.first_with_name("Table Creator").result.value.to_pandas()

    assert type(df) == type(pd.DataFrame())


@pytest.mark.parametrize(
    "dataflow_object,dataflow_object_extra",
    [
        (
            ("Windows", "external_input_table.json"),
            ("Windows", "datetimeoffset_table_column_dtypes.json"),
        )
    ],
    indirect=True,
)
def test_external_input_table(
    dataflow_object: DataFlowObject,
    dataflow_object_extra: DataFlowObject,
):
    # lazily create a new table contract by running a dataflow that has a table result
    table = (
        dataflow_object_extra.run()
        .modules.get(name="Column Type Converter")
        .result.value
    )
    dataflow_run = dataflow_object.run(external_inputs={"TableInput": table})

    assert list(dataflow_run.modules.first().result.value.Headers) == list(
        table.Headers
    )
    assert dataflow_run.modules.first().result.value.SqlQuery == table.SqlQuery


@pytest.mark.parametrize("file_path_string", ["external_input_file.txt"], indirect=True)
@pytest.mark.parametrize(
    "dataflow_object",
    [("Windows", "external_file_input.json")],
    indirect=True,
)
def test_external_input_file(dataflow_object: DataFlowObject, file_path_string: str):
    run = dataflow_object.run(
        external_inputs={"my external file input": file_path_string}
    )
    # my IDE automatically adds \r\n, so I just leave it that way in test
    assert str(run.modules.get(name="File Reader").result.value) == "success\r\n"


@pytest.mark.parametrize(
    "dataflow_object",
    [("Windows", "tablecreator.json")],
    indirect=True,
)
def test_dataflow_object_to_pandas(dataflow_object: DataFlowObject):
    dataflow = dataflow_object.run()
    df = dataflow.modules.first().result.value.to_pandas()

    assert isinstance(df, pd.DataFrame)
    assert df["b"][1] == 3


@pytest.mark.parametrize(
    "clean_file_path",
    ["text-test.txt", "xlsx-test.xlsx", "csv-test.csv"],
    indirect=True,
)
@pytest.mark.parametrize(
    "dataflow_object",
    [("Windows", "csv_writer.json")],
    indirect=True,
)
def test_download_file_result(dataflow_object: DataFlowObject, clean_file_path: Path):
    dataflow_run = dataflow_object.run()
    file_ref = dataflow_run.modules.first().result.value

    assert isinstance(file_ref, Contracts.FileReference)
    assert file_ref.LocalFile is None

    new_file_ref = file_ref.to_file(
        clean_file_path.parent, file_name=clean_file_path.name
    )

    assert new_file_ref.LocalFile == str(clean_file_path)
    assert clean_file_path.exists()


@pytest.mark.parametrize("session", ["Windows"], indirect=True)
def test_session(session: Session):
    DataFlow.create(
        file_path=str(
            Path(os.path.dirname(Path(__file__)), "TestFiles", "calculator_test.json")
        )
    )  # dataflow.create() will throw an error if session authentication failed
    assert True
