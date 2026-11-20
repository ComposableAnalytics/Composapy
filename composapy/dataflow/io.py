from __future__ import annotations

import base64
import uuid
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING

from composapy.decorators import session_required
from composapy.session import get_session

if TYPE_CHECKING:
    from composapy.contracts import ExecutionHandle
    from composapy.dataflow.models import Module


def _multipart_file_body(file_path):
    """One Base64 part named FileUpload, as in the UploadFile capture. Returns (body, content_type)."""
    path = Path(file_path)
    if any(c in path.name for c in '"\r\n'):
        raise ValueError(
            f"The file {path.name!r} can't be uploaded: its name contains a double quote or a line break. Rename it first."
        )
    boundary = uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="FileUpload"; filename="{path.name}"\r\n'
        "Content-Type: text/plain\r\n"
        "Content-Transfer-Encoding: Base64\r\n\r\n"
    ).encode("utf-8")
    body = (
        head
        + base64.b64encode(path.read_bytes())
        + f"\r\n--{boundary}--\r\n".encode("ascii")
    )
    return body, f"multipart/form-data; boundary={boundary}"


def _run_query(execution_handle):
    return {"HandleId": str(execution_handle.HandleId), "Id": str(execution_handle.Id)}


@session_required
def upload_files_as_external_input(
    execution_handle: ExecutionHandle, module: Module, external_inputs: dict
) -> None:
    module_name = module.contract.ModuleInputs["Name"]
    module_input = module.contract.ModuleInputs["Input"]
    file_path = str(PureWindowsPath(external_inputs[module_name.ValueObj]))

    body, content_type = _multipart_file_body(file_path)
    query = {
        **_run_query(execution_handle),
        "ModuleHandleId": module.contract.UiHandle,
        "ModuleInputHandleId": module_input.UiHandle,
    }
    get_session().file_upload_service.UploadFile(
        body, _content_type=content_type, _query=query
    )


@session_required
def upload_files_to_runs_dir(execution_handle: ExecutionHandle, file_path):
    body, content_type = _multipart_file_body(file_path)
    result = get_session().file_upload_service.UploadFilesToRuns(
        body, _content_type=content_type, _query=_run_query(execution_handle)
    )
    return result[0]
