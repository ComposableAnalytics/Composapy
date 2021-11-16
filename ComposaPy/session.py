import System
import System.Net
from System import Uri
from CompAnalytics import IServices
from CompAnalytics.IServices import *


class Session:
    """Use as initialization parameter for any class contained within an api.py file."""

    def __init__(self, username_or_api, password=None):
        if password == None:
            connection_settings = IServices.Deploy.ConnectionSettings()
            connection_settings.Uri = Uri("http://localhost/CompApp/")
            connection_settings.AuthMode = IServices.Deploy.AuthMode.Api
            connection_settings.ApiKey = username_or_api
        else:
            form_credential = System.Net.NetworkCredential(username_or_api, password)
            connection_settings = IServices.Deploy.ConnectionSettings()
            connection_settings.Uri = Uri("http://localhost/CompApp/")
            connection_settings.AuthMode = IServices.Deploy.AuthMode.Form
            connection_settings.FormCredential = form_credential

        self.connection_settings = connection_settings
        self.ResourceManager = IServices.Deploy.ResourceManager(connection_settings)

        self._services = {}
        for method in self.ResourceManager.AvailableServices():
            service_string = str(method).split(".")[-1][1:]
            try:
                self._services[service_string] = self.ResourceManager.CreateAuthChannel[
                    method
                ](service_string)
            except:
                self._services[
                    service_string
                ] = self.ResourceManager.CreateAuthChannelNoWebScripting[method](
                    service_string
                )
