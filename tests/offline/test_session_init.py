"""Offline tests for Session.__init__ and close(): the uri it needs, the credentials each AuthMode takes, the login a
Form or Windows session makes when it is created, and the context manager.

The HTTP layer is a fake requests.Session, so nothing leaves the process. Token sessions make no request at all.
"""

import pytest
import requests

from composapy._transport import client as client_module
from composapy._transport.proxy import load_operations
from composapy.auth import AuthMode
from composapy.exceptions import (
    CONNECTION_ERROR_MESSAGE,
    AuthenticationError,
    InvalidAuthModeAction,
    InvalidFormConfigError,
    InvalidTokenConfigError,
    InvalidWindowsConfigError,
    SessionException,
    SessionRegistrationException,
    UriNotConfiguredError,
)
from composapy.session import Session, get_session, handle_connection_exception

URI = "http://example.test/CompApp/"
LOGIN_PAGE = (
    '<form><input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="state-1" />'
    '<input type="hidden" name="__EVENTVALIDATION" value="valid-2" /></form>'
)


class FakeResponse:
    def __init__(self, text="", content=b"", status_code=200):
        self.text, self.content, self.status_code = text, content, status_code


class FakeHttp:
    """Stands in for requests.Session: a login page that hands out an .ASPXAUTH cookie, and a record of every call."""

    issue_cookie = True
    connection_failures = 0
    page = LOGIN_PAGE
    instances = []

    def __init__(self):
        self.headers, self.cookies, self.auth = {}, {}, None
        self.gets, self.posts, self.requests = [], [], []
        self.closed = 0
        FakeHttp.instances.append(self)

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        if len(self.gets) <= FakeHttp.connection_failures:
            raise requests.ConnectionError("no route to host")
        return FakeResponse(text=FakeHttp.page)

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if FakeHttp.issue_cookie:
            self.cookies[".ASPXAUTH"] = "cookie-value"
        return FakeResponse(status_code=302)

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return FakeResponse(content=b'{"d":null}')

    def close(self):
        self.closed += 1


@pytest.fixture(autouse=True)
def http(monkeypatch):
    """Every Session made by these tests gets a FakeHttp, whose class attributes a test may change."""
    monkeypatch.setattr(requests, "Session", FakeHttp)
    monkeypatch.setattr(FakeHttp, "issue_cookie", True)
    monkeypatch.setattr(FakeHttp, "connection_failures", 0)
    monkeypatch.setattr(FakeHttp, "page", LOGIN_PAGE)
    monkeypatch.setattr(FakeHttp, "instances", [])
    monkeypatch.delenv("APPLICATION_URI", raising=False)
    return FakeHttp


def token_session(**kwargs):
    kwargs.setdefault("uri", URI)
    return Session(auth_mode=AuthMode.TOKEN, credentials="token-for-tests", **kwargs)


# ----------------------------------------------------------------------------------------------
# The uri
# ----------------------------------------------------------------------------------------------


def test_no_uri_and_no_environment_variable_is_refused_and_names_both_ways_to_set_it():
    with pytest.raises(UriNotConfiguredError) as error:
        Session(auth_mode=AuthMode.TOKEN, credentials="token-for-tests")
    assert "APPLICATION_URI" in str(error.value) and "uri" in str(error.value)
    assert isinstance(error.value, SessionException)


def test_the_default_auth_mode_is_windows_and_needs_a_uri_like_the_others():
    with pytest.raises(UriNotConfiguredError):
        Session()


def test_the_environment_variable_is_used_when_no_uri_is_passed(monkeypatch):
    monkeypatch.setenv("APPLICATION_URI", "http://env.test/CompApp/")
    session = token_session(uri=None)
    assert session.uri == "http://env.test/CompApp/"


def test_a_uri_that_is_passed_overrides_the_environment_variable(monkeypatch):
    monkeypatch.setenv("APPLICATION_URI", "http://env.test/CompApp/")
    assert token_session().uri == URI


@pytest.mark.parametrize(
    "given, expected",
    [
        ("http://example.test/CompApp", "http://example.test/CompApp/"),
        ("http://example.test/CompApp/", "http://example.test/CompApp/"),
        ("http://example.test", "http://example.test/"),
        ("https://example.test:8443/a/b", "https://example.test:8443/a/b/"),
    ],
)
def test_a_uri_always_ends_with_a_slash(given, expected, monkeypatch):
    session = token_session(uri=given)
    assert session.uri == expected and session.connection_settings.Uri == expected
    assert session._client.uri == expected
    # the same rule for the environment variable
    monkeypatch.setenv("APPLICATION_URI", given)
    assert token_session(uri=None).uri == expected


def test_a_uri_with_a_slash_already_is_not_given_a_second_one():
    assert token_session(uri="http://example.test/CompApp//").uri.endswith("CompApp//")


def test_the_uri_is_used_to_build_every_request(http):
    session = token_session(uri="http://example.test/CompApp")
    session.property_service.GetProperty(1)
    ((method, url, _),) = http.instances[-1].requests
    assert (method, url) == (
        "POST",
        "http://example.test/CompApp/Services/PropertyService.svc/GetProperty",
    )
    assert session.resource_manager.CreateServiceEndpointUri("PropertyService") == (
        "http://example.test/CompApp/Services/PropertyService.svc"
    )


def test_pinned_an_empty_uri_is_not_refused_and_becomes_a_slash():
    # Pinned, needs a decision: "" is not None, so neither the missing-uri check nor anything else stops it, and every
    # request would go to the relative url "Services/...". An APPLICATION_URI set to "" does the same.
    assert token_session(uri="").uri == "/"


def test_pinned_an_empty_environment_variable_counts_as_set_and_becomes_a_slash(
    monkeypatch,
):
    # Pinned, needs a decision: see the test above
    monkeypatch.setenv("APPLICATION_URI", "")
    assert token_session(uri=None).uri == "/"


def test_the_uri_is_checked_before_the_credentials():
    with pytest.raises(UriNotConfiguredError):
        Session(auth_mode=AuthMode.TOKEN, credentials=None)


def test_the_auth_mode_is_checked_before_the_uri():
    with pytest.raises(TypeError, match="auth_mode must be an AuthMode"):
        Session(auth_mode="Token", credentials="token-for-tests")


# ----------------------------------------------------------------------------------------------
# Windows credentials
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "credentials", ["token", ("user", "password"), ["user", "password"], 1, b"x"]
)
def test_windows_authentication_takes_no_credentials(credentials, http):
    with pytest.raises(InvalidWindowsConfigError) as error:
        Session(uri=URI, auth_mode=AuthMode.WINDOWS, credentials=credentials)
    assert "AuthMode.WINDOWS" in str(error.value)
    assert http.instances == []  # refused before an HTTP session was made


def test_the_windows_refusal_does_not_repeat_the_credentials_it_refused():
    # A password handed to the wrong mode must not end up in the traceback or in any log that holds it
    with pytest.raises(InvalidWindowsConfigError) as error:
        Session(uri=URI, auth_mode=AuthMode.WINDOWS, credentials=("user", "s3cret"))
    message = str(error.value)
    assert "s3cret" not in message and "user" not in message
    assert "received credentials, which are not accepted for this mode" in message
    assert "credentials input values if using" in message and "vaules" not in message


class FakeNegotiateAuth:
    pass


@pytest.fixture
def windows_login(monkeypatch):
    """A Windows login that finds requests-negotiate-sspi, which only a Windows machine with pywin32 has."""
    monkeypatch.setattr(client_module, "_negotiate_auth", lambda: FakeNegotiateAuth)
    monkeypatch.setattr(client_module.sys, "platform", "win32")


@pytest.mark.parametrize("credentials", [None, "", (), 0])
def test_windows_authentication_accepts_credentials_that_are_empty(
    credentials, windows_login
):
    session = Session(uri=URI, auth_mode=AuthMode.WINDOWS, credentials=credentials)
    assert session.auth_mode is AuthMode.WINDOWS


def test_a_windows_session_negotiates_and_then_logs_in_on_the_windows_page(
    windows_login, http
):
    session = Session(uri=URI, auth_mode=AuthMode.WINDOWS)
    fake = http.instances[-1]
    assert isinstance(fake.auth, FakeNegotiateAuth)
    assert fake.gets[0][0] == URI + "Account/WinLogin.aspx"
    ((url, kwargs),) = fake.posts
    assert url == URI + "Account/WinLogin.aspx"
    assert kwargs["data"] == {
        "__VIEWSTATE": "state-1",
        "__EVENTVALIDATION": "valid-2",
        "ctl00$MainContent$LoginButton": "Log In",
    }
    assert session._client._login_failed is False


def test_windows_authentication_off_windows_is_refused_with_the_reason(monkeypatch):
    monkeypatch.setattr(client_module.sys, "platform", "linux")
    with pytest.raises(InvalidAuthModeAction, match="requires Windows"):
        Session(uri=URI, auth_mode=AuthMode.WINDOWS)


# ----------------------------------------------------------------------------------------------
# Token credentials
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "credentials", [None, 123, b"token", ("token",), ["token"], {"token": "x"}]
)
def test_token_authentication_needs_a_string(credentials, http):
    with pytest.raises(InvalidTokenConfigError) as error:
        Session(uri=URI, auth_mode=AuthMode.TOKEN, credentials=credentials)
    assert "AuthMode.TOKEN" in str(error.value)
    assert "to the credentials initialization kwargs" in str(error.value)
    assert http.instances == []


def test_a_token_goes_in_the_authorization_header_and_nothing_is_requested(http):
    session = token_session()
    fake = http.instances[-1]
    assert fake.headers == {"Authorization": "token-for-tests"}
    assert fake.gets == [] and fake.posts == [] and fake.requests == []
    assert session._credentials == "token-for-tests"
    assert session.auth_mode is AuthMode.TOKEN


def test_pinned_an_empty_token_is_accepted_and_sent_as_an_empty_header(http):
    # Pinned, needs a decision: "" is a str, so it passes the check, and the server would then refuse every request
    session = Session(uri=URI, auth_mode=AuthMode.TOKEN, credentials="")
    assert http.instances[-1].headers == {"Authorization": ""}
    assert session.auth_mode is AuthMode.TOKEN


# ----------------------------------------------------------------------------------------------
# Form credentials
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "credentials",
    [
        None,
        "user:password",
        ("user",),
        ("user", "password", "extra"),
        (),
        ["user", "password"],
        {"user": "password"},
    ],
    ids=["none", "string", "one", "three", "empty", "list", "dict"],
)
def test_form_authentication_needs_a_pair_in_a_tuple(credentials, http):
    with pytest.raises(InvalidFormConfigError) as error:
        Session(uri=URI, auth_mode=AuthMode.FORM, credentials=credentials)
    assert "AuthMode.FORM" in str(error.value)
    assert "to the credentials initialization kwargs" in str(error.value)
    assert http.instances == []


def test_a_form_session_signs_in_when_it_is_made_with_the_page_fields_and_the_credentials(
    http,
):
    session = Session(uri=URI, auth_mode=AuthMode.FORM, credentials=("me", "pw"))
    fake = http.instances[-1]
    assert fake.gets == [(URI + "Account/FormLogin.aspx", {"timeout": (60, 60)})]
    ((url, kwargs),) = fake.posts
    assert url == URI + "Account/FormLogin.aspx"
    assert kwargs["data"] == {
        "__VIEWSTATE": "state-1",
        "__EVENTVALIDATION": "valid-2",
        "ctl00$MainContent$LoginUser$UserName": "me",
        "ctl00$MainContent$LoginUser$Password": "pw",
        "ctl00$MainContent$LoginUser$LoginButton": "Login Button",
    }
    assert kwargs["allow_redirects"] is False
    assert session._client._login_failed is False and fake.requests == []


def test_a_form_login_that_gets_no_cookie_fails_at_the_first_call_not_at_creation(http):
    FakeHttp.issue_cookie = False
    session = Session(uri=URI, auth_mode=AuthMode.FORM, credentials=("me", "wrong"))
    assert session._client._login_failed is True
    with pytest.raises(AuthenticationError, match="ASPXAUTH"):
        session.property_service.GetProperty(1)
    assert http.instances[-1].requests == []  # nothing went to the service


def test_a_login_page_without_the_hidden_fields_is_an_authentication_error(http):
    FakeHttp.page = "<html>maintenance</html>"
    with pytest.raises(AuthenticationError, match="__VIEWSTATE"):
        Session(uri=URI, auth_mode=AuthMode.FORM, credentials=("me", "pw"))
    assert http.instances[-1].posts == []


def test_a_login_page_that_cannot_be_reached_is_tried_five_times_then_the_friendly_error(
    http,
):
    FakeHttp.connection_failures = 99
    with pytest.raises(ConnectionError) as error:
        Session(uri=URI, auth_mode=AuthMode.FORM, credentials=("me", "pw"))
    assert str(error.value) == CONNECTION_ERROR_MESSAGE
    assert len(http.instances[-1].gets) == 5


def test_a_login_page_that_fails_twice_is_tried_again(http):
    FakeHttp.connection_failures = 2
    session = Session(uri=URI, auth_mode=AuthMode.FORM, credentials=("me", "pw"))
    assert len(http.instances[-1].gets) == 3
    assert session._client._login_failed is False


# ----------------------------------------------------------------------------------------------
# What a session holds
# ----------------------------------------------------------------------------------------------


def test_a_session_has_a_proxy_for_every_service_the_operations_file_lists():
    session = token_session()
    assert set(session.services) == set(load_operations())
    assert session.property_service is session.services["PropertyService"]
    assert session.queryview_service is session.services["QueryViewService"]
    assert session.resource_manager.AvailableServices() == list(load_operations())


def test_creating_a_session_does_not_register_it():
    token_session()
    assert get_session(raise_exception=False) is None


def test_register_makes_it_the_session_and_clear_registration_removes_it():
    first, second = token_session(), token_session()
    first.register()
    assert get_session() is first
    second.register()
    assert get_session() is second
    Session.clear_registration()
    assert get_session(raise_exception=False) is None
    with pytest.raises(SessionRegistrationException, match="No session"):
        get_session()


# ----------------------------------------------------------------------------------------------
# Closing
# ----------------------------------------------------------------------------------------------


def test_close_closes_the_http_session(http):
    token_session().close()
    assert http.instances[-1].closed == 1


def test_closing_twice_is_harmless(http):
    session = token_session()
    session.close()
    session.close()
    assert http.instances[-1].closed == 2  # the fake counts both calls


def test_the_resource_manager_dispose_closes_the_session_too(http):
    token_session().resource_manager.Dispose()
    assert http.instances[-1].closed == 1


def test_as_a_context_manager_it_gives_itself_and_closes_on_exit(http):
    with token_session() as session:
        assert isinstance(session, Session)
        assert http.instances[-1].closed == 0
    assert http.instances[-1].closed == 1


def test_the_context_manager_closes_on_an_error_and_lets_it_through(http):
    with pytest.raises(RuntimeError, match="boom"):
        with token_session():
            raise RuntimeError("boom")
    assert http.instances[-1].closed == 1


def test_pinned_closing_does_not_unregister_the_session():
    # Pinned, needs a decision: a registered session that was closed stays the registered one
    with token_session() as session:
        session.register()
    assert get_session() is session


# ----------------------------------------------------------------------------------------------
# handle_connection_exception
# ----------------------------------------------------------------------------------------------


def test_a_requests_connection_error_becomes_the_friendly_connection_error():
    with pytest.raises(ConnectionError) as error:
        handle_connection_exception(requests.ConnectionError("refused"))
    assert str(error.value) == CONNECTION_ERROR_MESSAGE
    assert error.value.__suppress_context__ is True


@pytest.mark.parametrize("error", [ValueError("x"), requests.Timeout("slow")])
def test_any_other_exception_is_left_for_the_caller_to_raise(error):
    assert handle_connection_exception(error) is None
