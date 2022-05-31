from pathlib import Path
import pytest
import pandas as pd

from composapy.dataflow.models import DataFlowObject

from System import Uri
from CompAnalytics import Contracts


@pytest.mark.parametrize("dataflow_object", ["tablecreator.json"], indirect=True)
def test_singular_noun_retrieval_module(dataflow_object: DataFlowObject):
    assert isinstance(dataflow_object.module.contract, Contracts.Module)


@pytest.mark.parametrize("dataflow_object", ["file_input.json"], indirect=True)
def test_singular_noun_retrieval_result(dataflow_object: DataFlowObject):
    assert isinstance(dataflow_object.module.input.contract, Contracts.ModuleInput)


@pytest.mark.parametrize("dataflow_object", ["tablecreator.json"], indirect=True)
def test_singular_noun_retrieval_result(dataflow_object: DataFlowObject):
    assert isinstance(dataflow_object.module.result.contract, Contracts.ModuleOutput)


@pytest.mark.parametrize("dataflow_object", ["tablecreator.json"], indirect=True)
def test_dataflow_object_repr_html_(dataflow_object: DataFlowObject):
    dataflow = dataflow_object.run()
    dataflow_module_result = dataflow.modules.first().result

    assert isinstance(dataflow_module_result._repr_html_(), str)


@pytest.mark.parametrize("dataflow_object", ["tablecreator.json"], indirect=True)
def test_dataflow_object_to_pandas(dataflow_object: DataFlowObject):
    dataflow = dataflow_object.run()
    df = dataflow.modules.first().result.to_pandas()

    assert isinstance(df, pd.DataFrame)
    assert df["b"][1] == 3


@pytest.mark.parametrize(
    "dataflow_object,clean_file_path",
    [
        ("file_writer.json", "text-test.txt"),
        ("xlsx_writer.json", "xlsx-test.xlsx"),
        ("csv_writer.json", "csv-test.csv"),
    ],
    indirect=True,
)
def test_download_file_result(dataflow_object: DataFlowObject, clean_file_path: Path):
    dataflow_run = dataflow_object.run()
    result = dataflow_run.modules.first().result

    assert isinstance(result.value, Contracts.FileReference)
    assert result.value.LocalFile is None

    result.to_file(clean_file_path.parent, file_name=clean_file_path.name)

    assert result.value.LocalFile == str(clean_file_path)
    assert clean_file_path.exists()


@pytest.mark.parametrize(
    "file_path_object", ["create_file_ref_target.txt"], indirect=True
)
def test_create_file_reference_from_file(file_path_object):
    import composapy.helper as cp

    _file_ref = cp.file_ref(file_path_object)
    assert isinstance(_file_ref, Contracts.FileReference)
    assert _file_ref.LocalFile == str(file_path_object)
    assert str(_file_ref.Uri) == str(Uri(str(file_path_object)))
