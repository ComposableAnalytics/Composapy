import os
import pytest
from pathlib import Path, PureWindowsPath
from dotenv import load_dotenv
import warnings
import json
import uuid
from datetime import datetime, timedelta, timezone

# does not override environment variables, this is essentially a failsafe for local dev environment
for env_file in sorted(Path().rglob(".test*.env")):
    load_dotenv(env_file)

FIXTURE_DIR: Path = Path(os.path.join(os.path.dirname(os.path.realpath(__file__))))
LOCAL_FILES_DIR: Path = FIXTURE_DIR.joinpath(".local_files")
os.environ["COMPOSAPY_INI_DIR"] = str(LOCAL_FILES_DIR)


def _clean_testing_local_files():
    LOCAL_FILES_DIR.mkdir(exist_ok=True)
    for child in LOCAL_FILES_DIR.iterdir():
        if child.is_file():
            child.unlink()


_clean_testing_local_files()

from composapy.dataflow.api import DataFlow
from composapy.queryview.api import QueryView
from composapy.session import Session, get_session
from composapy.key.models import KeyObject, get_key_object
from composapy.queryview.models import QueryViewObject, QueryViewPagedObject
from composapy.key.api import Key
from composapy.auth import AuthMode
from composapy._wire.objects import ContractObject
from composapy.contracts.file_reference import FileReference
from composapy.contracts.queryview import LiteralInput, SearchInput


class TestSetupException(Exception):
    pass


class InvalidTestConfigError(TestSetupException):
    pass


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
        "TEST_API_KEY is not set in the environment or in a .test*.env file. A temporary api key will "
        "be created with your (TEST_USERNAME, TEST_PASSWORD) for this test run, but will not be "
        "saved. To remove this warning -- add a valid TEST_API_KEY to tests/.test.local.env."
    )

    session = create_form_auth_session()  # registers a Form session
    user_service = session.services["UserService"]
    user = user_service.GetCurrentUser()
    expires = datetime.now(timezone.utc) + timedelta(
        days=3
    )  # written as /Date(ms)/, as the DateTime? parameter needs
    api_key = user_service.GenerateUserToken(
        user.Id, user.UserName, "DataLab Unit Test", expires
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


@pytest.fixture(scope="module", autouse=True)
def windows_auth(request):
    # Inside a DataLab the C# suites manage IIS, and they copy only the test files and conftest.py into its working
    # directory, so conftest.py is a top-level module there and iis.py is not beside it. iis is imported here, where
    # tox runs it with `tests` as a package, and nowhere else.
    if "test_windows_auth.py" not in request.keywords or os.getenv(
        "JUPYTER_ENVIRONMENT_FLAG"
    ):
        yield
    else:
        from .iis import windows_auth_enabled

        with windows_auth_enabled(os.getenv("APPLICATION_URI")):
            yield


@pytest.fixture
def session(request):
    creators = {
        "Windows": create_windows_auth_session,
        "Form": create_form_auth_session,
        "Token": create_token_auth_session,
    }
    created = creators[request.param]()
    try:
        yield created
    finally:
        created.close()


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


SQL_TYPE = (
    "CompAnalytics.Extension.Sql.SqlConnectionSettings, CompAnalytics.Extension.Sql, "
    "Version=1.0.0.0, Culture=neutral, PublicKeyToken=792cfbd70dcd13a9"
)


def make_sql_property(
    name, host, username, password, database=None, port=None, connection_parameters=None
):
    settings = {
        "Password": password,
        "ConnectionParameters": connection_parameters or [],
        "Database": database,
        "Host": host,
        "Port": port,
        "Username": username,
        "UseMultipleActiveResultSets": None,
    }
    return ContractObject(
        [
            ("__type", "Property:#CompAnalytics.Contracts"),
            ("AssemblyQualifiedType", SQL_TYPE),
            ("DisplayType", "SqlConnectionSettings"),
            ("DisplayTypeName", "Database Connection Settings"),
            ("Name", name),
            ("Value", json.dumps(settings)),
            ("EnvironmentValues", []),
        ]
    )


@pytest.fixture
def property():
    create_form_auth_session()
    property_service = get_session().property_service

    property = make_sql_property(
        uuid.uuid4().hex, "host.com", "user", "password", port=1234
    )

    saved_property = property_service.SaveProperty(property)

    yield saved_property

    property_service.DeleteProperty(saved_property.Id)


@pytest.fixture
def default_health_key_object() -> KeyObject:
    create_form_auth_session()
    property_service = get_session().property_service

    # A name of its own, so a run that died before it cleaned up, or another run on the same server, can't collide with it
    property = make_sql_property(
        f"Test Health Db Key {uuid.uuid4().hex}",
        ".",
        "CompAnalyticsPublicUser",
        "c0mpanalytics!",
        database="Health",
        connection_parameters=[{"Key": "TrustServerCertificate", "Value": "yes"}],
    )

    saved_property = property_service.SaveProperty(property)

    try:
        yield Key.get(saved_property.Id)
    finally:
        # A test may have registered the Key, and it is about to stop existing
        registered = get_key_object(raise_exception=False)
        if registered is not None and registered.id == saved_property.Id:
            KeyObject.clear_registration()
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
def file_ref(request):
    file_path = Path(os.path.dirname(Path(__file__)), "TestFiles", request.param)
    file_ref = FileReference.CreateWithAbsoluteUri(str(file_path), file_path.as_uri())
    return file_ref


@pytest.fixture
def queryview_driver(default_health_key_object) -> QueryViewObject:
    yield QueryView.driver(default_health_key_object)


@pytest.fixture
def queryview_driver_interactive(default_health_key_object) -> QueryViewPagedObject:
    yield QueryView.driver(default_health_key_object, interactive=True)


def new_input(kind, **members):
    factory = SearchInput if kind == "SearchInput" else LiteralInput
    return factory(**members)


@pytest.fixture
def queryview_input_driver(default_health_key_object) -> QueryViewObject:
    driver = QueryView.driver(default_health_key_object)

    # set up literal/search inputs
    race_input = new_input(
        "LiteralInput",
        DisplayName="raceLiteralInput",
        TemplateName="raceLiteralInput",
        DataType="String",
        Default="White",
    )

    red_input = new_input(
        "LiteralInput",
        DisplayName="redLiteralInput",
        TemplateName="redLiteralInput",
        DataType="Boolean",
        Default="true",
    )

    age_input = new_input(
        "SearchInput",
        DisplayName="ageSearchInput",
        TemplateName="ageSearchInput",
        DataType="Number",
        Column="age",
        Default="50",
        DefaultOperator=">",
    )

    gender_input = new_input(
        "SearchInput",
        DisplayName="genderSearchInput",
        TemplateName="genderSearchInput",
        DataType="String",
        Column="gender",
        Default="M",
        DefaultOperator="=",
        OperatorOptional=True,
    )

    date_input = new_input(
        "SearchInput",
        DisplayName="dateSearchInput",
        TemplateName="dateSearchInput",
        DataType="Date",
        Column="visit_date",
        DefaultOperator="<",
        OperatorOptional=True,
    )

    gender_literal_input = new_input(
        "LiteralInput",
        DisplayName="genderLiteralInput",
        TemplateName="genderLiteralInput",
        DataType="String",
        IsMultiChoice=True,
        ChoiceQuery="SELECT DISTINCT gender FROM syndromic_events",
    )

    age_literal_input = new_input(
        "LiteralInput",
        DisplayName="ageLiteralInput",
        TemplateName="ageLiteralInput",
        DataType="Number",
        IsMultiChoice=True,
        ChoiceQuery="SELECT DISTINCT age FROM syndromic_events",
    )

    driver.contract.LiteralInputs.append(race_input)
    driver.contract.LiteralInputs.append(red_input)
    driver.contract.LiteralInputs.append(gender_literal_input)
    driver.contract.LiteralInputs.append(age_literal_input)
    driver.contract.SearchInputs.append(age_input)
    driver.contract.SearchInputs.append(gender_input)
    driver.contract.SearchInputs.append(date_input)

    yield driver
