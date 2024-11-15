import os
import pytest
from pathlib import Path, PureWindowsPath
from dotenv import load_dotenv
import warnings
from urllib.parse import urlparse
import shutil

# does not override environment variables, this is essentially a failsafe for local dev environment
for env_file in sorted(Path().rglob(".test*.env")):
    load_dotenv(env_file)

# set DATALAB_DLL_DIR environment variable separately
if not os.getenv("DATALAB_DLL_DIR"):
    os.environ["DATALAB_DLL_DIR"] = str(
        Path(__file__).parent.parent.parent.parent.joinpath(
            "Product", "CompAnalytics.DataLabService", "bin", "Debug"
        )
    )

FIXTURE_DIR: Path = Path(os.path.join(os.path.dirname(os.path.realpath(__file__))))
LOCAL_FILES_DIR: Path = FIXTURE_DIR.joinpath(".local_files")
os.environ["COMPOSAPY_INI_DIR"] = str(LOCAL_FILES_DIR)


def _clean_testing_local_files():
    LOCAL_FILES_DIR.mkdir(exist_ok=True)
    for child in LOCAL_FILES_DIR.iterdir():
        child.unlink()


_clean_testing_local_files()

from composapy.dataflow.api import DataFlow
from composapy.queryview.api import QueryView
from composapy.session import Session, get_session
from composapy.utils import _remove_suffix
from composapy.key.models import KeyObject
from composapy.queryview.models import QueryViewObject, QueryViewPagedObject
from composapy.key.api import Key
from composapy.auth import AuthMode

from CompAnalytics import Contracts
from CompAnalytics.Contracts import Property
from CompAnalytics.Contracts.QueryView import LiteralInput, SearchInput
from CompAnalytics.Extension.Sql import SqlConnectionSettings
from System import Uri, Guid
from CompAnalytics.Utils import WinAuthUtils


class TestSetupException(Exception):
    pass


class InvalidTestConfigError(TestSetupException):
    pass


@pytest.fixture(scope="function", autouse=False)
def dll_exclude(monkeypatch):
    DATALAB_DLL_DIR = os.getenv("DATALAB_DLL_DIR")
    temp_dll_subfolder_path = Path(DATALAB_DLL_DIR, "testDllExclude")
    mock_dll = "CompAnalytics.MockExclude.dll"
    mock_dll_src_path = Path(os.path.dirname(Path(__file__)), "TestFiles", mock_dll)
    mock_dll_target_path = temp_dll_subfolder_path.joinpath(mock_dll)

    # setup
    temp_dll_subfolder_path.mkdir(exist_ok=True)
    shutil.copyfile(mock_dll_src_path, mock_dll_target_path)
    monkeypatch.setenv("DATALAB_DLL_DIR_EXCLUDE", str(temp_dll_subfolder_path) + ";")

    yield

    # cleanup
    mock_dll_target_path.unlink()
    temp_dll_subfolder_path.rmdir()
    monkeypatch.delenv("DATALAB_DLL_DIR_EXCLUDE", raising=False)


@pytest.fixture(scope="function", autouse=True)
def _clean_local_files_dir():
    _clean_testing_local_files()


def create_token_auth_session() -> Session:
    if os.getenv("TEST_API_KEY"):
        session = Session(
            auth_mode=AuthMode.TOKEN, credentials=os.getenv("TEST_API_KEY")
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

    session = Session(auth_mode=AuthMode.TOKEN, credentials=api_key)
    session.register()
    return session


def create_windows_auth_session():
    session = Session(auth_mode=AuthMode.WINDOWS)
    session.register()
    return session


def create_form_auth_session() -> Session:
    if not os.getenv("TEST_USERNAME") or not os.getenv("TEST_PASSWORD"):
        raise InvalidTestConfigError(
            "TEST_USERNAME and/or TEST_PASSWORD in test configuration files were not found, but "
            "are needed for creating a session with auth mode Form."
        )

    session = Session(
        auth_mode=AuthMode.FORM,
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


@pytest.fixture(scope="module", autouse=True)
def windows_auth(request):
    if not "test_windows_auth.py" in request.keywords:
        yield
    else:
        enable_windows_auth()
        yield
        disable_windows_auth()


@pytest.fixture
def session(request):
    if request.param == "Windows":
        yield create_windows_auth_session()
    elif request.param == "Form":
        yield create_form_auth_session()
    elif request.param == "Token":
        yield create_token_auth_session()


@pytest.fixture
def dataflow_object(request):
    if request.param[0] == "Windows":
        try:
            create_windows_auth_session()

            yield DataFlow.create(
                file_path=str(
                    Path(os.path.dirname(Path(__file__)), "TestFiles", request.param[1])
                )
            )
        finally:
            pass

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


@pytest.fixture
def property() -> Contracts.Property:
    create_form_auth_session()
    property_service = get_session().property_service

    connection_settings = SqlConnectionSettings()
    connection_settings.Host = "host.com"
    connection_settings.Port = 1234
    connection_settings.Username = "user"
    connection_settings.Password = "password"

    property = Property(connection_settings)
    property.Name = Guid.NewGuid().ToString("N")

    saved_property = property_service.SaveProperty(property)

    yield saved_property

    property_service.DeleteProperty(saved_property.Id)


@pytest.fixture
def default_health_key_object() -> KeyObject:
    create_form_auth_session()
    property_service = get_session().property_service

    connection_settings = SqlConnectionSettings()
    connection_settings.Host = "."
    connection_settings.Port = None
    connection_settings.Database = "Health"
    connection_settings.Username = "CompAnalyticsPublicUser"
    connection_settings.Password = "c0mpanalytics!"

    property = Property(connection_settings)
    property.Name = "Test Health Db Key"

    saved_property = property_service.SaveProperty(property)

    yield Key.get(saved_property.Id)

    property_service.DeleteProperty(saved_property.Id)


# used when a fixture needs another copy of parameterized fixture
dataflow_object_extra = dataflow_object


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
def queryview_driver(default_health_key_object) -> QueryViewObject:
    yield QueryView.driver(default_health_key_object)


@pytest.fixture
def queryview_driver_interactive(default_health_key_object) -> QueryViewPagedObject:
    yield QueryView.driver(default_health_key_object, interactive=True)


@pytest.fixture
def queryview_input_driver(default_health_key_object) -> QueryViewObject:
    driver = QueryView.driver(default_health_key_object)

    # set up literal/search inputs
    race_input = LiteralInput()
    race_input.DisplayName = "raceLiteralInput"
    race_input.TemplateName = "raceLiteralInput"
    race_input.DataType = "String"
    race_input.Default = "White"

    red_input = LiteralInput()
    red_input.DisplayName = "redLiteralInput"
    red_input.TemplateName = "redLiteralInput"
    red_input.DataType = "Boolean"
    red_input.Default = "true"

    age_input = SearchInput()
    age_input.DisplayName = "ageSearchInput"
    age_input.TemplateName = "ageSearchInput"
    age_input.DataType = "Number"
    age_input.Column = "age"
    age_input.Default = "50"
    age_input.DefaultOperator = ">"

    gender_input = SearchInput()
    gender_input.DisplayName = "genderSearchInput"
    gender_input.TemplateName = "genderSearchInput"
    gender_input.DataType = "String"
    gender_input.Column = "gender"
    gender_input.Default = "M"
    gender_input.DefaultOperator = "="
    gender_input.OperatorOptional = True

    date_input = SearchInput()
    date_input.DisplayName = "dateSearchInput"
    date_input.TemplateName = "dateSearchInput"
    date_input.DataType = "Date"
    date_input.Column = "visit_date"
    date_input.DefaultOperator = "<"
    date_input.OperatorOptional = True

    gender_literal_input = LiteralInput()
    gender_literal_input.DisplayName = "genderLiteralInput"
    gender_literal_input.TemplateName = "genderLiteralInput"
    gender_literal_input.DataType = "String"
    gender_literal_input.IsMultiChoice = True
    gender_literal_input.ChoiceQuery = "SELECT DISTINCT gender FROM syndromic_events"

    age_literal_input = LiteralInput()
    age_literal_input.DisplayName = "ageLiteralInput"
    age_literal_input.TemplateName = "ageLiteralInput"
    age_literal_input.DataType = "Number"
    age_literal_input.IsMultiChoice = True
    age_literal_input.ChoiceQuery = "SELECT DISTINCT age FROM syndromic_events"

    driver.contract.LiteralInputs.Add(race_input)
    driver.contract.LiteralInputs.Add(red_input)
    driver.contract.LiteralInputs.Add(gender_literal_input)
    driver.contract.LiteralInputs.Add(age_literal_input)
    driver.contract.SearchInputs.Add(age_input)
    driver.contract.SearchInputs.Add(gender_input)
    driver.contract.SearchInputs.Add(date_input)

    yield driver
