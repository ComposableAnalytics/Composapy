from __future__ import annotations

import os
from pathlib import Path

import pytest

from composapy.session import Session, get_session, SessionRegistrationException
from composapy.dataflow.api import DataFlow


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
