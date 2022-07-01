from __future__ import annotations
from pathlib import Path, PureWindowsPath

from System import Uri
from CompAnalytics.Contracts import FileReference


def file_ref(path: str | Path) -> FileReference:
    if isinstance(path, str):
        path = Path(path)

    uri = Uri(str(path.absolute()))
    file_ref = FileReference.CreateWithAbsoluteUri(uri.LocalPath, uri)
    return file_ref
