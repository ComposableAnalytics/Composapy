"""Offline tests for composapy.contracts.uri.Uri, the value of FileReference.Uri.

EXPECTED is what the baseline wheel's System.Uri returned for each member, recorded by tools/parity/corpus/uri_members.py
under pythonnet on 2026-10-27, so these tests hold the candidate to the behavior it replaces.
"""

import copy
import json
import pickle

import pytest

from composapy._wire import codec
from composapy.contracts import FileReference
from composapy.contracts.uri import RelativeUriError, Uri

WINDOWS = "file:///C:/data/folder/a.txt"
ESCAPED = "file:///C:/data/my%20folder/a%20b.txt"
UNC = "file://server/share/dir/a.txt"
HTTPS = "https://Example.test:8443/a/b%20c.txt?x=1&y=2#frag"
HTTP = "http://example.test/a/b.txt"
RELATIVE = "/CompApp/runs/70850f2b/5f051543/note.txt"

EXPECTED = {
    WINDOWS: dict(
        AbsoluteUri=WINDOWS,
        AbsolutePath="C:/data/folder/a.txt",
        LocalPath="C:\\data\\folder\\a.txt",
        Scheme="file",
        Host="",
        Port=-1,
        IsFile=True,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="C:/data/folder/a.txt",
        Segments=["/", "C:/", "data/", "folder/", "a.txt"],
        ToString=WINDOWS,
    ),
    ESCAPED: dict(
        AbsoluteUri=ESCAPED,
        AbsolutePath="C:/data/my%20folder/a%20b.txt",
        LocalPath="C:\\data\\my folder\\a b.txt",
        Scheme="file",
        Host="",
        Port=-1,
        IsFile=True,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="C:/data/my%20folder/a%20b.txt",
        Segments=["/", "C:/", "data/", "my%20folder/", "a%20b.txt"],
        ToString="file:///C:/data/my folder/a b.txt",
    ),
    UNC: dict(
        AbsoluteUri=UNC,
        AbsolutePath="/share/dir/a.txt",
        LocalPath="\\\\server\\share\\dir\\a.txt",
        Scheme="file",
        Host="server",
        Port=-1,
        IsFile=True,
        IsUnc=True,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="/share/dir/a.txt",
        Segments=["/", "share/", "dir/", "a.txt"],
        ToString=UNC,
    ),
    HTTPS: dict(
        AbsoluteUri="https://example.test:8443/a/b%20c.txt?x=1&y=2#frag",
        AbsolutePath="/a/b%20c.txt",
        LocalPath="/a/b c.txt",
        Scheme="https",
        Host="example.test",
        Port=8443,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="?x=1&y=2",
        Fragment="#frag",
        PathAndQuery="/a/b%20c.txt?x=1&y=2",
        Segments=["/", "a/", "b%20c.txt"],
        ToString="https://example.test:8443/a/b c.txt?x=1&y=2#frag",
    ),
    HTTP: dict(
        AbsoluteUri=HTTP,
        AbsolutePath="/a/b.txt",
        LocalPath="/a/b.txt",
        Scheme="http",
        Host="example.test",
        Port=80,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="/a/b.txt",
        Segments=["/", "a/", "b.txt"],
        ToString=HTTP,
    ),
}
CASES = [
    (uri, member, value)
    for uri, members in EXPECTED.items()
    for member, value in members.items()
]


@pytest.mark.parametrize(
    "text, member, expected",
    CASES,
    ids=[f"{i}-{m}" for i, (_, m, _) in enumerate(CASES)],
)
def test_every_member_matches_what_system_uri_returned(text, member, expected):
    uri = Uri(text)
    actual = getattr(uri, member)
    actual = actual() if callable(actual) else actual
    assert actual == expected and type(actual) is type(expected)


@pytest.mark.parametrize("text", list(EXPECTED))
def test_str_of_an_absolute_uri_is_its_to_string_and_the_original_text_is_kept(text):
    uri = Uri(text)
    assert str(uri) == EXPECTED[text]["ToString"] and uri.OriginalString == text


def test_a_relative_uri_answers_only_original_string_to_string_and_is_absolute_false():
    uri = Uri(RELATIVE)
    assert (
        uri.OriginalString == RELATIVE
        and uri.ToString() == RELATIVE
        and str(uri) == RELATIVE
        and uri.IsAbsoluteUri is False
    )
    for member in (
        "AbsoluteUri",
        "AbsolutePath",
        "LocalPath",
        "Scheme",
        "Host",
        "Port",
        "IsFile",
        "IsUnc",
        "Query",
        "Fragment",
        "PathAndQuery",
        "Segments",
    ):
        with pytest.raises(RelativeUriError, match="relative URI"):
            getattr(uri, member)


def test_it_is_a_str_that_compares_hashes_and_serializes_as_its_text():
    uri = Uri(ESCAPED)
    assert (
        isinstance(uri, str)
        and uri == ESCAPED
        and hash(uri) == hash(ESCAPED)
        and {uri: 1}[ESCAPED] == 1
    )
    assert json.dumps({"Uri": uri}) == json.dumps({"Uri": ESCAPED})
    assert uri.startswith("file:///") and uri.endswith("a%20b.txt")


def test_an_escape_that_changes_meaning_stays_escaped_and_a_multibyte_escape_decodes_whole():
    assert (
        str(Uri("https://example.test/a%2Fb%25c%3Fd%23e"))
        == "https://example.test/a%2Fb%25c%3Fd%23e"
    )
    assert (
        str(Uri("https://example.test/caf%C3%A9.txt"))
        == "https://example.test/caf\u00e9.txt"
    )
    assert (
        Uri("https://example.test/caf%C3%A9.txt").AbsoluteUri
        == "https://example.test/caf%C3%A9.txt"
    )
    assert (
        Uri("https://example.test/a b.txt").AbsoluteUri
        == "https://example.test/a%20b.txt"
    )


def test_a_default_port_is_not_in_the_absolute_uri_and_an_explicit_one_is_the_port():
    assert (
        Uri("http://example.test:80/a").AbsoluteUri == "http://example.test/a"
        and Uri("http://example.test:80/a").Port == 80
    )
    assert Uri("https://example.test/a").Port == 443


def test_a_windows_path_is_read_as_a_file_uri():
    uri = Uri("C:\\data\\a b.txt")
    assert (
        uri.IsAbsoluteUri
        and uri.IsFile
        and uri.LocalPath == "C:\\data\\a b.txt"
        and uri.AbsoluteUri == "file:///C:/data/a%20b.txt"
    )


# ----------------------------------------------------------------------------------------------
# As the value of a FileReference
# ----------------------------------------------------------------------------------------------


def reference(uri_text):
    return codec.decode(
        json.dumps(
            {"__type": "FileReference:#CompAnalytics.Contracts", "Uri": uri_text}
        )
    )


def test_a_file_reference_returns_its_uri_with_the_members():
    ref = reference(ESCAPED)
    assert (
        type(ref.Uri) is Uri
        and ref.Uri.LocalPath == "C:\\data\\my folder\\a b.txt"
        and ref.Uri == ESCAPED
    )


def test_the_contract_text_is_not_changed_by_reading_or_encoding_it():
    ref = reference(ESCAPED)
    _ = (ref.Uri.AbsoluteUri, str(ref.Uri), ref.Uri.LocalPath)
    assert ref["Uri"] == ESCAPED and type(ref["Uri"]) is str
    assert json.loads(codec.encode(ref))["Uri"] == ESCAPED


def test_a_file_reference_made_from_another_ones_uri_keeps_the_escapes():
    original = reference(ESCAPED)
    copy = FileReference.CreateWithAbsoluteUri("C:\\local\\a b.txt", original.Uri)
    assert (
        copy["Uri"] == ESCAPED
    )  # str(Uri) is the unescaped text; the stored value must not be


def test_the_uri_survives_a_pickle_as_the_original_text():
    ref = FileReference.CreateWithAbsoluteUri("C:\\local\\a b.txt", ESCAPED)
    loaded = pickle.loads(pickle.dumps(ref))
    assert (
        loaded["Uri"] == ESCAPED
        and type(loaded.Uri) is Uri
        and loaded.LocalFile == "C:\\local\\a b.txt"
    )


def test_a_uri_assigned_to_a_file_reference_is_stored_as_text():
    ref = reference(HTTP)
    ref.Uri = HTTPS
    assert ref["Uri"] == HTTPS and ref.Uri.Port == 8443


def test_a_file_reference_without_a_uri_returns_none():
    assert (
        codec.decode(
            '{"__type":"FileReference:#CompAnalytics.Contracts","Uri":null}'
        ).Uri
        is None
    )


# ----------------------------------------------------------------------------------------------
# More URIs: expectations derived from System.Uri
#
# DERIVED is not part of the recorded baseline. Each value was read from a real System.Uri on 2026-11-06, on .NET 8 and
# on .NET Framework 4.8 (PowerShell 5.1), which gave the same answer for every member listed here. Where the two differ
# (an IPv6 host, a %2F escape in ToString) the case is not in this table.
# ----------------------------------------------------------------------------------------------

USER_INFO = "https://user:pw@Example.test:8080/p/q?x=1#f"
UPPER_CASE = "HTTP://EXAMPLE.TEST/A/B"
NON_ASCII = "http://example.test/caf\u00e9"
SPACE = "http://example.test/a b"
EMPTY_QUERY = "http://example.test/a?"
EMPTY_FRAGMENT = "http://example.test/a#"
LOCALHOST = "file://localhost/C:/a.txt"
DRIVE_SLASHES = "C:/data/a.txt"
FTP = "ftp://example.test:21/a"
WS = "ws://example.test/a"
SEMICOLON = "http://example.test/a;b=c"
HASH_ESCAPE = "file:///C:/data/a%23b.txt"
DIRECTORY = "http://example.test/dir/"

DERIVED = {
    USER_INFO: dict(
        AbsoluteUri="https://user:pw@example.test:8080/p/q?x=1#f",
        AbsolutePath="/p/q",
        LocalPath="/p/q",
        Scheme="https",
        Host="example.test",
        Port=8080,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="?x=1",
        Fragment="#f",
        PathAndQuery="/p/q?x=1",
        Segments=["/", "p/", "q"],
        ToString="https://user:pw@example.test:8080/p/q?x=1#f",
    ),
    UPPER_CASE: dict(
        AbsoluteUri="http://example.test/A/B",
        AbsolutePath="/A/B",
        LocalPath="/A/B",
        Scheme="http",
        Host="example.test",
        Port=80,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="/A/B",
        Segments=["/", "A/", "B"],
        ToString="http://example.test/A/B",
    ),
    NON_ASCII: dict(
        AbsoluteUri="http://example.test/caf%C3%A9",
        AbsolutePath="/caf%C3%A9",
        LocalPath="/caf\u00e9",
        Scheme="http",
        Host="example.test",
        Port=80,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="/caf%C3%A9",
        Segments=["/", "caf%C3%A9"],
        ToString="http://example.test/caf\u00e9",
    ),
    SPACE: dict(
        AbsoluteUri="http://example.test/a%20b",
        AbsolutePath="/a%20b",
        LocalPath="/a b",
        Scheme="http",
        Host="example.test",
        Port=80,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="/a%20b",
        Segments=["/", "a%20b"],
        ToString="http://example.test/a b",
    ),
    EMPTY_QUERY: dict(
        AbsoluteUri="http://example.test/a?",
        AbsolutePath="/a",
        LocalPath="/a",
        Scheme="http",
        Host="example.test",
        Port=80,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="?",
        Fragment="",
        PathAndQuery="/a?",
        Segments=["/", "a"],
        ToString="http://example.test/a?",
    ),
    EMPTY_FRAGMENT: dict(
        AbsoluteUri="http://example.test/a#",
        AbsolutePath="/a",
        LocalPath="/a",
        Scheme="http",
        Host="example.test",
        Port=80,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="#",
        PathAndQuery="/a",
        Segments=["/", "a"],
        ToString="http://example.test/a#",
    ),
    LOCALHOST: dict(
        AbsoluteUri="file://localhost/C:/a.txt",
        AbsolutePath="/C:/a.txt",
        LocalPath="\\\\localhost\\C:\\a.txt",
        Scheme="file",
        Host="localhost",
        Port=-1,
        IsFile=True,
        IsUnc=True,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="/C:/a.txt",
        Segments=["/", "C:/", "a.txt"],
        ToString="file://localhost/C:/a.txt",
    ),
    DRIVE_SLASHES: dict(
        AbsoluteUri="file:///C:/data/a.txt",
        AbsolutePath="C:/data/a.txt",
        LocalPath="C:\\data\\a.txt",
        Scheme="file",
        Host="",
        Port=-1,
        IsFile=True,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="C:/data/a.txt",
        Segments=["/", "C:/", "data/", "a.txt"],
        ToString="file:///C:/data/a.txt",
    ),
    FTP: dict(
        AbsoluteUri="ftp://example.test/a",
        AbsolutePath="/a",
        LocalPath="/a",
        Scheme="ftp",
        Host="example.test",
        Port=21,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="/a",
        Segments=["/", "a"],
        ToString="ftp://example.test/a",
    ),
    WS: dict(
        AbsoluteUri="ws://example.test/a",
        AbsolutePath="/a",
        LocalPath="/a",
        Scheme="ws",
        Host="example.test",
        Port=80,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="/a",
        Segments=["/", "a"],
        ToString="ws://example.test/a",
    ),
    SEMICOLON: dict(
        AbsoluteUri="http://example.test/a;b=c",
        AbsolutePath="/a;b=c",
        LocalPath="/a;b=c",
        Scheme="http",
        Host="example.test",
        Port=80,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="/a;b=c",
        Segments=["/", "a;b=c"],
        ToString="http://example.test/a;b=c",
    ),
    HASH_ESCAPE: dict(
        AbsoluteUri="file:///C:/data/a%23b.txt",
        AbsolutePath="C:/data/a%23b.txt",
        LocalPath="C:\\data\\a#b.txt",
        Scheme="file",
        Host="",
        Port=-1,
        IsFile=True,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="C:/data/a%23b.txt",
        Segments=["/", "C:/", "data/", "a%23b.txt"],
        ToString="file:///C:/data/a%23b.txt",
    ),
    DIRECTORY: dict(
        AbsoluteUri="http://example.test/dir/",
        AbsolutePath="/dir/",
        LocalPath="/dir/",
        Scheme="http",
        Host="example.test",
        Port=80,
        IsFile=False,
        IsUnc=False,
        IsAbsoluteUri=True,
        Query="",
        Fragment="",
        PathAndQuery="/dir/",
        Segments=["/", "dir/"],
        ToString="http://example.test/dir/",
    ),
}
DERIVED_CASES = [
    (uri, member, value)
    for uri, members in DERIVED.items()
    for member, value in members.items()
]


@pytest.mark.parametrize(
    "text, member, expected",
    DERIVED_CASES,
    ids=[f"{i}-{m}" for i, (_, m, _) in enumerate(DERIVED_CASES)],
)
def test_every_member_matches_what_system_uri_returns_for_more_uris(
    text, member, expected
):
    actual = getattr(Uri(text), member)
    actual = actual() if callable(actual) else actual
    assert actual == expected and type(actual) is type(expected)


@pytest.mark.parametrize("text", list(DERIVED))
def test_str_of_a_derived_uri_is_its_to_string_and_the_original_text_is_kept(text):
    uri = Uri(text)
    assert str(uri) == DERIVED[text]["ToString"] and uri.OriginalString == text


def test_a_scheme_in_capitals_is_read_as_lower_case_and_the_host_too():
    uri = Uri("HTTPS://Example.Test/Path")
    assert (uri.Scheme, uri.Host, uri.AbsolutePath) == (
        "https",
        "example.test",
        "/Path",
    )
    assert uri.OriginalString == "HTTPS://Example.Test/Path"


def test_a_uri_with_user_info_keeps_it_in_the_absolute_uri_and_not_in_the_host():
    uri = Uri("https://user@example.test/a")
    assert uri.Host == "example.test" and uri.Port == 443
    assert uri.AbsoluteUri == "https://user@example.test/a"


# ----------------------------------------------------------------------------------------------
# Pinned current behaviour: a decision is open, or there is nothing to compare with
# ----------------------------------------------------------------------------------------------


def test_pinned_an_ipv6_host_is_kept_in_the_form_it_was_written():
    # Matches .NET 8, which prints the compact form. .NET Framework 4.8 expands it to
    # [0000:0000:0000:0000:0000:0000:0000:0001], so what a script sees depends on the runtime the baseline ran on.
    uri = Uri("http://[::1]:8080/a/b")
    assert uri.Host == "[::1]" and uri.Port == 8080
    assert uri.AbsoluteUri == "http://[::1]:8080/a/b" and uri.IsFile is False


def test_an_empty_string_is_a_relative_uri():
    uri = Uri("")
    assert uri == "" and uri.IsAbsoluteUri is False
    assert uri.OriginalString == "" and uri.ToString() == "" and str(uri) == ""
    with pytest.raises(RelativeUriError, match="relative URI"):
        uri.Scheme


def test_pinned_two_spellings_of_one_absolute_uri_are_not_equal():
    # It compares as the text, as the class says; System.Uri.Equals would treat these as the same URI
    assert Uri("HTTP://EXAMPLE.TEST/a") != Uri("http://example.test/a")
    assert (
        Uri("HTTP://EXAMPLE.TEST/a").AbsoluteUri
        == Uri("http://example.test/a").AbsoluteUri
    )


def test_a_uri_is_a_str_so_text_operations_give_plain_text():
    uri = Uri("http://example.test/a")
    assert type(uri + "b") is str and type(uri[:4]) is str and type(uri.upper()) is str
    assert repr(uri) == "Uri('http://example.test/a')"
    assert repr(Uri("a'b")) == 'Uri("a\'b")'


@pytest.mark.parametrize("protocol", [2, 3, 4, 5])
def test_a_bare_uri_survives_a_pickle_as_the_original_text(protocol):
    uri = Uri(ESCAPED)
    loaded = pickle.loads(pickle.dumps(uri, protocol=protocol))
    assert type(loaded) is Uri and loaded.OriginalString == ESCAPED
    assert loaded == uri and loaded.LocalPath == uri.LocalPath


@pytest.mark.parametrize("protocol", [0, 1])
def test_a_bare_uri_survives_a_pickle_of_the_oldest_protocols_unchanged(protocol):
    loaded = pickle.loads(pickle.dumps(Uri(ESCAPED), protocol=protocol))
    assert loaded.OriginalString == ESCAPED


def test_a_bare_uri_survives_a_copy_as_a_uri():
    uri = Uri(ESCAPED)
    for copied in (copy.copy(uri), copy.deepcopy(uri)):
        assert type(copied) is Uri and copied.OriginalString == ESCAPED


# ----------------------------------------------------------------------------------------------
# Where a plain reading of the text would differ from System.Uri (the expected values are System.Uri's)
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["mailto:a@b.com", "urn:isbn:123", "data:text/plain,hi"]
)
def test_a_uri_without_an_authority_keeps_its_text(text):
    uri = Uri(text)
    assert (
        uri.AbsoluteUri == text
        and str(uri) == text
        and uri.Scheme == text.split(":")[0]
    )


def test_the_members_of_a_mailto_uri():
    uri = Uri("mailto:a@b.com")
    assert (uri.Host, uri.AbsolutePath, uri.PathAndQuery, uri.Segments) == (
        "b.com",
        "",
        "",
        [],
    )


def test_an_implicit_unc_path_is_read_as_a_file_uri():
    uri = Uri("\\\\server\\share\\dir\\a b.txt")
    assert uri.IsAbsoluteUri and uri.IsFile and uri.IsUnc and uri.Host == "server"
    assert uri.AbsoluteUri == "file://server/share/dir/a%20b.txt"
    assert uri.LocalPath == "\\\\server\\share\\dir\\a b.txt"


@pytest.mark.parametrize(
    "text, absolute_uri",
    [
        ("http://example.test", "http://example.test/"),
        ("HTTPS://Example.Test", "https://example.test/"),
        ("http://example.test:8080", "http://example.test:8080/"),
        ("http://example.test?q=1", "http://example.test/?q=1"),
    ],
)
def test_a_uri_with_no_path_has_the_path_slash(text, absolute_uri):
    uri = Uri(text)
    assert uri.AbsoluteUri == absolute_uri and uri.AbsolutePath == "/"
    assert uri.Segments == ["/"] and str(uri) == absolute_uri


def test_dot_segments_in_the_path_are_resolved():
    uri = Uri("http://example.test/a/./b/../c")
    assert uri.AbsoluteUri == "http://example.test/a/c" and uri.AbsolutePath == "/a/c"
    assert uri.Segments == ["/", "a/", "c"]


def test_a_space_in_the_query_or_fragment_is_escaped_in_those_members():
    uri = Uri("http://example.test/a?b c#d e")
    assert uri.Query == "?b%20c" and uri.Fragment == "#d%20e"
    assert uri.AbsoluteUri == "http://example.test/a?b%20c#d%20e"  # this one already is
