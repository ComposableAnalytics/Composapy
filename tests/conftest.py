import os
import pytest
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".test.env")

if os.getenv("IS_UNPACKAGED"):
    from src.composapy.loader import load_init

    load_init()

    from src.composapy.dataflow.api import DataFlow
    from src.composapy.dataflow.models import DataFlowObject
    from src.composapy.queryview.api import QueryView
    from src.composapy.session import Session

else:
    from composapy.loader import load_init

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
