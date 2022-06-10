from __future__ import annotations

import os
from enum import Enum

from System import Uri, Net
from CompAnalytics import IServices


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


class Session:
    """Holds connection and binding state for composapy api usage."""

    class AuthMode(Enum):
        TOKEN = "Token"
        FORM = "Form"
        WINDOWS = "Windows"

    @property
    def app_service(self) -> IServices.IApplicationService:
        """A composable analytics csharp binding to the IServices.IApplicationService (otherwise
        known as a dataflow service) object.
        """
        return self.services["ApplicationService"]

    @property
    def table_service(self) -> IServices.ITableService:
        """A composable analytics csharp binding to the IServices.ITableService object."""
        return self.services["TableService"]

    @property
    def file_upload_service(self) -> IServices.IFileUploadService:
        """A composable analytics csharp binding to the IServices.IFileUploadService object."""
        return self.services["FileUploadService"]

    @property
    def resource_manager(self) -> IServices.Deploy.ResourceManager:
        """A composable analytics csharp binding to the IServices.Deploy.ResourceManager object."""
        return self.ResourceManager

    @property
    def api_token(self) -> str:
        if self.auth_mode is not Session.AuthMode.TOKEN:
            raise InvalidAuthModeAction(
                f"Authentication type {self.auth_mode} does not use an api token."
            )
        return self._api_token

    @property
    def uri(self) -> str:
        return str(self.connection_settings.Uri)

    @property
    def auth_mode(self) -> AuthMode:
        return self._auth_mode

    def __init__(
        self,
        uri: str = None,
        auth_mode: AuthMode = AuthMode.WINDOWS,
        credentials=None,
    ):
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
        self._api_token = (
            str(credentials) if auth_mode == Session.AuthMode.TOKEN else None
        )

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
            method_name = self.get_method_name(method)
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

    @staticmethod
    def get_method_name(method):
        return str(method).split(".")[-1][1:]
