import os
import pytest
from pathlib import Path

from dotenv import load_dotenv
from composapy.loader import load_init

test_env = sorted(Path().rglob(".test.env"))[0]
load_dotenv(test_env)

load_init()

from composapy.dataflow.api import DataFlow
from composapy.dataflow.models import DataFlowObject
from composapy.queryview.api import QueryView
from composapy.session import Session


@pytest.fixture
def session():
    return Session(os.getenv("TEST_USERNAME"), os.getenv("TEST_PASSWORD"))


@pytest.fixture
def dataflow(session: Session) -> DataFlow:
    return DataFlow(session)


@pytest.fixture
def dataflow_object(dataflow: DataFlow, request) -> DataFlowObject:
    return dataflow.create(
        file_path=str(Path(os.path.dirname(Path(__file__)), "TestFiles", request.param))
    )


# used when a fixture needs another copy of parameterized fixture
dataflow_object_extra = dataflow_object


@pytest.fixture
def queryview(session: Session) -> QueryView:
    return queryview(session)
