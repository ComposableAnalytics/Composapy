from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath

import json_fix  # used to patch json with fake magic method __json__

from System import Uri
from System.IO import File, SeekOrigin
from CompAnalytics.Contracts import FileReference
from CompAnalytics.Core import ContractSerializer
from CompAnalytics.Utils import FileUtils, StandardPaths

from composapy.decorators import session_required
from composapy.session import get_session
from composapy.utils import _urljoin


# patching json package using json-fix
# json-fix : https://pypi.org/project/json-fix/
def _json(self):
    return json.loads(ContractSerializer.Serialize(self))


FileReference.__json__ = _json

# patching copy.deepycopy
# python docs : https://docs.python.org/3/library/copy.html#copy.deepcopy
def deep_copy(self, memo):
    """Only use for things which don't actually need to be copied."""
    return self


FileReference.__deepcopy__ = deep_copy


# monkey patching FileReference for pickling
# python docs : https://docs.python.org/3/library/pickle.html#object.__reduce_ex__
# composable docs : https://dev.composable.ai/api/CompAnalytics.Contracts.FileReference.html
def reduce_ex(self, protocol):
    """Called when using pickle.dumps(file_ref_to_pickle), serializes the Uri with Composable
    serializer."""
    return (self.__class__, (self.LocalFile, ContractSerializer.Serialize(self.Uri)))


FileReference.__reduce_ex__ = reduce_ex


class FileReferencePickleBehavior(FileReference):
    """This is used for changing the behavior of pickling/depickling for FileReferences."""

    def __new__(self, *args, **kwargs):
        """Called when using pickle.loads(picked_file_ref), deserializes the Uri with Composable
        serializer."""
        return FileReference.Create(
            args[0], ContractSerializer.Deserialize[Uri](args[1])
        )


# patch FileReference with a utility function "to_file"
@session_required
def to_file(self, save_dir: Path | str = None, file_name: str = None):
    """Downloads a run file by calling file_ref.to_file().

    Parameters:
    (Path|str) save_dir: the directory to save the downloaded file to
    (str) file_name:
        The name of the newly saved file (default is None). If None is provided,
        uses the original filename from URI.
    """
    session_uri = get_session().uri
    file_upload_service = get_session().file_upload_service
    file_ref_uri = str(self.Uri)

    # string magic to parse the useful bits out of uri
    file_ref_relative_uri = "/".join(list(filter(None, file_ref_uri.split("/")))[1:])

    if isinstance(save_dir, str):
        save_dir = Path(save_dir)
    if not save_dir:
        save_dir = Path.cwd()

    if not file_name:
        file_name = file_ref_uri[file_ref_uri.rindex("/") :].strip("/")

    virtual_path = _urljoin(session_uri, file_ref_relative_uri)
    windows_path: PureWindowsPath = PureWindowsPath(save_dir.joinpath(file_name))

    Path.mkdir(save_dir, parents=True, exist_ok=True)
    file_path: Path = save_dir.joinpath(file_name)

    _input_stream = file_upload_service.StreamFile(virtual_path)
    input_stream = FileUtils.GetEntireFileStream(_input_stream)  # fix seek issues

    output_stream = File.Create(str(windows_path))

    input_stream.Seek(0, SeekOrigin.Begin)
    input_stream.CopyTo(output_stream)

    output_stream.Close()
    input_stream.Close()

    return FileReference.Create[FileReference](
        str(file_path),
        StandardPaths.CreateSiteRelativePath(Uri(virtual_path)),
    )


FileReference.to_file = to_file
