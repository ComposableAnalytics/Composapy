"""What a caller can do with FileReference.Uri: the members of System.Uri that a script might reach for."""

import composapy  # the compatibility namespace is installed by importing composapy
from CompAnalytics.Contracts import FileReference

URIS = {
    "windows_file": "file:///C:/data/folder/a.txt",
    "windows_file_escaped": "file:///C:/data/my%20folder/a%20b.txt",
    "unc_file": "file://server/share/dir/a.txt",
    "https_full": "https://Example.test:8443/a/b%20c.txt?x=1&y=2#frag",
    "http_default_port": "http://example.test/a/b.txt",
    "site_relative": "/CompApp/runs/70850f2b/5f051543/note.txt",
}


def members(uri):
    return {
        "OriginalString": lambda: uri.OriginalString,
        "AbsoluteUri": lambda: uri.AbsoluteUri,
        "AbsolutePath": lambda: uri.AbsolutePath,
        "LocalPath": lambda: uri.LocalPath,
        "Scheme": lambda: uri.Scheme,
        "Host": lambda: uri.Host,
        "Port": lambda: uri.Port,
        "IsFile": lambda: uri.IsFile,
        "IsUnc": lambda: uri.IsUnc,
        "IsAbsoluteUri": lambda: uri.IsAbsoluteUri,
        "Query": lambda: uri.Query,
        "Fragment": lambda: uri.Fragment,
        "PathAndQuery": lambda: uri.PathAndQuery,
        "Segments": lambda: list(uri.Segments),
        "ToString": lambda: uri.ToString(),
        "str": lambda: str(uri),
        "equals_text": lambda: uri == URI_TEXT[0],
    }


for label, text in URIS.items():
    URI_TEXT = [text]
    if text.startswith("/"):
        ref = FileReference.Create("C:/local/note.txt", uri_arg(text))
    else:
        ref = FileReference.CreateWithAbsoluteUri("C:/local/note.txt", uri_arg(text))
    uri = ref.Uri
    for member, read in members(uri).items():
        attempt(f"{label}.{member}", read)
