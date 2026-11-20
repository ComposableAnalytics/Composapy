"""Offline tests for the arguments a Session refuses, which need no server."""

import pytest

from composapy._transport.client import ServiceClient
from composapy.auth import AuthMode
from composapy.session import Session

URI = "http://example.test/CompApp/"


@pytest.mark.parametrize(
    "value", ["Token", "TOKEN", 1, None, object(), AuthMode.TOKEN.value]
)
def test_an_auth_mode_that_is_not_an_authmode_is_a_type_error(value):
    with pytest.raises(TypeError, match="auth_mode must be an AuthMode"):
        Session(uri=URI, auth_mode=value, credentials="token")


@pytest.mark.parametrize(
    "mode, credentials",
    [(AuthMode.TOKEN, "token"), (AuthMode.FORM, ("user", "password"))],
)
def test_each_authmode_is_still_accepted(mode, credentials, monkeypatch):
    # a Form session signs in when it is made, so stand in for the login page, which this test has no server for
    monkeypatch.setattr(
        ServiceClient, "_form_login", lambda self, username, password: None
    )
    assert Session(uri=URI, auth_mode=mode, credentials=credentials).auth_mode is mode
