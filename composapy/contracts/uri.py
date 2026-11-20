import re
from urllib.parse import quote, unquote

_PARSE = re.compile(
    r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*):(?://(?P<authority>[^/?#]*))?(?P<path>[^?#]*)(?P<query>\?[^#]*)?(?P<fragment>#.*)?$"
)
_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_IMPLICIT_UNC = re.compile(r"^\\\\(?P<host>[^\\/]+)(?P<path>.*)$")
_DEFAULT_PORTS = {"http": 80, "https": 443, "ftp": 21, "ws": 80, "wss": 443}
_KEEP_ESCAPED = ("%25", "%2F", "%3F", "%23")
_RELATIVE = "This operation is not supported for a relative URI."
# Schemes written scheme://..., whatever the text after them: System.Uri adds the slashes to these
_WITH_SLASHES = frozenset(_DEFAULT_PORTS) | {"file"}


class RelativeUriError(ValueError):
    """Raised by a Uri member that a relative URI does not support, as System.Uri raises InvalidOperationException."""


def _unescape(text):
    """Unescape what System.Uri.ToString does: everything except the escapes that would change the URI's meaning."""

    def decode_run(match):
        out, pending = [], []
        for token in re.findall(r"%[0-9A-Fa-f]{2}", match.group(0)):
            if token.upper() in _KEEP_ESCAPED:
                if pending:
                    out.append(unquote("".join(pending)))
                    pending = []
                out.append(token)
            else:
                pending.append(
                    token
                )  # consecutive escapes decode together: %C3%A9 is one letter
        if pending:
            out.append(unquote("".join(pending)))
        return "".join(out)

    return re.sub(r"(?:%[0-9A-Fa-f]{2})+", decode_run, text)


def _escape(text):
    return quote(text, safe="%:/?#[]@!$&'()*+,;=~-._")


def _resolve_dots(path):
    """Remove the . and .. segments of an absolute path, as System.Uri does: /a/./b/../c is /a/c."""
    if not path.startswith("/") or "." not in path:
        return path
    kept = []
    segments = path.split("/")[1:]
    for position, segment in enumerate(segments):
        last = position == len(segments) - 1
        if segment in (".", ".."):
            if segment == ".." and kept:
                kept.pop()
            if last:
                kept.append("")  # a path that ends in a dot segment ends in a slash
        else:
            kept.append(segment)
    return "/" + "/".join(kept)


def _finish(parts):
    if parts["has_authority"] or parts["scheme"] == "file":
        if parts["authority"] and parts["path"] == "":
            parts["path"] = "/"  # a host with no path has the path /
        parts["path"] = _resolve_dots(parts["path"])
    return parts


class Uri(str):
    """The value of FileReference.Uri: the text the contract carries, with the members of System.Uri that scripts use."""

    __slots__ = ()

    def __reduce__(self):
        # The default for protocols 0 and 1 stores str(self), which is ToString and unescapes the text
        return (Uri, (self.OriginalString,))

    def _absolute(self):
        text = str(self.OriginalString)
        if _DRIVE_PATH.match(text):  # a Windows path is an implicit file URI
            return _finish(
                {
                    "scheme": "file",
                    "authority": "",
                    "path": "/" + text.replace("\\", "/"),
                    "query": "",
                    "fragment": "",
                    "has_authority": True,
                }
            )
        unc = _IMPLICIT_UNC.match(text)
        if unc:  # so is a UNC path
            return _finish(
                {
                    "scheme": "file",
                    "authority": unc.group("host"),
                    "path": unc.group("path").replace("\\", "/"),
                    "query": "",
                    "fragment": "",
                    "has_authority": True,
                }
            )
        match = _PARSE.match(text)
        if not match or len(match.group("scheme")) == 1:
            return None
        has_authority = match.group("authority") is not None
        parts = match.groupdict(default="")
        parts["has_authority"] = has_authority
        parts["scheme"] = parts["scheme"].lower()
        if parts["scheme"] == "mailto" and not has_authority:
            parts["authority"], parts["path"] = (
                parts["path"],
                "",
            )  # the address is user@host
        return _finish(parts)

    def _need(self):
        parts = self._absolute()
        if parts is None:
            raise RelativeUriError(_RELATIVE)
        return parts

    @property
    def OriginalString(self):
        return str.__str__(self)

    @property
    def IsAbsoluteUri(self):
        return self._absolute() is not None

    @property
    def Scheme(self):
        return self._need()["scheme"]

    @property
    def Host(self):
        authority = self._need()["authority"].rpartition("@")[2]
        host, _, port = authority.rpartition(":")
        return (host if port.isdigit() else authority).lower()

    @property
    def Port(self):
        parts = self._need()
        authority = parts["authority"].rpartition("@")[2]
        _, _, port = authority.rpartition(":")
        if port.isdigit():
            return int(port)
        return _DEFAULT_PORTS.get(parts["scheme"], -1)

    @property
    def IsFile(self):
        return self._need()["scheme"] == "file"

    @property
    def IsUnc(self):
        parts = self._need()
        return parts["scheme"] == "file" and bool(parts["authority"])

    @property
    def Query(self):
        return _escape(self._need()["query"])

    @property
    def Fragment(self):
        return _escape(self._need()["fragment"])

    @property
    def AbsolutePath(self):
        parts = self._need()
        path = parts["path"]
        if (
            parts["scheme"] == "file"
            and not parts["authority"]
            and re.match(r"^/[A-Za-z]:", path)
        ):
            path = path[1:]  # C:/dir/a.txt, with no leading slash
        return _escape(path)

    @property
    def PathAndQuery(self):
        return self.AbsolutePath + _escape(self._need()["query"])

    @property
    def Segments(self):
        return re.findall(r"[^/]*/|[^/]+", _escape(self._need()["path"]))

    @property
    def AbsoluteUri(self):
        parts = self._need()
        host = self.Host
        authority = parts["authority"].rpartition("@")
        explicit_port = re.search(r":(\d+)$", authority[2])
        netloc = authority[0] + ("@" if authority[1] else "") + host
        if explicit_port and _DEFAULT_PORTS.get(parts["scheme"]) != int(
            explicit_port.group(1)
        ):
            netloc += ":" + explicit_port.group(1)
        slashes = (
            "//" if parts["has_authority"] or parts["scheme"] in _WITH_SLASHES else ""
        )
        return f"{parts['scheme']}:{slashes}{netloc}{_escape(parts['path'])}{_escape(parts['query'])}{_escape(parts['fragment'])}"

    @property
    def LocalPath(self):
        parts = self._need()
        path = unquote(parts["path"])
        if parts["scheme"] != "file":
            return path
        if parts["authority"]:
            return "\\\\" + self.Host + path.replace("/", "\\")
        if re.match(r"^/[A-Za-z]:", path):
            path = path[1:]
        return path.replace("/", "\\")

    def ToString(self):
        return (
            _unescape(self.AbsoluteUri)
            if self._absolute() is not None
            else self.OriginalString
        )

    def __str__(self):
        return self.ToString()

    def __repr__(self):
        return f"Uri({self.OriginalString!r})"
