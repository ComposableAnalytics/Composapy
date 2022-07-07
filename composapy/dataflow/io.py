from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import PureWindowsPath

from System import Uri
from CompAnalytics.IServices import FileUploadClient

from composapy.session import get_session
from composapy.utils import _urljoin

if TYPE_CHECKING:
    from composapy.dataflow.models import Module
    from CompAnalytics.Contracts import ExecutionHandle


def upload_file_to_runs_dir(
    execution_handle: ExecutionHandle,
    module: Module,
    external_inputs: dict,
) -> None:
    """Uploads a file to the runs directory an execution context that has been created but has
    not yet run.

    Parameters:
    (ExecutionHandle): execution_handle: contract from composable dll library
    (Module) module: module from composapy models
    (dict[str, any]) external_inputs: example => {input_name: value, ...}
    """
    session = get_session()

    module_name = module.contract.ModuleInputs["Name"]
    module_input = module.contract.ModuleInputs["Input"]

    uri = Uri(_urljoin(session.uri, "Services/FileUploadService.svc"))

    windows_path = PureWindowsPath(external_inputs[module_name.ValueObj])

    FileUploadClient.UploadFileWithClient(
        uri,
        session.ResourceManager.Login,
        execution_handle,
        module.contract.UiHandle,
        module_input.UiHandle,
        str(windows_path),
    )
