import System
import System.Net
from System import Uri
from CompAnalytics import IServices
from CompAnalytics.IServices import *


class Session:
    """Holds connection and binding state for composapy api usage.
    """

    def __init__(
        self, username_or_api: str, password: str = None,
    ):
        self._connect_and_setup_bindings(username_or_api, password)

    def _connect_and_setup_bindings(self, username_or_api, password):
        if password == None:
            self.connection_settings = IServices.Deploy.ConnectionSettings()
            self.connection_settings.Uri = Uri("http://localhost/CompApp/")
            self.connection_settings.AuthMode = IServices.Deploy.AuthMode.Api
            self.connection_settings.ApiKey = username_or_api
        else:
            form_credential = System.Net.NetworkCredential(username_or_api, password)
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
