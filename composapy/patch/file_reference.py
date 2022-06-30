from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath

import json_fix  # used to patch json with fake magic method __json__
from six import string_types, integer_types
import papermill

from System import Uri
from System.IO import File, SeekOrigin
from CompAnalytics.Contracts import FileReference
from CompAnalytics.Core import ContractSerializer
from CompAnalytics.Utils import FileUtils, StandardPaths


from composapy.session import get_session
from composapy.utils import urljoin


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


# patching for papermill translators - defining custom parameter rendering logic for FileReference
# github docs : https://github.com/nteract/papermill/blob/main/papermill/translators.py
# @classmethod
def translate_file_ref(cls, val):
    return cls.translate_raw_str(
        f"ContractSerializer.Deserialize[FileReference]('{val}')"
    )


papermill.translators.PythonTranslator.translate_file_ref = translate_file_ref


# @classmethod
def translate(cls, val):
    """Translate each of the standard json/yaml types to appropriate objects."""

    if val is None:
        return cls.translate_none(val)
    elif isinstance(val, string_types):
        return cls.translate_str(val)
    # Needs to be before integer checks
    elif isinstance(val, bool):
        return cls.translate_bool(val)
    elif isinstance(val, integer_types):
        return cls.translate_int(val)
    elif isinstance(val, float):
        return cls.translate_float(val)
    elif isinstance(val, dict):
        return cls.translate_dict(val)
    elif isinstance(val, list):
        return cls.translate_list(val)
    elif isinstance(val, FileReference):
        return cls.translate_file_ref(ContractSerializer.Serialize(val))
    # Use this generic translation as a last resort
    return cls.translate_escaped_str(val)


papermill.translators.Translator.translate = translate


# patch FileReference with a utility function "to_file"
def _file_ref_to_file(self, save_dir: Path | str = None, file_name: str = None):
    """Downloads a run file by calling file_ref.to_file().

    Parameters:
    (Path|str) save_dir: the directory to save the downloaded file to
    (str) file_name:
        The name of the newly saved file (default is None). If None is provided,
        uses the original filename from URI.
    """

    session = get_session()
    file_ref_uri = str(self.Uri)

    # string magic to parse the useful bits out of uri
    file_ref_relative_uri = "/".join(list(filter(None, file_ref_uri.split("/")))[1:])

    if isinstance(save_dir, str):
        save_dir = Path(save_dir)
    if not save_dir:
        save_dir = Path.cwd()

    if not file_name:
        file_name = file_ref_uri[file_ref_uri.rindex("/") :].strip("/")

    virtual_path = urljoin(session.uri, file_ref_relative_uri)
    windows_path: PureWindowsPath = PureWindowsPath(save_dir.joinpath(file_name))

    Path.mkdir(save_dir, parents=True, exist_ok=True)
    file_path: Path = save_dir.joinpath(file_name)

    _input_stream = session.file_upload_service.StreamFile(virtual_path)
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


FileReference.to_file = _file_ref_to_file
