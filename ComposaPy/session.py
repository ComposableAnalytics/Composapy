import System
import System.Net
from System import Uri, Byte, Array
from CompAnalytics import IServices
from CompAnalytics.IServices import *

import io


class CsStream(io.RawIOBase):
    def __init__(self, stream):
        self.messageBodyStream = stream
        self.buffer = Array.CreateInstance(Byte, 4096)

    def read(self, size=-1):
        read_size = 4096 if size == -1 else min(size, 4096)
        number_bytes_read = self.messageBodyStream.Read(self.buffer, 0, read_size)
        return bytes(self.buffer)[0:number_bytes_read]

    def readable(self):
        return True


class Session:
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
