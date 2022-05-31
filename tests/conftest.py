import os
import pytest
from pathlib import Path
from dotenv import load_dotenv

from composapy.dataflow.api import DataFlow
from composapy.dataflow.models import DataFlowObject
from composapy.queryview.api import QueryView
from composapy.session import Session

from CompAnalytics import Contracts
from System import Uri

# does not override environment variables, this is essentially a failsafe for local dev environment
for env_file in sorted(Path().rglob(".test*.env")):
    load_dotenv(env_file)


@pytest.fixture
def session():
    if os.getenv("TEST_API_KEY"):
        api_key = os.getenv("TEST_API_KEY")
    else:
        from CompAnalytics import IServices
        from System import Net, Uri, DateTime, TimeSpan

        connection_settings = IServices.Deploy.ConnectionSettings()
        form_credential = Net.NetworkCredential(
            os.getenv("TEST_USERNAME"), os.getenv("TEST_PASSWORD")
        )
        connection_settings.Uri = Uri(os.getenv("APPLICATION_URI"))
        connection_settings.AuthMode = IServices.Deploy.AuthMode.Form
        connection_settings.FormCredential = form_credential

        resource_manager = IServices.Deploy.ResourceManager(connection_settings)
        user_service = resource_manager.CreateAuthChannel[IServices.IUserService](
            "UserService"
        )
        user = user_service.GetCurrentUser()
        token_expiration_date = DateTime.UtcNow + TimeSpan.FromDays(3)
        api_key = user_service.GenerateUserToken(
            user.Id, user.UserName, token_expiration_date
        )
        os.environ["TEST_API_KEY"] = api_key
    return Session(api_key)


@pytest.fixture
def session_with_token():
    return Session(api_token=os.getenv("TEST_API_KEY"))


@pytest.fixture
def dataflow(session: Session) -> DataFlow:
    return DataFlow(session=session)


@pytest.fixture
def dataflow_object(dataflow: DataFlow, request) -> DataFlowObject:
    return dataflow.create(
        file_path=str(Path(os.path.dirname(Path(__file__)), "TestFiles", request.param))
    )


# used when a fixture needs another copy of parameterized fixture
dataflow_object_extra = dataflow_object


FIXTURE_DIR: Path = Path(os.path.join(os.path.dirname(os.path.realpath(__file__))))


@pytest.fixture
def clean_file_path(request) -> Path:
    file_path = FIXTURE_DIR.joinpath(".local_files", request.param)
    file_path.unlink(missing_ok=True)
    return file_path


@pytest.fixture
def file_path_object(request) -> Path:
    return FIXTURE_DIR.joinpath("TestFiles", request.param)


@pytest.fixture
def file_path_string(request) -> str:
    return str(FIXTURE_DIR.joinpath("TestFiles", request.param))


@pytest.fixture
def file_ref(request) -> Contracts.FileReference:
    file_path = Path(os.path.dirname(Path(__file__)), "TestFiles", request.param)
    file_ref = Contracts.FileReference.CreateWithAbsoluteUri[Contracts.FileReference](
        str(file_path), Uri(str(file_path))
    )
    return file_ref


@pytest.fixture
def queryview(session: Session) -> QueryView:
    return queryview(session=session)
