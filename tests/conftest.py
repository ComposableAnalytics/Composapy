import os
import pytest
from pathlib import Path, PureWindowsPath
from dotenv import load_dotenv
import warnings
from urllib.parse import urlparse

from composapy.dataflow.api import DataFlow
from composapy.queryview.api import QueryView
from composapy.session import Session
from composapy.utils import _remove_suffix

from CompAnalytics import Contracts
from System import Uri
from CompAnalytics.Utils import WinAuthUtils

# does not override environment variables, this is essentially a failsafe for local dev environment
for env_file in sorted(Path().rglob(".test*.env")):
    load_dotenv(env_file)


class TestSetupException(Exception):
    pass


class InvalidTestConfigError(TestSetupException):
    pass


def create_token_auth_session() -> Session:
    if os.getenv("TEST_API_KEY"):
        session = Session(
            auth_mode=Session.AuthMode.TOKEN, credentials=os.getenv("TEST_API_KEY")
        )
        session.register()
        return session

    if not os.getenv("TEST_USERNAME") or not os.getenv("TEST_PASSWORD"):
        raise InvalidTestConfigError(
            "TEST_API_KEY was not supplied and TEST_USERNAME and/or TEST_PASSWORD in test "
            "configuration files were not found, but are needed to generate a new API token."
        )

    warnings.warn(
        "TEST_API_KEY is not setup inside of your .test.env file. A temporary api key will "
        "be created with your (TEST_USERNAME, TEST_PASSWORD) for this test run, but will not be "
        "set in your .local.env file. To remove this warning -- add a valid TEST_API_KEY to your "
        ".local.env config file."
    )

    from CompAnalytics import IServices
    from System import Net, Uri, DateTime, TimeSpan

    connection_settings = IServices.Deploy.ConnectionSettings()
    connection_settings.Uri = Uri(os.getenv("APPLICATION_URI"))
    connection_settings.AuthMode = IServices.Deploy.AuthMode.Form
    connection_settings.FormCredential = Net.NetworkCredential(
        os.getenv("TEST_USERNAME"), os.getenv("TEST_PASSWORD")
    )

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

    session = Session(auth_mode=Session.AuthMode.TOKEN, credentials=api_key)
    session.register()
    return session


def create_windows_auth_session():
    session = Session(auth_mode=Session.AuthMode.WINDOWS)
    session.register()
    return session


def create_form_auth_session() -> Session:
    if not os.getenv("TEST_USERNAME") or not os.getenv("TEST_PASSWORD"):
        raise InvalidTestConfigError(
            "TEST_USERNAME and/or TEST_PASSWORD in test configuration files were not found, but "
            "are needed for creating a session with auth mode Form."
        )

    session = Session(
        auth_mode=Session.AuthMode.FORM,
        credentials=(os.getenv("TEST_USERNAME"), os.getenv("TEST_PASSWORD")),
    )
    session.register()
    return session


def enable_windows_auth():
    """Csharp DataLabs tests are expected to manage windows authorization configuration."""
    if not os.getenv("JUPYTER_ENVIRONMENT_FLAG"):
        uri = os.getenv("APPLICATION_URI")
        virtual_path = _remove_suffix(urlparse(uri).path, "/")
        WinAuthUtils.EnableWindowsAuth(True, virtual_path)


def disable_windows_auth():
    """Csharp DataLabs tests are expected to manage windows authorization configuration."""
    if not os.getenv("JUPYTER_ENVIRONMENT_FLAG"):
        uri = os.getenv("APPLICATION_URI")
        virtual_path = _remove_suffix(urlparse(uri).path, "/")
        WinAuthUtils.EnableWindowsAuth(False, virtual_path)


@pytest.fixture
def session(request):
    if request.param == "Windows":
        enable_windows_auth()
        yield create_windows_auth_session()
        disable_windows_auth()
    elif request.param == "Form":
        yield create_form_auth_session()
    elif request.param == "Token":
        yield create_token_auth_session()


@pytest.fixture
def dataflow_object(request):
    if request.param[0] == "Windows":
        try:
            enable_windows_auth()
            create_windows_auth_session()

            yield DataFlow.create(
                file_path=str(
                    Path(os.path.dirname(Path(__file__)), "TestFiles", request.param[1])
                )
            )
        finally:
            disable_windows_auth()

    elif request.param[0] == "Form":
        create_form_auth_session()
        yield DataFlow.create(
            file_path=str(
                Path(os.path.dirname(Path(__file__)), "TestFiles", request.param[1])
            )
        )
    elif request.param[0] == "Token":
        create_token_auth_session()
        yield DataFlow.create(
            file_path=str(
                Path(os.path.dirname(Path(__file__)), "TestFiles", request.param[1])
            )
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
def file_path_object(request) -> PureWindowsPath:
    return PureWindowsPath(FIXTURE_DIR.joinpath("TestFiles", request.param))


@pytest.fixture
def file_path_string(request) -> str:
    return str(PureWindowsPath(FIXTURE_DIR.joinpath("TestFiles", request.param)))


@pytest.fixture
def file_ref(request) -> Contracts.FileReference:
    file_path = Path(os.path.dirname(Path(__file__)), "TestFiles", request.param)
    file_ref = Contracts.FileReference.CreateWithAbsoluteUri[Contracts.FileReference](
        str(file_path), Uri(str(file_path))
    )
    return file_ref


@pytest.fixture
def queryview(session_token_auth: Session) -> QueryView:
    return queryview()
