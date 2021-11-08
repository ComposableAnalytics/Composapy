import importlib
import pandas as pd
import sys
from time import time


import unittest

ca = importlib.import_module('ComposaPy')
import clr
clr.AddReference(r'C:\Users\Mike\source\Workspaces\Composable Analytics\Product\CompAnalytics.Contracts\bin\Debug\CompAnalytics.Contracts.dll')
from CompAnalytics.Contracts import CsvFileReference

path_to_unit_test_data = 'C:\\Users\\Mike\\source\\Workspaces\\Composable Analytics\\Product\\UnitTests\\TestData\\'
api_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbklkIjoiYmU2YmM0YzUtZWQ0MS00NjhjLWI5MTUtYzY1ZTFiY2NhMTY3IiwiaWF0IjoxNjM1NzkyNjg4LCJpc3MiOiJDb21wb3NhYmxlQW5hbHl0aWNzIiwiYXVkIjoiQ29tcG9zYWJsZUFuYWx5dGljcyJ9.v8nZTSJQ8DfgWXHhA5O5CRw7QcV1ejtMA8XSHbBgSQw'
user = 'unittestadmin'
pw = 'unittestadmin'

class CompApiUnitTests(unittest.TestCase):
    def test_run_dataflow_get_output(self):
        comp_session = ca.ComposableSession('unittestadmin','unittestadmin')
        
        
        
        app_id = comp_session.import_app_from_json(path_to_unit_test_data + 'CalculatorTest.json')

        run_id = comp_session.run_dataflow(app_id)
        modules = comp_session.get_run_modules(run_id)
        comp_session._services['ApplicationService'].DeleteApplication(app_id)
        #print(modules)
        
        self.assertEqual(len(modules), 5)
        self.assertEqual(modules[0]['ModuleOutputValues']['Result'],3.0)
        self.assertEqual(modules[1]['ModuleOutputValues']['Result'],5.0)
        
        first_string_format_module = next((x for x in modules if x['Name'] == "String Formatter 2"), None)
        self.assertEqual(first_string_format_module['ModuleOutputValues']['Result'], 'This is a bad format')
    
    def test_queryview_to_pandas(self):
        comp_session = ca.ComposableSession('unittestadmin','unittestadmin')
        df = comp_session.queryview_from_id(137072)
        print(df.head())
        print(df.dtypes)
    
    def test_queryview_to_pandas_streaming(self):
        comp_session = ca.ComposableSession('unittestadmin','unittestadmin')
        
        t = time()
        df = comp_session.queryview_from_id(137072)
        print(time()-t)
        print(df.head())
        print(df.dtypes)
        print(len(df))
        #print(df.read())
        #print(df.read())
        #print(df.read())
        #print(df.read())
        #print(df.read())
        #print(bytes(df.read()))
        #pd.read_csv(df)
        #with open(df,"r") as stream:
        #    print(stream)
    
    def test_convert_table_to_pandas(self):
        comp_session = ca.ComposableSession('unittestadmin','unittestadmin')
        app_id = comp_session.import_app_from_json('C:\\PythonNet\\TestFiles\\tablecreator.json')

        run_id = comp_session.run_dataflow(app_id)
        modules = comp_session.get_run_modules(run_id)
        comp_session._services['ApplicationService'].DeleteApplication(app_id)
        table = modules[0]['ModuleOutputValues']['Result']
        df = comp_session.convert_table_to_pandas(table)

        self.assertEqual(type(df), type(pd.DataFrame()))

    def test_convert_table_to_pandas_dtypes(self):
        app_id = 137298 # change this

        comp_session = ca.ComposableSession('unittestadmin','unittestadmin')
        run_id = comp_session.run_dataflow(app_id)
        modules = comp_session.get_run_modules(run_id)
        table = modules[0]['ModuleOutputValues']['Result']
        df = comp_session.convert_table_to_pandas(table)

        print(df)
        print(df.dtypes)

        self.assertEqual(type(df), type(pd.DataFrame()))
        self.assertEqual(df.dtypes['SystemDateTimeOffset'], 'datetime64[ns]')

    # def test_all_external_inputs(self):
    #     comp_session = ca.ComposableSession(api_key)
    #     path_to_my_csv = r'C:\Composable\Product\UnitTests\TestData\DupColumns.csv'
    #     dict_of_inputs = {'IntInput': 3, 'FileInput': path_to_my_csv, 'TableInput': pd.DataFrame({'a':[1]})}
    #     dataflow_id = 7552
    #     run_id = comp_session.run_dataflow_with_inputs(dataflow_id,dict_of_inputs)
    #     #print(run_id)

    # def test_all_external_inputs_pw(self):
    #     comp_session = ca.ComposableSession(user,pw)
    #     path_to_my_csv = r'C:\Composable\Product\UnitTests\TestData\DupColumns.csv'
    #     dict_of_inputs = {'IntInput': 3, 'FileInput': path_to_my_csv, 'TableInput': pd.DataFrame({'a':[1]})}
    #     dataflow_id = 7552
    #     run_id = comp_session.run_dataflow_with_inputs(dataflow_id,dict_of_inputs)
    #     #print(run_id)

if __name__ == '__main__':
    unittest.main()


