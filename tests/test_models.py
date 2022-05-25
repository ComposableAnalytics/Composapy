from pathlib import Path

import pytest
from composapy.dataflow.models import DataFlowObject

from System import Uri
from CompAnalytics.Contracts import FileReference


@pytest.mark.parametrize("dataflow_object", ["tablecreator.json"], indirect=True)
def test_dataflow_object_repr_html_(dataflow_object: DataFlowObject):
    dataflow = dataflow_object.run()
    dataflow_module_result = dataflow.modules.first().result

    assert isinstance(dataflow_module_result._repr_html_(), str)


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

    assert isinstance(result.value, FileReference)
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
    assert isinstance(_file_ref, FileReference)
    assert _file_ref.LocalFile == str(file_path_object)
    assert str(_file_ref.Uri) == str(Uri(str(file_path_object)))
