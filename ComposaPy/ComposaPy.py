# import sys
# import urllib
# import os
# import requests
# import json
# from json2html import *

# from CompAnalytics.Services import ApplicationService
# from CompAnalytics.Contracts import ExecutionContextOptions, OrderedModuleInputCollection
# from CompAnalytics.IServices import IApplicationServiceClient, IQueryViewServiceClient
# from CompAnalytics.IServices.Login import FormLoginScope
# from CompAnalytics.IServices.Deploy import ResourceManager, ConnectionSettings, AuthMode, WindowsLogonType

# from System.IO import FileStream, File
# from CompAnalytics.Contracts import CsvFileReference
import io
import numpy as np
import pandas as pd
import System
import System.Net
from System import String, Uri, Enum, DateTime, Type, Byte, Array, Object
from System.Collections.Generic import KeyValuePair, List, IList
from CompAnalytics import Services, Contracts, IServices, Execution, Core, Extension
from CompAnalytics.IServices import *


MAP_CS_TYPES_TO_PANDAS_TYPES = {
    "System.String": "object",
    "System.Int64": "Int64",
    "System.Int32": "Int64",
    "System.Int16": "Int64",
    "System.Double": "float64",
    "System.Decimal": "float64",
    "System.Single": "float64",
    "System.Boolean": "bool",
    "System.Guid": "object",
}


MAP_STRING_TYPES_TO_PANDAS_TYPES = {
    "CHAR": "object",
    "INTEGER": "int64",
    "INT": "int64",
    "BIGINT": "int64",
    "INT64": "int64",
    "UNSIGNED BIG INT": "int64",
    "VARCHAR": "object",
    "STRING": "object",
    "TEXT": "object",
    "FLOAT": "float64",
    "DOUBLE": "float64",
    "REAL": "float64",
    "BOOLEAN": "bool",
    "DATETIME": "datetime64",
    "DATETIMEOFFSET": "datetime64",
    "BLOB": "object",
    "OBJECT": "object",
    "GUID": "object",
}


class CsStream(io.RawIOBase):
    def __init__(self, stream):
        self.messageBodyStream = stream
        self.buffer = Array.CreateInstance(Byte, 4096)

    def read(self, size=-1):
        read_size = 4096 if size == -1 else min(size, 4096)
        number_bytes_read = self.messageBodyStream.Read(self.buffer, 0, read_size)
        # print(bytes(self.buffer)[0:number_bytes_read])
        return bytes(self.buffer)[0:number_bytes_read]

    def readable(self):
        return True


class ComposableSession:
    def __init__(self, username_or_api, password=None):

        if password == None:
            connectsettings = IServices.Deploy.ConnectionSettings()
            # connectsettings.Uri = Uri('http://ipv4.fiddler/CompApp/')
            connectsettings.Uri = Uri("http://localhost/CompApp/")
            connectsettings.AuthMode = IServices.Deploy.AuthMode.Api
            connectsettings.ApiKey = username_or_api
        else:
            form_credential = System.Net.NetworkCredential(username_or_api, password)
            connectsettings = IServices.Deploy.ConnectionSettings()
            # connectsettings.Uri = Uri('http://ipv4.fiddler/CompApp/')
            connectsettings.Uri = Uri("http://localhost/CompApp/")
            connectsettings.AuthMode = IServices.Deploy.AuthMode.Form
            connectsettings.FormCredential = form_credential
            # print(sys.path)
            # make sure to make a python.exe.config
            ## deleting the plugins link
            ## in python.exe.config , removed redirect for System.net.http
        self.connectionsettings = connectsettings
        self.ResourceManager = IServices.Deploy.ResourceManager(connectsettings)
        ## SERVICE LIST

        # print(dir(self.ResourceManager))

        self._services = {}
        for method in self.ResourceManager.AvailableServices():
            ### CompAnalytics.IServices.ISecurableResourceService -> SecurableResourceService
            service_string = str(method).split(".")[-1][1:]
            # print(str(method))
            # print(service_string)
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

    # return a queryview as a pandas dataframe
    def get_queryview(self, id):
        queryview_service = self._services["QueryViewService"]
        queryview = queryview_service.Get(id)
        queryview_data = queryview_service.RunQueryDynamic(queryview)
        column_names = []
        for column in queryview_data.ColumnDefinitions:
            column_names.append(column.Name)

        df = pd.DataFrame(queryview_data.Data)
        df.columns = column_names
        dtypes_dict = self._make_pandas_dtypes_from_list_of_column_defs(
            queryview_data.ColumnDefinitions
        )

        ## There is a pandas bug about converting objects to nullable ints, first need to convert to floats
        df.replace(to_replace=[None, "None"], value=np.nan, inplace=True)
        interim_dtypes = dtypes_dict.copy()
        for key in interim_dtypes.keys():
            if interim_dtypes[key] == "Int64":
                interim_dtypes[key] = "float"
        df = df.astype(interim_dtypes)
        return df.astype(dtypes_dict)

    def run_dataflow(self, app_id):
        """
        Runs a dataflow from the app id.
        
        Parameters
        (int) id: id of the dataflow
        
        Return
        (int) run_id: associated run id
        """

        appservice = self._services["ApplicationService"]
        app = appservice.GetApplication(app_id)

        # for i in range(len(app.Modules)):
        if not app:
            return None
        for i, module in enumerate(app.Modules):
            module = app.Modules[i]
            module.RequestingExecution = True
            app.Modules[i] = module

        execution_context = appservice.CreateExecutionContext(
            app, Contracts.ExecutionContextOptions()
        )
        app_ran = appservice.RunExecutionContext(execution_context)

        return execution_context.Id

    def run_status(self, run_id):
        """
        Checks status of a run.
        
        Parameters
        (int) run_id: id of the run
        
        Return
        (int) run_id: associated run id
        """
        run = self._services["ApplicationService"].GetRun(run_id)
        return System.Enum.GetNames(Contracts.ExecutionStatus)[run.Status]

    def wait_for_run_execution(self, run_id):
        """
        Waits until run has finished.
        
        Parameters
        (int) run_id: id of the run
        
        Return
        (string) execution_status: status of the execution
        """
        run = self._services["ApplicationService"].GetRun(run_id)
        if run.Status == Contracts.ExecutionStatus.Running:
            self._services["ApplicationService"].WaitForExecutionContext(run.Handle)
        execution_names = System.Enum.GetNames(Contracts.ExecutionStatus)

        output = {}
        output["execution_status"] = execution_names[
            self._services["ApplicationService"].GetRun(run_id).Status
        ]
        output["run_id"] = run_id
        return output

    def get_run_modules(self, run_id):
        """
        Get list of modules of a run.
        
        Parameters
        (int) app_id: id of the app.
        
        Return
        (list) modules: list of modules.
        """
        app = self._services["ApplicationService"].GetRun(run_id).Application
        list_of_modules = app.Modules
        modules_by_id = {}

        for module in list_of_modules:
            curr_module_values = {}
            curr_module_values["Name"] = module.Name
            curr_module_values["ModuleType"] = module.ModuleType.Name
            curr_module_values["Id"] = module.Id

            module_outputs_names = list(module.ModuleOutputs.Indexes.Keys)
            # print(module_outputs_names)
            module_inputs_names = list(module.ModuleInputs.Indexes.Keys)

            module_outputs = {}
            for name in module_outputs_names:
                module_outputs[name] = module.ModuleOutputs.GetItemForKey(name).ValueObj

            module_inputs = {}
            for name in module_inputs_names:
                module_inputs[name] = module.ModuleInputs.GetItemForKey(name).ValueObj

            curr_module_values["ModuleOutputValues"] = module_outputs
            curr_module_values["ModuleInputValues"] = module_inputs

            modules_by_id[module.Id] = curr_module_values

        # acm = Execution.ApplicationConnectionManager(app)

        output = list(modules_by_id.values())
        return output

    def import_app_from_json(self, json):
        """
        import and save app from a json string of an app.
        
        Parameters
        (string) json: json string of app.
        
        Return
        (id) app_id: the id of the app.
        """
        appStr = System.IO.File.ReadAllText(json)
        # print(appStr)
        app = self._services["ApplicationService"].ImportApplicationFromString(appStr)
        saved_app = self._services["ApplicationService"].SaveApplication(app)
        return saved_app.Id

    def queryview_from_id_direct(self, queryview_id):
        """
        Read a queryview from id to a pandas dataframe
        
        Parameters
        (int) id: queryview id.
        
        Return
        (Pandas.DataFrame) df: DataFrame of Queryview.
        """
        queryview = self._services["QueryViewService"].Get(queryview_id)
        queryview_data = self._services["QueryViewService"].RunQueryDynamic(queryview)
        columns_definitions = queryview_data.ColumnDefinitions
        column_names = []
        column_dtypes = {}

        for column_definition in columns_definitions:
            if not column_definition.Exclude:
                column_names.append(column_definition.Name)
                column_dtypes[column_definition.Name] = MAP_CS_TYPES_TO_PANDAS_TYPES[
                    column_definition.Type
                ]

        data = queryview_data.Data
        df = pd.DataFrame(data)
        df.columns = column_names
        # print(column_dtypes
        print(df.head())
        print(column_dtypes)
        return df.astype(column_dtypes)

    def queryview_from_id(self, queryview_id):
        """
        Read a queryview from id to a pandas dataframe
        
        Parameters
        (int) id: queryview id.
        
        Return
        (Pandas.DataFrame) df: DataFrame of Queryview.
        """
        queryview = self._services["QueryViewService"].Get(queryview_id)
        paging_options = queryview.PagingOptions
        # print(paging_options.PageNum)
        # print(paging_options.PageLimit)
        paging_options.PageNum = 1
        paging_options.PageLimit = 0x7FFFFFFF
        queryview.PagingOptions = paging_options
        stream = self._services["QueryViewService"].GetQueryResultsDownloadWeb(
            queryview, "csv"
        )
        df = pd.read_csv(CsStream(stream))

        ## convert datetime by regex
        mask = df.astype(str).apply(
            lambda x: x.str.match(r"(\d{2,4}-\d{2}-\d{2,4})+").all()
        )
        df.loc[:, mask] = df.loc[:, mask].apply(pd.to_datetime)

        return df

    def convert_table_to_pandas(self, table):
        table_results = self._services["TableService"].GetResultFromTable(
            table, 0, 0x7FFFFFFF
        )
        headers = table_results.Headers
        results = table_results.Results
        df = pd.DataFrame(results)
        df.columns = headers

        dtypes_dict = self._make_pandas_dtypes_dict(table.Columns)
        for key in dtypes_dict.keys():
            if dtypes_dict[key] == "float64":
                df[key] = df[key].apply(lambda x: System.Decimal.ToDouble(x))

        # table_column_dict = table.Columns.Dictionary
        # for key in table.Columns.Dictionary.Keys:
        #    column = table_column_dict[key]
        #    if column.Type == "DATETIMEOFFSET":
        #        dtypes_dict[column.Name] = 'datetime64'

        return df.astype(dtypes_dict)

    def _make_pandas_dtypes_dict(self, table_columns):
        dtypes_dict = dict()
        for key in table_columns.Dictionary.Keys:
            column = table_columns.Dictionary[key]
            dtypes_dict[column.Name] = MAP_STRING_TYPES_TO_PANDAS_TYPES[column.Type]
        return dtypes_dict

    def _make_pandas_dtypes_from_list_of_column_defs(self, list_of_column_defs):
        dtypes_dict = dict()
        for column_def in list_of_column_defs:
            dtypes_dict[column_def.Name] = MAP_CS_TYPES_TO_PANDAS_TYPES[column_def.Type]
        return dtypes_dict

    @staticmethod
    def _input_default(module, value):
        moduleinput = module.ModuleInputs.GetItemForKey("Input")
        moduleinput.ValueObj = value
        module.ModuleInputs.Remove("Input")
        module.ModuleInputs.Add(moduleinput)

    @staticmethod
    def _upload_file(execHandle, moduleHandle, inputHandle, fileName):
        moduleinput = module.ModuleInputs.GetItemForKey("Input")
        moduleinput.ValueObj = value
        module.ModuleInputs.Remove("Input")
        module.ModuleInputs.Add(moduleinput)

    @staticmethod
    def _input_table(module, value):
        moduleinput = module.ModuleInputs.GetItemForKey("Input")
        moduleinput.ValueObj = value
        module.ModuleInputs.Remove("Input")
        module.ModuleInputs.Add(moduleinput)

    def _upload_file(self, file_path, execution_context):
        uri = self.ResourceManager.CreateServiceEndpointUri("FileUploadService")
        print(dir(self.ResourceManager))
        uploadResult = FileUploadClient.UploadFile(
            self.ResourceManager.Login,
            execution_context,
            fileUploader.UiHandle,
            fileInput.UiHandle,
            filePath,
        )
        return uploadResult

    def run_dataflow_with_inputs(self, app_id, dict_of_inputs):
        app = self._services["ApplicationService"].GetApplication(app_id)
        for i in range(len(app.Modules)):
            module = app.Modules[i]
            module.RequestingExecution = True

            if "External" in module.ModuleType.Name:

                inpt = next(inpt for inpt in module.ModuleInputs if inpt.Name == "Name")
                if inpt.ValueObj in dict_of_inputs.keys():
                    # print('hello')

                    method_to_call = {
                        "External Double Input": ComposableSession._input_default,
                        "External Bool Input": ComposableSession._input_default,
                        "External Int Input": ComposableSession._input_default,
                        "External String Input": ComposableSession._input_default,
                        "External Line Input": ComposableSession._input_default,
                        "External File Input": ComposableSession._input_default,
                    }

                    # method = method_to_call

                    if module.ModuleType.Name in method_to_call.keys():
                        method_to_call[module.ModuleType.Name](
                            module, dict_of_inputs[inpt.ValueObj]
                        )

                    # moduleinput = module.ModuleInputs.GetItemForKey('Input')
                    # moduleinput.ValueObj = dict_of_inputs[inpt.ValueObj]
                    # module.ModuleInputs.Remove('Input')
                    # module.ModuleInputs.Add(moduleinput)

            app.Modules[i] = module

        execution_context = self._services["ApplicationService"].CreateExecutionContext(
            app, Contracts.ExecutionContextOptions()
        )

        ## stream up the files
        for i in range(len(app.Modules)):
            if app.Modules[i].ModuleType.Name == "External File Input":
                fileUploader = app.Modules[i]

                fileInputName = next(
                    inpt for inpt in fileUploader.ModuleInputs if inpt.Name == "Name"
                )

                if fileInputName.ValueObj in dict_of_inputs.keys():
                    fileInput = next(
                        inpt
                        for inpt in fileUploader.ModuleInputs
                        if inpt.Name == "Input"
                    )

                    filePath = dict_of_inputs[fileInputName.ValueObj]

                    # val = self._upload_file(filePath,execution_context)
                    # print(val)
                    # print(self._services['FileUploadService'].UploadFile(stream))
                    uri = self.ResourceManager.CreateServiceEndpointUri(
                        "FileUploadService"
                    )

                    uploadResult = FileUploadClient.UploadFile(
                        uri,
                        self.ResourceManager.Login,
                        execution_context,
                        fileUploader.UiHandle,
                        fileInput.UiHandle,
                        filePath,
                    )
                    # print(uploadResult)

        ## stream up the tables
        for i in range(len(app.Modules)):
            if app.Modules[i].ModuleType.Name == "External Table Input":
                fileUploader = app.Modules[i]

                fileInputName = next(
                    inpt for inpt in fileUploader.ModuleInputs if inpt.Name == "Name"
                )
                # print(fileInputName.ValueObj)
                if fileInputName.ValueObj in dict_of_inputs.keys():

                    df = dict_of_inputs[fileInputName.ValueObj]
                    # headers = list(df.columns)
                    # rows = [[1,2],[3,4]]
                    # types = [str,str]

                    headers = List[String](list(df.columns))
                    rows = List[List[Object]]([[1, 2], [3, 4]])
                    types = List[Type]([str, str])

                    # headers = IList[String](list(df.columns))
                    # rows = IList[IList[String]]([["1","2"],["3","4"]])
                    # types = IList[Type]([str,str])

                    # headers = List[String]()
                    # rows = List[List[Object]]()
                    # types = List[Type]()

                    # print(dir(Extension.Tables.CreateTableExecutor))
                    # table = self._services['TableService'].CreateTableFromStream(execution_context)
                    table = Extension.Tables.CreateTableExecutor.CreateTablePython(
                        headers, rows, types, execution_context
                    )

                    ComposableSession._input_default(module, table)

        app_ran = self._services["ApplicationService"].RunExecutionContext(
            execution_context
        )
        # print(comp_session.get_run_modules(execution_context.Id))
        return execution_context.Id

    def get_run_info(self, id):
        return
