from __future__ import annotations
from typing import TYPE_CHECKING
import os
from pathlib import Path
import pytest

from composapy.auth import AuthMode
from composapy.session import get_session, SessionRegistrationException
from composapy.dataflow.api import DataFlow
from composapy.utils import get_config_path
from composapy.config import read_config_session
from composapy.session import Session


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
    config_session = read_config_session()

    assert config_session.auth_mode == AuthMode.TOKEN
    assert config_session.uri == session.uri
    assert getattr(config_session, "token") == session._credentials


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_register_session_save_true_form(session: Session):
    session.register(save=True)
    config_session = read_config_session()

    assert config_session.auth_mode == AuthMode.FORM
    assert config_session.uri == session.uri
    assert getattr(config_session, "username") == session._credentials[0]
    assert getattr(config_session, "password") == session._credentials[1]
