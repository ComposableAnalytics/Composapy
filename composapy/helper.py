from __future__ import annotations
from pathlib import Path

from System import Uri
from CompAnalytics.Contracts import FileReference


def file_ref(path_like: str | Path) -> FileReference:
    if isinstance(path_like, Path):
        path_like = str(path_like)

    uri = Uri(path_like)
    file_ref = FileReference.CreateWithAbsoluteUri(uri.LocalPath, uri)
    return file_ref
