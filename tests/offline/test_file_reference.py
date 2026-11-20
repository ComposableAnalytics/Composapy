"""Offline tests for the typed FileReference contract (composapy.contracts): the factory, the subclasses,
pickling, and to_file. A fake FileUploadService stands in for the real one.
"""

import copy
import json
import pickle
from pathlib import Path

import pytest

from composapy._wire import codec
from composapy.auth import AuthMode
from composapy.contracts.execution_handle import ExecutionHandle
from composapy.contracts.file_reference import (
    AudioReference,
    CsvFileReference,
    FileReference,
    FileReferencePickleBehavior,
    ImageReference,
    InvalidFileReference,
    KmlReference,
    KmzReference,
    Mp3Reference,
    StlReference,
    VideoReference,
    WavReference,
)
from composapy.decorators import SessionRequiredError
from composapy.session import Session

TESTS_DIR = Path(__file__).resolve().parent.parent
BASELINE_DIR = TESTS_DIR / "baseline" / "pickles"
MANIFEST = json.loads((BASELINE_DIR / "manifest.json").read_text(encoding="utf-8"))
BASELINE = MANIFEST["file_reference.pkl"]

URI = "http://example.test/CompApp/"
RUN_URI = "/CompApp/runs/70850f2b-e3a3-48f8-9c44-68c7ad009375/5f051543-bf10-482a-8be1-7b11e87d2009/note.txt"
HANDLE_JSON = json.dumps(
    {
        "__type": "ExecutionHandle:#CompAnalytics.Contracts",
        "AppId": 685697,
        "HandleId": "70850f2b-e3a3-48f8-9c44-68c7ad009375",
        "Id": 685736,
    }
)


class FakeFileUploadService:
    def __init__(self, content=b"hello\n"):
        self.content, self.calls = content, []

    def StreamResultFile(self, resource_id):
        self.calls.append(("StreamResultFile", resource_id))
        return self.content

    def StreamRunFile(self, handle, uri):
        self.calls.append(("StreamRunFile", handle, uri))
        return self.content


@pytest.fixture
def service():
    session = Session(uri=URI, auth_mode=AuthMode.TOKEN, credentials="token-for-tests")
    session.register()
    fake = FakeFileUploadService()
    session.services["FileUploadService"] = fake
    yield fake
    Session.clear_registration()


def server_reference(uri=RUN_URI, type_name="FileReference"):
    return codec.decode(
        json.dumps({"__type": f"{type_name}:#CompAnalytics.Contracts", "Uri": uri})
    )


# ----------------------------------------------------------------------------------------------
# The factory
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, expected",
    [
        (r"C:\data\a.csv", CsvFileReference),
        (r"C:\data\A.CSV", CsvFileReference),
        (r"C:\data\a.kml", KmlReference),
        (r"C:\data\a.kmz", KmzReference),
        (r"C:\data\a.jpg", ImageReference),
        (r"C:\data\a.jpeg", ImageReference),
        (r"C:\data\a.png", ImageReference),
        (r"C:\data\a.gif", ImageReference),
        (r"C:\data\a.stl", StlReference),
        (r"C:\data\a.mp3", Mp3Reference),
        (r"C:\data\a.wav", WavReference),
        (r"C:\data\a.mp4", VideoReference),
        (r"C:\data\a.webm", VideoReference),
        (r"C:\data\a.txt", FileReference),
        (r"C:\data\a.tif", FileReference),
        (r"C:\data\noextension", FileReference),
    ],
)
def test_the_factory_picks_the_subclass_from_the_extension(path, expected):
    assert type(FileReference.Create(path, "/CompApp/runs/x/a")) is expected


def test_as_type_overrides_the_extension():
    reference = FileReference.Create(
        r"C:\data\a.csv", "/CompApp/runs/x/a.csv", as_type=FileReference
    )
    assert type(reference) is FileReference


def test_a_created_reference_has_its_members_in_order_and_a_local_file():
    reference = FileReference.Create(r"C:\data\a.csv", "/CompApp/runs/x/a.csv")
    assert list(reference) == ["__type", "Uri"]
    assert reference.type_name == "CsvFileReference:#CompAnalytics.Contracts"
    assert (
        reference.Uri == "/CompApp/runs/x/a.csv"
        and reference.LocalFile == r"C:\data\a.csv"
    )
    assert json.loads(codec.encode(reference)) == {
        "__type": "CsvFileReference:#CompAnalytics.Contracts",
        "Uri": "/CompApp/runs/x/a.csv",
    }  # LocalFile is not sent over the wire


@pytest.mark.parametrize(
    "path", [r"C:\data\a.txt", "C:/data/a.txt", r"\\server\share\a.txt", "/data/a.txt"]
)
def test_a_rooted_path_is_accepted(path):
    assert FileReference.Create(path, "/CompApp/runs/x/a.txt").LocalFile == path


@pytest.mark.parametrize("path", ["a.txt", r"data\a.txt", "data/a.txt"])
def test_a_relative_path_is_rejected_with_the_dotnet_message(path):
    with pytest.raises(
        ValueError,
        match="Can't create a FileReference using a relative path. Please provide an absolute path.",
    ):
        FileReference.Create(path, "/CompApp/runs/x/a.txt")


def test_an_absolute_uri_is_rejected_unless_asked_for():
    uri = "file:///C:/data/a.txt"
    with pytest.raises(
        ValueError,
        match="Can't create a FileReference using an absolute URI. Please provide a relative URI.",
    ):
        FileReference.Create(r"C:\data\a.txt", uri)
    assert FileReference.CreateWithAbsoluteUri(r"C:\data\a.txt", uri).Uri == uri


# ----------------------------------------------------------------------------------------------
# Decoding and the contract
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [
        FileReference,
        CsvFileReference,
        ImageReference,
        KmlReference,
        KmzReference,
        StlReference,
        Mp3Reference,
        WavReference,
        VideoReference,
        AudioReference,
    ],
)
def test_the_server_json_decodes_to_each_class(kind):
    reference = server_reference(type_name=kind.TYPE_NAME)
    assert type(reference) is kind
    assert reference.Uri == RUN_URI and reference.LocalFile is None


def test_a_decoded_reference_writes_back_the_same_json():
    text = json.dumps(
        {"__type": "FileReference:#CompAnalytics.Contracts", "Uri": RUN_URI}
    )
    assert codec.encode(codec.decode(text)) == text


def test_deepcopy_returns_the_same_object():
    reference = server_reference()
    assert copy.deepcopy(reference) is reference


def test_a_result_id_set_on_a_reference_is_not_a_member_and_is_not_sent():
    reference = server_reference()
    setattr(reference, "_contract__result_id", 7)  # what dataflow/models.py does
    assert reference._contract__result_id == 7 and hasattr(
        reference, "_contract__result_id"
    )
    assert list(reference) == ["__type", "Uri"]
    assert "_contract__result_id" not in codec.encode(reference)


def test_a_reference_without_a_result_id_does_not_claim_to_have_one():
    assert not hasattr(server_reference(), "_contract__result_id")


# ----------------------------------------------------------------------------------------------
# Pickling
# ----------------------------------------------------------------------------------------------


def test_a_local_reference_round_trips_through_a_pickle():
    reference = FileReference.CreateWithAbsoluteUri(
        r"C:\data\a.csv", "file:///C:/data/a.csv"
    )
    loaded = pickle.loads(pickle.dumps(reference))
    assert type(loaded) is CsvFileReference
    assert (
        loaded == reference
        and loaded.LocalFile == r"C:\data\a.csv"
        and loaded.Uri == "file:///C:/data/a.csv"
    )


def test_a_reference_from_the_server_round_trips_through_a_pickle():
    reference = server_reference()  # no local file
    loaded = pickle.loads(pickle.dumps(reference))
    assert (
        type(loaded) is FileReference
        and loaded == reference
        and loaded.LocalFile is None
    )


def test_the_pickle_behavior_class_can_be_assigned_and_pickled():
    reference = FileReference.Create(r"C:\data\a.txt", "/CompApp/runs/x/a.txt")
    reference.__class__ = FileReferencePickleBehavior  # what the DataLab wrappers do
    loaded = pickle.loads(pickle.dumps(reference))
    assert (
        isinstance(loaded, FileReference)
        and loaded == reference
        and loaded.LocalFile == r"C:\data\a.txt"
    )


def test_a_pickle_written_by_the_baseline_behavior_class_loads_including_its_absolute_uri():
    # 0.13.3 could not load this: its factory rejected the absolute URI that file_ref() produces (Appendix A.8)
    loaded = pickle.loads((BASELINE_DIR / "file_reference_behavior.pkl").read_bytes())
    assert isinstance(loaded, FileReference)
    assert json.loads(codec.encode(loaded)) == BASELINE["json"]
    assert loaded.Uri.startswith("file:///")
    assert loaded.LocalFile.endswith("create_file_ref_target.txt")


def test_a_pickle_written_by_the_baseline_plain_class_loads():
    loaded = pickle.loads((BASELINE_DIR / "file_reference.pkl").read_bytes())
    assert isinstance(loaded, FileReference)
    assert json.loads(codec.encode(loaded)) == BASELINE["json"]


# ----------------------------------------------------------------------------------------------
# to_file
# ----------------------------------------------------------------------------------------------


def downloaded_reference(result_id=685721):
    reference = server_reference()
    setattr(reference, "_contract__result_id", result_id)
    return reference


def test_to_file_downloads_a_dataflow_result_by_its_result_id(service, tmp_path):
    saved = downloaded_reference().to_file(save_dir=tmp_path)
    assert service.calls == [("StreamResultFile", 685721)]
    assert (
        tmp_path / "note.txt"
    ).read_bytes() == b"hello\n"  # named from the end of the URI
    assert type(saved) is FileReference
    assert saved.LocalFile == str(tmp_path / "note.txt")
    assert saved.Uri == RUN_URI  # site-relative, as the server gave it


def test_to_file_takes_a_folder_given_as_a_string_and_a_file_name(service, tmp_path):
    saved = downloaded_reference().to_file(
        save_dir=str(tmp_path / "new" / "sub"), file_name="copy.txt"
    )
    assert (tmp_path / "new" / "sub" / "copy.txt").read_bytes() == b"hello\n"
    assert saved.LocalFile == str(tmp_path / "new" / "sub" / "copy.txt")


def test_to_file_defaults_to_the_current_folder(service, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    downloaded_reference().to_file()
    assert (tmp_path / "note.txt").read_bytes() == b"hello\n"


def test_to_file_returns_a_plain_reference_even_for_a_csv(service, tmp_path):
    reference = server_reference(
        uri=RUN_URI.replace("note.txt", "data.csv"), type_name="CsvFileReference"
    )
    setattr(reference, "_contract__result_id", 1)
    assert (
        type(reference.to_file(save_dir=tmp_path)) is FileReference
    )  # the old Create[FileReference] did the same


def test_to_file_inside_a_run_uses_the_execution_handle_and_the_uri(
    service, tmp_path, monkeypatch
):
    monkeypatch.setenv("_execution_handle", HANDLE_JSON)
    server_reference().to_file(save_dir=tmp_path)
    name, handle, uri = service.calls[0]
    assert name == "StreamRunFile" and uri == RUN_URI
    assert (
        type(handle) is ExecutionHandle
        and handle.HandleId == "70850f2b-e3a3-48f8-9c44-68c7ad009375"
    )
    assert (tmp_path / "note.txt").read_bytes() == b"hello\n"


def test_to_file_needs_a_result_id_or_an_execution_handle(
    service, tmp_path, monkeypatch
):
    monkeypatch.delenv("_execution_handle", raising=False)
    with pytest.raises(
        InvalidFileReference,
        match="Can't download file if file reference was not created by a dataflow run",
    ):
        server_reference().to_file(save_dir=tmp_path)
    assert service.calls == []


@pytest.mark.parametrize(
    "uri, name",
    [
        (RUN_URI, "note.txt"),
        ("note.txt", "note.txt"),  # no slash at all
        ("/note.txt", "note.txt"),
        (RUN_URI + "/", "note.txt"),  # a trailing slash
        (
            RUN_URI + "?version=2&x=1",
            "note.txt",
        ),  # a query string is not part of the name
        ("/CompApp/runs/x/my%20file.txt", "my%20file.txt"),  # left as the URI wrote it
    ],
)
def test_to_file_names_the_file_from_the_end_of_the_uri_path(
    service, tmp_path, uri, name
):
    reference = server_reference(uri=uri)
    setattr(reference, "_contract__result_id", 1)

    reference.to_file(save_dir=tmp_path)

    assert (tmp_path / name).read_bytes() == b"hello\n"


@pytest.mark.parametrize("uri", ["", "/", "http://host", "http://host/"])
def test_to_file_asks_for_a_name_when_the_uri_has_none(service, tmp_path, uri):
    reference = server_reference(uri=uri)
    setattr(reference, "_contract__result_id", 1)

    with pytest.raises(InvalidFileReference, match="file_name"):
        reference.to_file(save_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []  # nothing was written under a made-up name

    reference.to_file(save_dir=tmp_path, file_name="given.txt")
    assert (tmp_path / "given.txt").read_bytes() == b"hello\n"


# ----------------------------------------------------------------------------------------------
# The constructor the pickle uses: FileReference(local_file, serialized_uri)
# ----------------------------------------------------------------------------------------------


def test_the_two_argument_constructor_takes_a_local_file_and_the_uri_as_json():
    reference = FileReference(r"C:\data\a.txt", json.dumps(RUN_URI))
    assert list(reference) == ["__type", "Uri"]
    assert reference.type_name == "FileReference:#CompAnalytics.Contracts"
    assert reference.Uri == RUN_URI and reference.LocalFile == r"C:\data\a.txt"


def test_the_two_argument_constructor_accepts_no_local_file():
    reference = FileReference(None, json.dumps(RUN_URI))
    assert reference.LocalFile is None and reference.Uri == RUN_URI


def test_the_serialized_uri_may_use_the_dotnet_escaped_slashes():
    reference = FileReference(None, '"\\/CompApp\\/runs\\/x\\/a.txt"')
    assert reference["Uri"] == "/CompApp/runs/x/a.txt"


@pytest.mark.parametrize("serialized", ["", "not json", "{", "/CompApp/runs/x"])
def test_the_two_argument_constructor_refuses_a_uri_that_is_not_json(serialized):
    with pytest.raises(ValueError):  # json.JSONDecodeError
        FileReference(r"C:\data\a.txt", serialized)


def test_a_serialized_null_uri_gives_a_reference_whose_uri_is_none():
    reference = FileReference(r"C:\data\a.txt", "null")
    assert reference["Uri"] is None and reference.Uri is None
    loaded = pickle.loads(pickle.dumps(reference))
    assert loaded.Uri is None and loaded.LocalFile == r"C:\data\a.txt"


def test_pinned_a_first_argument_that_is_not_text_falls_through_to_the_dict_constructor():
    # Needs a decision: with two arguments and a local file that is neither None nor text, dict() refuses with its own message
    with pytest.raises(TypeError, match="at most 1 argument"):
        FileReference(5, json.dumps(RUN_URI))


def test_keyword_members_make_a_reference_with_no_type_and_no_local_file():
    reference = FileReference(Uri=RUN_URI)
    assert dict(reference) == {"Uri": RUN_URI}
    assert reference.LocalFile is None and reference.Uri == RUN_URI


def test_a_dict_given_to_the_constructor_is_the_members_and_there_is_no_local_file():
    reference = FileReference(
        {"__type": "FileReference:#CompAnalytics.Contracts", "Uri": RUN_URI}
    )
    assert reference.Uri == RUN_URI and reference.LocalFile is None


@pytest.mark.parametrize("create", ["Create", "CreateWithAbsoluteUri"])
def test_create_with_a_uri_of_none_is_refused(create):
    # .NET's FileReference.Create(path, null) throws; storing str(None) as the URI would give a reference to "None"
    with pytest.raises(ValueError, match="uri is needed"):
        getattr(FileReference, create)(r"C:\data\a.txt", None)


# ----------------------------------------------------------------------------------------------
# Copying and pickling a reference that has a local file
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("protocol", range(0, pickle.HIGHEST_PROTOCOL + 1))
def test_a_reference_with_a_local_file_round_trips_through_every_pickle_protocol(
    protocol,
):
    reference = FileReference.Create(r"C:\data\a.csv", "/CompApp/runs/x/a.csv")
    loaded = pickle.loads(pickle.dumps(reference, protocol=protocol))
    assert type(loaded) is CsvFileReference and loaded == reference
    assert (
        loaded.LocalFile == r"C:\data\a.csv"
        and loaded["Uri"] == "/CompApp/runs/x/a.csv"
    )


def test_a_local_file_that_is_not_ascii_survives_a_pickle():
    path = "C:\\data\\caf\u00e9 \u4e2d.txt"
    loaded = pickle.loads(pickle.dumps(FileReference.Create(path, "/CompApp/runs/x/a")))
    assert loaded.LocalFile == path


def test_a_uri_that_was_assigned_after_creation_is_what_is_pickled():
    reference = FileReference.Create(r"C:\data\a.txt", "/CompApp/runs/x/a.txt")
    reference.Uri = "/CompApp/runs/y/b.txt"
    loaded = pickle.loads(pickle.dumps(reference))
    assert loaded["Uri"] == "/CompApp/runs/y/b.txt"


def test_a_shallow_copy_is_a_new_reference_with_the_same_local_file():
    reference = FileReference.Create(r"C:\data\a.csv", "/CompApp/runs/x/a.csv")
    shallow = copy.copy(reference)
    assert shallow is not reference and shallow == reference
    assert type(shallow) is CsvFileReference and shallow.LocalFile == r"C:\data\a.csv"


def test_a_deep_copy_is_the_same_reference_with_its_local_file():
    reference = FileReference.Create(r"C:\data\a.csv", "/CompApp/runs/x/a.csv")
    deep = copy.deepcopy(reference)
    assert deep is reference and deep.LocalFile == r"C:\data\a.csv"
    inside = copy.deepcopy({"files": [reference]})
    assert inside["files"][0] is reference


def test_a_reference_in_a_list_pickles_with_its_local_file():
    refs = [
        FileReference.Create(r"C:\data\a.csv", "/CompApp/runs/x/a.csv"),
        server_reference(),
    ]
    loaded = pickle.loads(pickle.dumps(refs))
    assert [type(r) for r in loaded] == [CsvFileReference, FileReference]
    assert [r.LocalFile for r in loaded] == [r"C:\data\a.csv", None]


@pytest.mark.parametrize("protocol", range(0, pickle.HIGHEST_PROTOCOL + 1))
def test_the_result_id_is_kept_by_a_pickle_so_to_file_can_download_it_again(
    protocol, service, tmp_path, monkeypatch
):
    monkeypatch.delenv("_execution_handle", raising=False)
    reference = downloaded_reference()
    loaded = pickle.loads(pickle.dumps(reference, protocol=protocol))
    assert loaded._contract__result_id == 685721
    assert "_contract__result_id" not in loaded  # still an attribute and not a member
    loaded.to_file(save_dir=tmp_path)
    assert service.calls == [("StreamResultFile", 685721)]


def test_a_shallow_copy_keeps_the_result_id_too(service, tmp_path, monkeypatch):
    monkeypatch.delenv("_execution_handle", raising=False)
    shallow = copy.copy(downloaded_reference())
    assert shallow._contract__result_id == 685721
    shallow.to_file(save_dir=tmp_path)
    assert service.calls == [("StreamResultFile", 685721)]


def test_the_result_id_is_kept_by_a_pickle_and_a_shallow_copy_of_a_reference_with_a_local_file():
    reference = FileReference.Create(r"C:\data\a.csv", "/CompApp/runs/x/a.csv")
    setattr(reference, "_contract__result_id", 12)
    for other in (pickle.loads(pickle.dumps(reference)), copy.copy(reference)):
        assert other._contract__result_id == 12
        assert other.LocalFile == r"C:\data\a.csv" and other == reference


def test_the_result_id_is_kept_by_a_pickle_and_a_shallow_copy_of_a_reference_with_no_uri():
    reference = FileReference()
    setattr(reference, "_contract__result_id", 12)
    for other in (pickle.loads(pickle.dumps(reference)), copy.copy(reference)):
        assert other._contract__result_id == 12
        assert other == {} and "Uri" not in other


def test_a_reference_without_a_result_id_has_none_after_a_pickle_or_a_copy():
    reference = FileReference.Create(r"C:\data\a.csv", "/CompApp/runs/x/a.csv")
    for other in (pickle.loads(pickle.dumps(reference)), copy.copy(reference)):
        assert not hasattr(other, "_contract__result_id")


def test_a_reference_with_no_uri_member_can_be_pickled():
    # FileReference() and a decoded {"__type": "FileReference:#CompAnalytics.Contracts"} both have no Uri member
    reference = FileReference()
    assert pickle.loads(pickle.dumps(reference)) == reference


# ----------------------------------------------------------------------------------------------
# to_file with no session
# ----------------------------------------------------------------------------------------------


def test_to_file_needs_a_registered_session(tmp_path):
    reference = downloaded_reference()  # no session fixture: none is registered
    with pytest.raises(
        SessionRequiredError, match="requires an active, registered session"
    ):
        reference.to_file(save_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_to_file_checks_the_session_before_it_checks_where_the_reference_came_from(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("_execution_handle", raising=False)
    with pytest.raises(SessionRequiredError):
        server_reference().to_file(
            save_dir=tmp_path
        )  # would be InvalidFileReference with a session


def test_to_file_after_the_session_is_cleared_needs_a_session_again(service, tmp_path):
    reference = downloaded_reference()
    reference.to_file(save_dir=tmp_path)
    Session.clear_registration()
    with pytest.raises(SessionRequiredError):
        reference.to_file(save_dir=tmp_path, file_name="again.txt")
    assert not (tmp_path / "again.txt").exists()
