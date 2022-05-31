from __future__ import annotations
from typing import TYPE_CHECKING
import requests

from composapy.utils import urljoin

if TYPE_CHECKING:
    from composapy.dataflow.models import Module
    from composapy.session import Session
    from CompAnalytics.Contracts import ExecutionHandle


def upload_file_to_runs_dir(
    session: Session,
    execution_handle: ExecutionHandle,
    module: Module,
    external_inputs: dict,
):
    """Uploads a file to the runs directory an execution context that has been created but has
    not yet run.

    Parameters:
    (Session) session: must have valid user token attached
    (ExecutionState): execution_state: contract from composable dll library
    (Module) module: module from composapy models
    (dict[str, any]) external_inputs: example => {input_name: value, ...}
    """
    module_name = module.contract.ModuleInputs["Name"]
    module_input = module.contract.ModuleInputs["Input"]
    with open(external_inputs[module_name.ValueObj], "rb") as _file:
        response = requests.post(
            urljoin(
                session.uri,
                "Services/FileUploadService.svc/UploadFile",
            ),
            params={
                "HandleId": execution_handle.HandleId,
                "Id": execution_handle.Id,
                "ModuleHandleId": module.contract.UiHandle,
                "ModuleInputHandleId": module_input.UiHandle,
            },
            files={str(external_inputs[module_name.ValueObj]): _file},
            headers={"Authorization": session.api_token},
        )
        response.raise_for_status()
