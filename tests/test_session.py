from __future__ import annotations
from typing import TYPE_CHECKING
import os
from pathlib import Path
import pytest

from composapy.auth import AuthMode
from composapy.session import get_session, SessionRegistrationException
from composapy.dataflow.api import DataFlow
from composapy.config import get_config_session, read_config
from composapy.session import Session

username = os.getenv("TEST_USERNAME")
password = os.getenv("TEST_PASSWORD")


@pytest.mark.parametrize("session", ["Token", "Form"], indirect=True)
def test_session(session: Session):
    DataFlow.create(
        file_path=str(
            Path(os.path.dirname(Path(__file__)), "TestFiles", "calculator_test.json")
        )
    )  # dataflow.create() will throw an error if session authentication failed
    assert True


# don't need all variation of logon types for register/unregister
@pytest.mark.parametrize("session", ["Token"], indirect=True)
def test_register_session(session: Session):
    session.register()

    assert session == get_session()


@pytest.mark.parametrize("session", ["Token"], indirect=True)
def test_clear_registration_session(session: Session):
    session.register()
    Session.clear_registration()

    with pytest.raises(SessionRegistrationException):
        get_session()


@pytest.mark.parametrize("session", ["Token"], indirect=True)
def test_register_session_save_true_token(session: Session):
    session.register(save=True)
    _, config = read_config()
    config_session = get_config_session(config)

    assert config_session.auth_mode == AuthMode.TOKEN
    assert config_session.uri == session.uri
    assert getattr(config_session, "token") == session._credentials


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_register_session_save_true_form(session: Session):
    session.register(save=True)
    _, config = read_config()
    config_session = get_config_session(config)

    assert config_session.auth_mode == AuthMode.FORM
    assert config_session.uri == session.uri
    assert getattr(config_session, "username") == session._credentials[0]
    assert getattr(config_session, "password") == session._credentials[1]


def test_session_invalid_uri_error_message():
    """Test that the improved error message is displayed when an invalid URI is provided."""
    invalid_uri = "https://localhost/CompApp/"
    with pytest.raises(ConnectionError) as exc_info:
        session = Session(
            auth_mode=AuthMode.FORM, credentials=(username, password), uri=invalid_uri
        )
    expected_message = (
        "Unable to connect to URI. Common issues include incorrect URI scheme "
        "(http or https) or a typo in your URI. Please verify that you are using "
        "the correct scheme for your server."
    )
    assert expected_message in str(exc_info.value)


def test_session_uri_trailing_slash():
    """Test that a URI without a trailing slash is automatically corrected."""
    uri_without_slash = "http://localhost/CompApp"
    session = Session(
        auth_mode=AuthMode.FORM, credentials=(username, password), uri=uri_without_slash
    )
    assert session.uri.endswith(
        "/"
    ), "The session URI should end with a trailing slash."
