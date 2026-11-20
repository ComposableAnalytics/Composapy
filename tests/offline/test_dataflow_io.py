"""Offline tests for composapy.dataflow.io: the multipart body, the query, and what comes back.

A fake FileUploadService records what the functions send. Two tests also run the real client and proxy over a
fake HTTP session, to check the bytes that would go on the wire.
"""

import email
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from composapy._wire import codec
from composapy.auth import AuthMode
from composapy.contracts import ExecutionHandle, FileReference
from composapy.dataflow.models import DataFlowObject
from composapy.dataflow.io import (
    _multipart_file_body,
    upload_files_as_external_input,
    upload_files_to_runs_dir,
)
from composapy.decorators import SessionRequiredError
from composapy.exceptions import ServiceFault
from composapy.session import Session

URI = "http://example.test/CompApp/"
HANDLE_ID = "70850f2b-e3a3-48f8-9c44-68c7ad009375"
RUN_ID = 685736
UPLOADED_URI = "/CompApp/runs/70850f2b-e3a3-48f8-9c44-68c7ad009375/5f051543-bf10-482a-8be1-7b11e87d2009/note.txt"
REPLY_FILE_REFERENCES = (
    '{"d": [{"__type": "FileReference:#CompAnalytics.Contracts", "Uri": "%s"}]}'
    % UPLOADED_URI
)


class FakeFileUploadService:
    """Records every call; answers as the decoded replies would look."""

    def __init__(self):
        self.calls = []

    def UploadFile(self, body, _content_type=None, _query=None):
        self.calls.append(("UploadFile", body, _content_type, _query))
        return len(body)

    def UploadFilesToRuns(self, body, _content_type=None, _query=None):
        self.calls.append(("UploadFilesToRuns", body, _content_type, _query))
        return codec.unwrap(codec.decode(REPLY_FILE_REFERENCES))


@pytest.fixture
def session():
    session = Session(uri=URI, auth_mode=AuthMode.TOKEN, credentials="token-for-tests")
    session.register()
    yield session
    Session.clear_registration()


@pytest.fixture
def service(session):
    fake = FakeFileUploadService()
    session.services["FileUploadService"] = fake
    return fake


@pytest.fixture
def handle():
    return ExecutionHandle(HandleId=HANDLE_ID, Id=RUN_ID)


@pytest.fixture
def module():
    contract = codec.decode(
        json.dumps(
            {
                "__type": "Module:#CompAnalytics.Contracts",
                "UiHandle": "module4bd94be4-390d-499f-8553-f7daaf917e66",
                "ModuleInputs": [
                    {"Name": "Name", "ValueObj": "my_file", "UiHandle": "input0"},
                    {"Name": "Input", "ValueObj": None, "UiHandle": "input6"},
                ],
            }
        )
    )
    return SimpleNamespace(contract=contract)


def parse_multipart(body, content_type):
    """Parse the body with the standard library, which also decodes the Base64 part."""
    message = email.message_from_bytes(
        b"Content-Type: " + content_type.encode("ascii") + b"\r\n\r\n" + body
    )
    assert message.is_multipart(), "the body is not a multipart message"
    parts = message.get_payload()
    assert len(parts) == 1
    return message, parts[0]


# ----------------------------------------------------------------------------------------------
# The multipart body
# ----------------------------------------------------------------------------------------------


def test_the_body_is_one_base64_part_named_fileupload(tmp_path):
    file = tmp_path / "note.txt"
    file.write_bytes(b"hello\n")
    body, content_type = _multipart_file_body(file)

    message, part = parse_multipart(body, content_type)
    assert message.get_content_type() == "multipart/form-data"
    assert part.get_param("name", header="content-disposition") == "FileUpload"
    assert part.get_filename() == "note.txt"
    assert part["Content-Transfer-Encoding"] == "Base64"
    assert part.get_payload(decode=True) == b"hello\n"


def test_the_boundary_in_the_header_is_the_one_in_the_body(tmp_path):
    file = tmp_path / "a.bin"
    file.write_bytes(b"x")
    body, content_type = _multipart_file_body(file)
    boundary = content_type.split("boundary=")[1]
    assert body.startswith(f"--{boundary}\r\n".encode("ascii"))
    assert body.endswith(f"\r\n--{boundary}--\r\n".encode("ascii"))


def test_every_body_gets_its_own_boundary(tmp_path):
    file = tmp_path / "a.bin"
    file.write_bytes(b"x")
    assert _multipart_file_body(file)[1] != _multipart_file_body(file)[1]


@pytest.mark.parametrize(
    "name, content",
    [
        ("binary.bin", bytes(range(256))),  # the 256-byte file from the capture
        ("text-lf.txt", b"one\ntwo\n"),  # not re-encoded, no CRLF added
        ("text-crlf.csv", b"a,b\r\n1,2\r\n"),
        (
            "utf8.txt",
            "café 中文\n".encode("utf-8"),
        ),  # not read through an ANSI code page
        ("empty.txt", b""),
        ("big.dat", bytes(range(256)) * 4000),  # about 1 MB
    ],
    ids=[
        "binary",
        "text-lf",
        "text-crlf",
        "utf8",
        "empty",
        "about-1MB",
    ],  # short ids: the bytes must not become the test name
)
def test_every_file_is_sent_byte_for_byte(tmp_path, name, content):
    file = tmp_path / name
    file.write_bytes(content)
    _, part = parse_multipart(*_multipart_file_body(file))
    assert part.get_payload(decode=True) == content
    assert part.get_filename() == name


def test_a_path_given_as_a_string_works_too(tmp_path):
    file = tmp_path / "note.txt"
    file.write_bytes(b"x")
    _, part = parse_multipart(*_multipart_file_body(str(file)))
    assert part.get_payload(decode=True) == b"x"


# ----------------------------------------------------------------------------------------------
# upload_files_as_external_input
# ----------------------------------------------------------------------------------------------


def test_an_external_file_is_uploaded_with_the_run_and_module_handles(
    service, handle, module, tmp_path
):
    file = tmp_path / "note.txt"
    file.write_bytes(b"hello\n")
    result = upload_files_as_external_input(handle, module, {"my_file": str(file)})

    assert result is None
    ((name, body, content_type, query),) = service.calls
    assert name == "UploadFile"
    assert query == {
        "HandleId": HANDLE_ID,
        "Id": str(RUN_ID),
        "ModuleHandleId": "module4bd94be4-390d-499f-8553-f7daaf917e66",
        "ModuleInputHandleId": "input6",
    }
    assert all(
        isinstance(value, str) for value in query.values()
    )  # plain text, as the service reads them
    _, part = parse_multipart(body, content_type)
    assert part.get_payload(decode=True) == b"hello\n"


def test_the_file_is_found_by_the_name_of_the_input(service, handle, module, tmp_path):
    right, wrong = tmp_path / "right.txt", tmp_path / "wrong.txt"
    right.write_bytes(b"right")
    wrong.write_bytes(b"wrong")
    upload_files_as_external_input(
        handle, module, {"my_file": right, "something_else": wrong}
    )  # a Path works too
    _, part = parse_multipart(service.calls[0][1], service.calls[0][2])
    assert part.get_payload(decode=True) == b"right"


def test_a_service_fault_during_an_upload_is_not_swallowed(
    session, handle, module, tmp_path
):
    class Failing:
        def UploadFile(self, *args, **kwargs):
            raise ServiceFault("Parameter name: g", status_code=500)

    session.services["FileUploadService"] = Failing()
    file = tmp_path / "a.txt"
    file.write_bytes(b"x")
    with pytest.raises(ServiceFault, match="Parameter name: g"):
        upload_files_as_external_input(handle, module, {"my_file": str(file)})


# ----------------------------------------------------------------------------------------------
# upload_files_to_runs_dir
# ----------------------------------------------------------------------------------------------


def test_a_file_uploaded_to_the_runs_folder_comes_back_as_a_file_reference(
    service, handle, tmp_path
):
    file = tmp_path / "note.txt"
    file.write_bytes(b"hello\n")
    reference = upload_files_to_runs_dir(handle, file)

    assert (
        type(reference) is FileReference
        and reference.Uri == UPLOADED_URI
        and reference.LocalFile is None
    )
    ((name, body, content_type, query),) = service.calls
    assert name == "UploadFilesToRuns"
    assert query == {
        "HandleId": HANDLE_ID,
        "Id": str(RUN_ID),
    }  # no module handles for this one
    _, part = parse_multipart(body, content_type)
    assert part.get_payload(decode=True) == b"hello\n"


# ----------------------------------------------------------------------------------------------
# Through the real client and proxy, over a fake HTTP session
# ----------------------------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, content):
        self.status_code, self.content = 200, content


def record_requests(session, reply):
    sent = []

    def request(method, url, **kwargs):
        sent.append((method, url, kwargs))
        return FakeResponse(reply)

    session._client.session.request = request
    return sent


def test_the_external_upload_request_on_the_wire(session, handle, module, tmp_path):
    sent = record_requests(session, b'{"d":6}')
    file = tmp_path / "note.txt"
    file.write_bytes(b"hello\n")
    upload_files_as_external_input(handle, module, {"my_file": str(file)})

    ((method, url, kwargs),) = sent
    assert (method, url) == ("POST", URI + "Services/FileUploadService.svc/UploadFile")
    assert kwargs["headers"]["Content-Type"].startswith(
        "multipart/form-data; boundary="
    )
    assert kwargs["params"]["ModuleInputHandleId"] == "input6"
    assert isinstance(kwargs["data"], bytes)  # not text: the bytes are sent as they are
    _, part = parse_multipart(kwargs["data"], kwargs["headers"]["Content-Type"])
    assert part.get_payload(decode=True) == b"hello\n"


def test_the_runs_folder_request_on_the_wire_and_its_decoded_reply(
    session, handle, tmp_path
):
    sent = record_requests(session, REPLY_FILE_REFERENCES.encode("utf-8"))
    file = tmp_path / "note.txt"
    file.write_bytes(b"hello\n")
    reference = upload_files_to_runs_dir(handle, file)

    ((method, url, kwargs),) = sent
    assert (method, url) == (
        "POST",
        URI + "Services/FileUploadService.svc/UploadFilesToRuns",
    )
    assert kwargs["params"] == {"HandleId": HANDLE_ID, "Id": str(RUN_ID)}
    assert type(reference) is FileReference and reference.Uri == UPLOADED_URI


def test_both_functions_need_a_registered_session(handle, module, tmp_path):
    Session.clear_registration()
    file = tmp_path / "a.txt"
    file.write_bytes(b"x")
    with pytest.raises(SessionRequiredError):
        upload_files_to_runs_dir(handle, file)
    with pytest.raises(SessionRequiredError):
        upload_files_as_external_input(handle, module, {"my_file": str(file)})


# ----------------------------------------------------------------------------------------------
# File names in the multipart header
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "with space.txt",
        "semi;colon.txt",
        "it's.txt",
        "per%cent.txt",
        "equals=sign.txt",
        "comma,.txt",
        "multi.dot.name.tar.gz",
        "UPPER.TXT",
        "no_extension",
    ],
)
def test_a_file_name_with_punctuation_is_sent_unchanged(tmp_path, name):
    file = tmp_path / name
    file.write_bytes(b"x")
    _, part = parse_multipart(*_multipart_file_body(file))
    assert part.get_filename() == name


def test_only_the_file_name_is_sent_not_the_folder(tmp_path):
    folder = tmp_path / "a folder" / "inner"
    folder.mkdir(parents=True)
    file = folder / "note.txt"
    file.write_bytes(b"x")
    body, _ = _multipart_file_body(file)
    assert b'filename="note.txt"' in body and b"a folder" not in body


def test_pinned_a_non_ascii_file_name_is_written_as_raw_utf8_in_the_header(tmp_path):
    # Pinned, needs a decision: the header is encoded as UTF-8 as it is, not as filename*= (RFC 5987) or escapes. No
    # capture has a non-ASCII name, so what the server makes of it is not known from here.
    file = tmp_path / "café 中文.txt"
    file.write_bytes(b"x")
    body, _ = _multipart_file_body(file)
    header = body.split(b"\r\n\r\n", 1)[0].decode("utf-8")
    assert 'filename="café 中文.txt"' in header


def with_a_name_that_windows_cannot_make(monkeypatch, name):
    """Windows will not create a file called a"b.txt, so only the name is made up and the bytes are faked."""
    path = Path("some folder") / name
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"hello")
    return path


@pytest.mark.parametrize(
    "name",
    [
        'say "hi".txt',
        "a.txt\r\nX-Injected: yes\r\nX-Rest: ",
        "a\nb.txt",
        "a\rb.txt",
    ],
)
def test_a_file_name_with_a_double_quote_or_a_line_break_is_refused_before_anything_is_built(
    monkeypatch, name
):
    # The name goes into a quoted header value: a quote would end it early and a line break would start another header
    path = with_a_name_that_windows_cannot_make(monkeypatch, name)
    with pytest.raises(ValueError, match="can't be uploaded"):
        _multipart_file_body(path)


# ----------------------------------------------------------------------------------------------
# A file that cannot be read, and a reply with nothing in it
# ----------------------------------------------------------------------------------------------


def test_a_file_that_does_not_exist_is_a_file_not_found_error_and_nothing_is_sent(
    service, handle, module, tmp_path
):
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError):
        upload_files_to_runs_dir(handle, missing)
    with pytest.raises(FileNotFoundError):
        upload_files_as_external_input(handle, module, {"my_file": str(missing)})
    assert service.calls == []


def test_a_folder_instead_of_a_file_is_an_os_error_and_nothing_is_sent(
    service, handle, tmp_path
):
    with pytest.raises(
        OSError
    ):  # PermissionError on Windows, IsADirectoryError elsewhere
        upload_files_to_runs_dir(handle, tmp_path)
    assert service.calls == []


def test_pinned_an_empty_reply_from_the_runs_folder_upload_is_an_index_error(
    session, handle, tmp_path
):
    # Pinned, needs a decision: result[0] on an empty list, with no message saying that the server returned no reference
    class Empty:
        def UploadFilesToRuns(self, body, _content_type=None, _query=None):
            return []

    session.services["FileUploadService"] = Empty()
    file = tmp_path / "note.txt"
    file.write_bytes(b"x")
    with pytest.raises(IndexError):
        upload_files_to_runs_dir(handle, file)


def test_pinned_a_reply_with_several_references_gives_the_first(
    session, handle, tmp_path
):
    # Pinned, needs a decision: only one file is sent, so the server should answer with one reference
    class Two:
        def UploadFilesToRuns(self, body, _content_type=None, _query=None):
            return ["first", "second"]

    session.services["FileUploadService"] = Two()
    file = tmp_path / "note.txt"
    file.write_bytes(b"x")
    assert upload_files_to_runs_dir(handle, file) == "first"


# ----------------------------------------------------------------------------------------------
# upload_files_as_external_input, reached through DataFlowObject
# ----------------------------------------------------------------------------------------------

FILES = Path(__file__).resolve().parent.parent / "TestFiles"
FILE_INPUT_NAME = (
    "my external file input"  # the Name input of external_input_file.json's one module
)


def file_flow():
    return DataFlowObject(
        codec.decode(
            (FILES / "external_input_file.json").read_text(encoding="utf-8-sig")
        )
    )


def test_a_file_input_that_is_given_is_uploaded_with_its_modules_handles(
    service, handle, tmp_path
):
    file = tmp_path / "data.bin"
    file.write_bytes(b"\x00\x01\x02")
    file_flow()._post_context_setup_steps({FILE_INPUT_NAME: str(file)}, handle)

    ((name, body, content_type, query),) = service.calls
    assert name == "UploadFile"
    assert query == {
        "HandleId": HANDLE_ID,
        "Id": str(RUN_ID),
        "ModuleHandleId": "modulecc8dce2f-3ef1-494a-9856-d4aa938ee00d",
        "ModuleInputHandleId": "input9",
    }
    _, part = parse_multipart(body, content_type)
    assert part.get_payload(decode=True) == b"\x00\x01\x02"
    assert part.get_filename() == "data.bin"


def test_a_file_input_given_as_a_path_object_is_uploaded_too(service, handle, tmp_path):
    file = tmp_path / "data.bin"
    file.write_bytes(b"x")
    file_flow()._post_context_setup_steps({FILE_INPUT_NAME: file}, handle)
    assert [call[0] for call in service.calls] == ["UploadFile"]


@pytest.mark.parametrize(
    "external_inputs", [None, {}, {"another input": 1}], ids=["none", "empty", "other"]
)
def test_nothing_is_uploaded_when_the_file_input_is_not_among_the_inputs(
    service, handle, external_inputs
):
    file_flow()._post_context_setup_steps(external_inputs, handle)
    assert service.calls == []


def test_the_name_of_the_input_is_matched_exactly(service, handle, tmp_path):
    file = tmp_path / "data.bin"
    file.write_bytes(b"x")
    file_flow()._post_context_setup_steps(
        {FILE_INPUT_NAME.upper(): str(file), FILE_INPUT_NAME + " ": str(file)}, handle
    )
    assert service.calls == []


def test_a_file_input_whose_file_is_missing_fails_before_the_run_is_started(
    service, handle, tmp_path
):
    with pytest.raises(FileNotFoundError):
        file_flow()._post_context_setup_steps(
            {FILE_INPUT_NAME: str(tmp_path / "missing.bin")}, handle
        )
    assert service.calls == []


def test_pinned_none_for_a_file_input_is_a_type_error_about_a_path(service, handle):
    # Pinned, needs a decision: the message is pathlib's ("argument should be a str or an os.PathLike object"), not one
    # that names the input
    with pytest.raises(TypeError):
        file_flow()._post_context_setup_steps({FILE_INPUT_NAME: None}, handle)
    assert service.calls == []


def test_run_creates_the_context_then_uploads_then_runs_and_reads_the_run(
    session, tmp_path
):
    events = []
    file = tmp_path / "data.bin"
    file.write_bytes(b"x")

    class FakeApplicationService:
        def CreateExecutionContext(self, contract, options):
            events.append(
                (
                    "create",
                    [m["RequestingExecution"] for m in contract["Modules"]],
                    options["Debug"],
                )
            )
            return ExecutionHandle(HandleId=HANDLE_ID, Id=RUN_ID)

        def RunExecutionContext(self, handle):
            events.append(("run", handle.Id))

        def GetRun(self, run_id):
            events.append(("get", run_id))
            return codec.decode(json.dumps({"Handle": {"Id": run_id, "AppId": None}}))

    class RecordingUploads(FakeFileUploadService):
        def UploadFile(self, body, _content_type=None, _query=None):
            events.append(("upload", _query["Id"]))
            return super().UploadFile(body, _content_type, _query)

    session.services["ApplicationService"] = FakeApplicationService()
    session.services["FileUploadService"] = RecordingUploads()

    run = file_flow().run({FILE_INPUT_NAME: str(file)})

    assert events == [
        ("create", [True], False),
        ("upload", str(RUN_ID)),
        ("run", RUN_ID),
        ("get", RUN_ID),
    ]
    assert run.id == RUN_ID and run.app_id is None


class RecordingApplicationService:
    def __init__(self):
        self.events = []

    def CreateExecutionContext(self, contract, options):
        self.events.append("create")
        return ExecutionHandle(HandleId=HANDLE_ID, Id=RUN_ID)

    def RunExecutionContext(self, handle):
        self.events.append("run")


def test_a_missing_file_stops_run_before_the_context_is_made(session, tmp_path):
    app = RecordingApplicationService()
    uploads = FakeFileUploadService()
    session.services["ApplicationService"] = app
    session.services["FileUploadService"] = uploads
    flow = file_flow()
    for module in flow.modules:
        module.contract.RequestingExecution = False
    missing = tmp_path / "missing.bin"
    with pytest.raises(FileNotFoundError) as error:
        flow.run({FILE_INPUT_NAME: str(missing)})
    assert FILE_INPUT_NAME in str(error.value) and "missing.bin" in str(error.value)
    # nothing was sent to the server, and the flow was not marked as requesting execution
    assert app.events == [] and uploads.calls == []
    assert [m.contract.RequestingExecution for m in flow.modules] == [False]


def test_a_folder_given_for_a_file_input_stops_run_before_the_context_is_made(
    session, tmp_path
):
    app = RecordingApplicationService()
    session.services["ApplicationService"] = app
    session.services["FileUploadService"] = FakeFileUploadService()
    with pytest.raises(ValueError, match=f"'{FILE_INPUT_NAME}' takes a file"):
        file_flow().run({FILE_INPUT_NAME: str(tmp_path)})
    assert app.events == []


def test_a_file_input_that_is_not_given_is_not_checked_by_run(session):
    app = RecordingApplicationService()
    session.services["ApplicationService"] = app
    session.services["FileUploadService"] = FakeFileUploadService()
    session.services["ApplicationService"].GetRun = lambda run_id: codec.decode(
        json.dumps({"Handle": {"Id": run_id, "AppId": None}})
    )
    file_flow().run({"another input": 1})
    assert app.events == ["create", "run"]
