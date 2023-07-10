from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import PureWindowsPath
import json

from System import Uri
from CompAnalytics.IServices import FileUploadClient
from CompAnalytics.Contracts import FileReference
from CompAnalytics.Core import ContractSerializer

from composapy.decorators import session_required
from composapy.session import get_session
from composapy.utils import _urljoin

if TYPE_CHECKING:
    from composapy.dataflow.models import Module
    from CompAnalytics.Contracts import ExecutionHandle


@session_required
def upload_files_as_external_input(
    execution_handle: ExecutionHandle,
    module: Module,
    external_inputs: dict,
) -> None:
    """Uploads a file to the runs directory in an execution context that has been created but has
    not yet run. Then, add it as an external module input.

    Parameters:
    (ExecutionHandle) execution_handle: contract from composable dll library
    (Module) module: module from composapy models
    (dict[str, any]) external_inputs: example => {input_name: value, ...}
    """
    session_uri = get_session().uri
    session_login_type = get_session().ResourceManager.Login

    module_name = module.contract.ModuleInputs["Name"]
    module_input = module.contract.ModuleInputs["Input"]

    uri = Uri(_urljoin(session_uri, "Services/FileUploadService.svc"))

    file_path = str(PureWindowsPath(external_inputs[module_name.ValueObj]))

    client = FileUploadClient(uri, session_login_type, execution_handle)
    client.UploadFiles(file_path, module.contract.UiHandle, module_input.UiHandle)


@session_required
def upload_files_to_runs_dir(
    execution_handle: ExecutionHandle, file_path: PureWindowsPath
) -> FileReference:
    """Uploads a file to the runs directory an execution context that has been created but has
    not yet run.

    Parameters:
    (ExecutionHandle) execution_handle: contract from composable dll library
    (PureWindowsPath) file_path: file to upload
    """
    session_uri = get_session().uri
    session_login_type = get_session().ResourceManager.Login

    uri = Uri(_urljoin(session_uri, "Services/FileUploadService.svc"))

    client = FileUploadClient(uri, session_login_type, execution_handle)
    http_response = client.UploadFilesToRuns(file_path)
    serialized_file_ref = _extract_serialized_file_ref(http_response)
    file_ref = ContractSerializer.Deserialize[FileReference](serialized_file_ref)
    return file_ref


def _extract_serialized_file_ref(json_file_ref: str) -> str:
    return json.dumps(json.loads(json_file_ref)["d"][0])
