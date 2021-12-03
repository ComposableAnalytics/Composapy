import System
import System.Net
from System import Uri
from CompAnalytics import IServices
from CompAnalytics.IServices import *


class Session:
    """Holds connection and binding state for composapy api usage."""

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

    def __init__(
        self,
        user_or_token: str,
        password: str = None,
    ):
        self._connect_and_setup_bindings(user_or_token, password)

    def _connect_and_setup_bindings(self, user_or_token, password):
        if not password:
            self.connection_settings = IServices.Deploy.ConnectionSettings()
            self.connection_settings.Uri = Uri("http://localhost/CompApp/")
            self.connection_settings.AuthMode = IServices.Deploy.AuthMode.Api
            self.connection_settings.ApiKey = user_or_token
        else:
            form_credential = System.Net.NetworkCredential(user_or_token, password)
            self.connection_settings = IServices.Deploy.ConnectionSettings()
            self.connection_settings.Uri = Uri("http://localhost/CompApp/")
            self.connection_settings.AuthMode = IServices.Deploy.AuthMode.Form
            self.connection_settings.FormCredential = form_credential

        self.ResourceManager = IServices.Deploy.ResourceManager(
            self.connection_settings
        )
        self.services = {}
        for method in self.ResourceManager.AvailableServices():
            service_string = str(method).split(".")[-1][1:]
            try:
                self.services[service_string] = self.ResourceManager.CreateAuthChannel[
                    method
                ](service_string)
            except:
                self.services[
                    service_string
                ] = self.ResourceManager.CreateAuthChannelNoWebScripting[method](
                    service_string
                )
