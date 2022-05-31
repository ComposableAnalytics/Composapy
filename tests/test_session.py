from __future__ import annotations

import os
from pathlib import Path

from composapy.session import Session
from composapy.dataflow.api import DataFlow


def test_session_with_token(session_with_token: Session):
    dataflow = DataFlow(session_with_token)
    dataflow.create(
        file_path=str(
            Path(os.path.dirname(Path(__file__)), "TestFiles", "calculator_test.json")
        )
    )  # dataflow.create() will throw an error if session authentication with token failed
    assert True
