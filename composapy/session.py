from __future__ import annotations
from typing import Optional
import os
from types import SimpleNamespace
import requests

from composapy.config import write_config_session
from composapy.auth import AuthMode
from composapy._transport.client import ServiceClient
from composapy._transport.proxy import ServiceProxy, load_operations
from composapy.exceptions import (
    InvalidAuthModeAction,
    SessionException,
    UriNotConfiguredError,
    InvalidTokenConfigError,
    InvalidFormConfigError,
    InvalidWindowsConfigError,
    SessionRegistrationException,
    CONNECTION_ERROR_MESSAGE,
)


class Session:
    """A valid, registered, session is required to access and use Composable resources.

    .. highlight:: python
    .. code-block:: python

            from composapy.session import Session
            from composapy.auth import AuthMode
    """

    @property
    def property_service(self) -> ServiceProxy:
        return self.services["PropertyService"]

    @property
    def app_service(self) -> ServiceProxy:
        return self.services["ApplicationService"]

    @property
    def table_service(self) -> ServiceProxy:
        return self.services["TableService"]

    @property
    def file_upload_service(self) -> ServiceProxy:
        return self.services["FileUploadService"]

    @property
    def queryview_service(self) -> ServiceProxy:
        return self.services["QueryViewService"]

    @property
    def resource_manager(self) -> _ResourceManager:
        return self.ResourceManager

    @property
    def uri(self) -> str:
        """Sometimes referred to as 'application uri'."""
        return str(self.connection_settings.Uri)

    @property
    def auth_mode(self) -> AuthMode:
        """The current auth mode associated with this Session object instance."""
        return self._auth_mode

    def __init__(
        self,
        uri: str = None,
        auth_mode: AuthMode = AuthMode.WINDOWS,
        credentials=None,
    ):
        """Composapy looks for the environment variable `APPLICATION_URI` by default
        (set by DataLabs). If you are using Composapy outside of the DataLabs environment and
        the `APPLICATION_URI` environment variable is not set, you can set it with keyword
        argument `uri`. You can create a session with Windows Authentication (if you are in a
        DataLab, this will be the same as the key on the DataLab edit screen), a string API Token
        (can be generated on the Composable website), or with a string tuple containing username
        and password.

        .. highlight:: python
        .. code-block:: python

            session = Session(auth_mode=AuthMode.WINDOWS)                                                                           # Windows Auth
            session = Session(auth_mode=AuthMode.TOKEN, credentials="<your-api-token-here>", uri="http://localhost/CompAnalytics/") # Token
            session = Session(auth_mode=AuthMode.FORM, credentials=("username", "password"))                                        # Form

            session.register()  # register your session so that composapy uses this
            session.register(save=True)  # optionally, save for autoload with configuration file "composapy.ini"

        :param uri: The Composable application uri used to access your resources. If using
            Composapy within DataLabs, uses the environment variable "APPLICATION_URI" that it sets
            during DataLabs startup. Setting the uri kwarg will override the usage of this
            environment variable.
        :param auth_mode: options are - AuthMode.WINDOWS (default), AuthMode.FORM, AuthMode.TOKEN
        :param credentials: The credentials for your specified auth_mode. WINDOWS uses the
            DataLab user credentials automatically (will raise error if any credentials are given),
            FORM takes a tuple of (username, password), and TOKEN takes a string token that can be
            generated in the Composable application.
        """
        if not isinstance(auth_mode, AuthMode):
            raise TypeError(
                f"auth_mode must be an AuthMode, not {type(auth_mode).__name__}."
            )

        if uri is None and os.environ.get("APPLICATION_URI") is None:
            raise UriNotConfiguredError(
                "A uri must be configured by either setting an "
                "environment variable named APPLICATION_URI, "
                "or by passing it to the Session "
                "initialization kwargs."
            )

        if auth_mode == AuthMode.WINDOWS and credentials:
            raise InvalidWindowsConfigError(
                "AuthMode.WINDOWS authorization does not "
                "use any credentials kwarg input value, "
                "and expected credentials input to be (None), "
                "but instead received credentials, which are not "
                "accepted for this mode (their values are not shown). Please "
                "remove any credentials input values if using AuthMode.WINDOWS "
                "authentication scheme."
            )

        if auth_mode == AuthMode.TOKEN and not isinstance(credentials, str):
            raise InvalidTokenConfigError(
                "For AuthMode.TOKEN authorization, "
                "you must pass a string (token) value to the "
                "credentials initialization kwargs."
            )

        if auth_mode == AuthMode.FORM and (
            not isinstance(credentials, tuple) or len(credentials) != 2
        ):
            raise InvalidFormConfigError(
                "For AuthMode.FORM authorization, "
                "you must pass a tuple (username, password) value to the "
                "credentials initialization kwargs."
            )

        uri = uri if uri is not None else os.getenv("APPLICATION_URI")
        if not uri.endswith("/"):
            uri += "/"

        self._auth_mode = auth_mode
        self._credentials = credentials

        self.connection_settings = SimpleNamespace(Uri=uri, AuthMode=auth_mode)

        self.ResourceManager = _ResourceManager(self)

        self._client = ServiceClient(uri, auth_mode, credentials)
        self.services = {
            name: ServiceProxy(self._client, name) for name in load_operations()
        }

    @classmethod
    def clear_registration(cls) -> None:
        """Used to unregister the currently registered session.

        .. highlight:: python
        .. code-block:: python

            Session.clear_registration()
        """
        singleton = _SessionSingleton()
        singleton.session = None

    def register(self, save=False) -> None:
        """Used to register a class instance of session that is used implicitly across the
        kernel. Only one session can registered at a time.

        .. highlight:: python
        .. code-block:: python

            session = Session(auth_mode=AuthMode.WINDOWS)
            session.register(save=True)

        :param save: If true, saves configuration in local composapy.ini file. Default is false.
        """
        singleton = _SessionSingleton()
        singleton.session = self

        if save:
            write_config_session(self)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def handle_connection_exception(e):
    """Turn a connection failure into the friendly ConnectionError; anything else is left alone."""
    if isinstance(e, requests.ConnectionError):
        raise ConnectionError(CONNECTION_ERROR_MESSAGE) from None


def get_session(raise_exception=True) -> Optional[Session]:
    """Used to get the current registered Session object.

    .. highlight:: python
    .. code-block:: python

        from composapy.session import Session, get_session
        Session(auth_mode=Session.AuthMode.WINDOWS).register()
        session = get_session()  # can use this anywhere on running kernel

    :return: the currently registered session
    """
    singleton = _SessionSingleton()
    if singleton.session is None and raise_exception:
        raise SessionRegistrationException("No session currently registered.")
    return singleton.session


class _SessionSingleton:
    session = None

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance


class _ResourceManager:

    def __init__(self, session):
        self._session = session

    def AvailableServices(self):
        return list(load_operations())

    def CreateServiceEndpointUri(self, name):
        return f"{self._session.uri}Services/{name}.svc"

    def Dispose(self):
        self._session.close()
