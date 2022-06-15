from __future__ import annotations

import os
from pathlib import Path

import pytest

from composapy.session import Session
from composapy.dataflow.api import DataFlow


@pytest.mark.parametrize("session", ["Token", "Form"], indirect=True)
def test_session(session: Session):
    dataflow = DataFlow(session=session)
    dataflow.create(
        file_path=str(
            Path(os.path.dirname(Path(__file__)), "TestFiles", "calculator_test.json")
        )
    )  # dataflow.create() will throw an error if session authentication failed
    assert True
