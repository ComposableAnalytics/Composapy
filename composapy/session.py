from __future__ import annotations

import os
from enum import Enum

from System import Uri, Net
from CompAnalytics import IServices


class Session:
    """A valid, registered, session is required to access and use Composable resources.

    .. highlight:: python
    .. code-block:: python

            from composapy.session import Session
    """

    class AuthMode(Enum):
        """
        - TOKEN
        - FORM
        - WINDOWS
        """

        TOKEN = "Token"
        FORM = "Form"
        WINDOWS = "Windows"

    @property
    def property_service(self) -> IServices.IPropertyService:
        """A Composable csharp binding to the IServices.IPropertyService."""
        return self.services["PropertyService"]

    @property
    def app_service(self) -> IServices.IApplicationService:
        """A Composable csharp binding to the IServices.IApplicationService."""
        return self.services["ApplicationService"]

    @property
    def table_service(self) -> IServices.ITableService:
        """A Composable csharp binding to the IServices.ITableService object."""
        return self.services["TableService"]

    @property
    def file_upload_service(self) -> IServices.IFileUploadService:
        """A Composable csharp binding to the IServices.IFileUploadService object."""
        return self.services["FileUploadService"]

    @property
    def resource_manager(self) -> IServices.Deploy.ResourceManager:
        """A Composable csharp binding to the IServices.Deploy.ResourceManager object."""
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

            session = Session(auth_mode=Session.AuthMode.WINDOWS)                                                                           # Windows Auth
            session = Session(auth_mode=Session.AuthMode.TOKEN, credentials="<your-api-token-here>", uri="http://localhost/CompAnalytics/") # Token
            session = Session(auth_mode=Session.AuthMode.FORM, credentials=("username", "password"))                                        # Form

            session.register()  # register your session so that composapy uses this

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
        if uri is None and os.environ.get("APPLICATION_URI") is None:
            raise UriNotConfiguredError(
                "A uri must be configured by either setting an "
                "environment variable named APPLICATION_URI, "
                "or by passing it to the Session "
                "initialization kwargs."
            )

        if auth_mode == Session.AuthMode.WINDOWS and credentials:
            raise InvalidWindowsConfigError(
                "AuthMode.WINDOWS authorization does not "
                "use any credentials kwarg input value, "
                "and expected credentials input to be (None), "
                f"but instead received ({credentials}). Please "
                "remove any credentials input vaules if using AuthMode.WINDOWS "
                "authentication scheme."
            )

        if auth_mode == Session.AuthMode.TOKEN and not isinstance(credentials, str):
            raise InvalidTokenConfigError(
                "For AuthMode.TOKEN authorization, "
                "you must pass a string (token) value to the"
                "credentials initialization kwargs."
            )

        if auth_mode == Session.AuthMode.FORM and (
            not isinstance(credentials, tuple) or len(credentials) != 2
        ):
            raise InvalidFormConfigError(
                "For AuthMode.FORM authorization, "
                "you must pass a tuple (username, password) value to the"
                "credentials initialization kwargs."
            )

        uri = uri if uri is not None else os.getenv("APPLICATION_URI")
        self._auth_mode = auth_mode

        self.connection_settings = IServices.Deploy.ConnectionSettings()
        self.connection_settings.Uri = Uri(uri)

        if auth_mode == Session.AuthMode.TOKEN:
            self.connection_settings.AuthMode = IServices.Deploy.AuthMode.Api
            self.connection_settings.ApiKey = credentials

        elif auth_mode == Session.AuthMode.FORM:
            self.connection_settings.AuthMode = IServices.Deploy.AuthMode.Form
            self.connection_settings.FormCredential = Net.NetworkCredential(
                credentials[0], credentials[1]
            )

        elif auth_mode == Session.AuthMode.WINDOWS:
            self.connection_settings.AuthMode = IServices.Deploy.AuthMode.Windows

        self.ResourceManager = IServices.Deploy.ResourceManager(
            self.connection_settings
        )

        self.services = {}
        for method in self.ResourceManager.AvailableServices():
            method_name = self._get_method_name(method)
            try:
                self.services[method_name] = self.ResourceManager.CreateAuthChannel[
                    method
                ](method_name)

            except:
                self.services[
                    method_name
                ] = self.ResourceManager.CreateAuthChannelNoWebScripting[method](
                    method_name
                )

    @classmethod
    def clear_registration(cls) -> None:
        """Used to unregister the currently registered session.

        .. highlight:: python
        .. code-block:: python

            Session.clear_registration()
        """
        singleton = _SessionSingleton()
        singleton.session = None

    def register(self) -> None:
        """Used to register a class instance of session that is used implicitly across the
        kernel. Only one session can registered at a time.

        .. highlight:: python
        .. code-block:: python

            session = Session(auth_mode=Session.AuthMode.WINDOWS)
            session.register()
        """
        singleton = _SessionSingleton()
        singleton.session = self

    @staticmethod
    def _get_method_name(method):
        return str(method).split(".")[-1][1:]


def get_session() -> Session:
    """Used to get the current registered Session object.

    .. highlight:: python
    .. code-block:: python

        from composapy.session import Session, get_session
        Session(auth_mode=Session.AuthMode.WINDOWS).register()
        session = get_session()  # can use this anywhere on running kernel

    :return: the currently registered session
    """
    singleton = _SessionSingleton()
    if singleton.session is None:
        raise SessionRegistrationException("No session currently registered.")
    return singleton.session


class _SessionSingleton:
    session = None

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance


class SessionException(Exception):
    pass


class UriNotConfiguredError(SessionException):
    pass


class InvalidTokenConfigError(SessionException):
    pass


class InvalidFormConfigError(SessionException):
    pass


class InvalidWindowsConfigError(SessionException):
    pass


class InvalidAuthModeAction(SessionException):
    pass


class SessionRegistrationException(SessionException):
    pass
