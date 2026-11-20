from __future__ import annotations

from composapy._wire.objects import ContractObject, register
from composapy.decorators import session_required
from composapy.session import get_session
from composapy.contracts.execution_handle import ExecutionHandle
from composapy.contracts import uri as _uri
from composapy.utils import _urljoin

import json
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit
import os


class FileReference(ContractObject):
    TYPE_NAME = "FileReference"

    def __init__(self, *args, **members):
        if (
            len(args) == 2
            and isinstance(args[1], str)
            and (args[0] is None or isinstance(args[0], str))
        ):
            local_file, serialized_uri = args
            super().__init__(
                [
                    ("__type", f"{self.TYPE_NAME}:#CompAnalytics.Contracts"),
                    ("Uri", json.loads(serialized_uri)),
                ]
            )  # json.loads handles the \/ escapes
            self._local_file = local_file
        else:
            super().__init__(*args, **members)
            self._local_file = None

    @property
    def Uri(self):
        """The URI, as the text the contract carries with the members of System.Uri (composapy.contracts.uri.Uri)."""
        value = self.get("Uri")
        return _uri.Uri(value) if isinstance(value, str) else value

    @property
    def LocalFile(self):
        return self._local_file

    def __deepcopy__(self, memo):
        return self

    def __reduce__(self):
        if "Uri" not in self:
            # Nothing to hand the two-argument form, and it would add a null Uri member the reference never had
            state = {"_local_file": self.LocalFile}
            state.update(self._result_id_state())
            return (self.__class__, (dict(self),), state)
        return (
            self.__class__,
            (self.LocalFile, json.dumps(self["Uri"])),
            self._result_id_state() or None,
        )

    def _result_id_state(self):
        # dataflow/models.py sets _contract__result_id as an attribute (not a member) so to_file can download the result;
        # carry it, or a pickled or shallow-copied reference could no longer be downloaded
        if "_contract__result_id" in self.__dict__:
            return {"_contract__result_id": self.__dict__["_contract__result_id"]}
        return {}

    @staticmethod
    def Create(local_file, uri, as_type=None):
        """A relative URI only, like the .NET FileReference.Create."""
        return _create(local_file, uri, allow_absolute_uri=False, as_type=as_type)

    @staticmethod
    def CreateWithAbsoluteUri(local_file, uri, as_type=None):
        """For a file stored remotely, or a local file's file:// URI (what file_ref() uses)."""
        return _create(local_file, uri, allow_absolute_uri=True, as_type=as_type)

    @session_required
    def to_file(self, save_dir: Path | str = None, file_name: str = None):
        """Downloads a run file by calling file_ref.to_file().

        Parameters:
        (Path|str) save_dir: the directory to save the downloaded file to
        (str) file_name:
            The name of the newly saved file (default is None). If None is provided,
            uses the original filename from URI.
        """
        file_upload_service = get_session().file_upload_service

        if hasattr(self, "_contract__result_id"):  # comes from dataflow api call
            input_stream = file_upload_service.StreamResultFile(
                self._contract__result_id
            )
        elif os.getenv("_execution_handle"):  # comes from notebook runner call
            input_stream = file_upload_service.StreamRunFile(
                ExecutionHandle(os.environ["_execution_handle"]), self["Uri"]
            )
        else:
            raise InvalidFileReference(
                "Can't download file if file reference was not created by a dataflow run."
            )

        session_uri = get_session().uri
        file_ref_uri = self["Uri"]

        if isinstance(save_dir, str):
            save_dir = Path(save_dir)
        if not save_dir:
            save_dir = Path.cwd()

        if not file_name:
            file_name = _file_name_from_uri(file_ref_uri)
            if not file_name:
                raise InvalidFileReference(
                    f"Can't tell what to call the file from the URI '{file_ref_uri}'. Pass file_name."
                )

        Path.mkdir(save_dir, parents=True, exist_ok=True)
        file_path: Path = save_dir.joinpath(file_name)

        file_path.write_bytes(input_stream)

        file_ref_relative_uri = "/".join(
            list(filter(None, file_ref_uri.split("/")))[1:]
        )
        virtual_path = _urljoin(session_uri, file_ref_relative_uri)
        components = urlsplit(virtual_path)
        site_relative = components.path + (
            f"?{components.query}" if components.query else ""
        )
        return FileReference.Create(
            str(file_path), site_relative, as_type=FileReference
        )


class CsvFileReference(FileReference):
    TYPE_NAME = "CsvFileReference"


class ImageReference(FileReference):
    TYPE_NAME = "ImageReference"


class KmlReference(FileReference):
    TYPE_NAME = "KmlReference"


class KmzReference(FileReference):
    TYPE_NAME = "KmzReference"


class StlReference(FileReference):
    TYPE_NAME = "StlReference"


class Mp3Reference(FileReference):
    TYPE_NAME = "Mp3Reference"


class WavReference(FileReference):
    TYPE_NAME = "WavReference"


class VideoReference(FileReference):
    TYPE_NAME = "VideoReference"


class AudioReference(FileReference):
    TYPE_NAME = "AudioReference"


class FileReferencePickleBehavior(FileReference):
    pass


class InvalidFileReference(Exception):
    pass


def _file_name_from_uri(uri):
    # The last part of the URI's path, without a query string or trailing slashes ('' if it has none)
    return urlsplit(uri).path.rstrip("/").rpartition("/")[2]


_BY_EXTENSION = {
    ".csv": CsvFileReference,
    ".kml": KmlReference,
    ".kmz": KmzReference,
    ".jpg": ImageReference,
    ".jpeg": ImageReference,
    ".png": ImageReference,
    ".gif": ImageReference,
    ".stl": StlReference,
    ".mp3": Mp3Reference,
    ".wav": WavReference,
    ".mp4": VideoReference,
    ".webm": VideoReference,
}


def _create(local_file, uri, allow_absolute_uri, as_type):
    if uri is None:
        raise ValueError("A uri is needed to create a FileReference, but it is None.")
    path = PureWindowsPath(local_file)
    if not (path.root or path.drive):  # .NET Path.IsPathRooted
        raise ValueError(
            "Can't create a FileReference using a relative path. Please provide an absolute path."
        )
    text = (
        uri.OriginalString if isinstance(uri, _uri.Uri) else str(uri)
    )  # str(Uri) is the unescaped form
    if not allow_absolute_uri and urlsplit(text).scheme:  # Uri.IsAbsoluteUri
        raise ValueError(
            "Can't create a FileReference using an absolute URI. Please provide a relative URI."
        )
    kind = as_type or _BY_EXTENSION.get(path.suffix.lower(), FileReference)
    reference = kind(
        [("__type", f"{kind.TYPE_NAME}:#CompAnalytics.Contracts"), ("Uri", text)]
    )
    reference._local_file = local_file
    return reference


for kind in (
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
):
    register(f"{kind.TYPE_NAME}:#CompAnalytics.Contracts", kind)
