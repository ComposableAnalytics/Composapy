<!-- #region tags=[] -->
# [readme] composapy
<!-- #endregion -->

Composapy comes packaged with DataLabs. Composapy binds features, such as DataFlow's, of other Composable products for use in a python environment.

- [#Quick-Start](#quick-start) : some simple use-cases and examples
- [#Reference](#reference) : more details about the components
- [#Additional-Information](#additional-information) : some other links to information outside of this repo


## Quick-Start


### Create a Session / Create a DataFlow (API)

<!-- #region pycharm={"name": "#%% md\n"} -->
Composapy looks for the environment variable `APPLICATION_URI` by default (set by DataLabs). If you are using Composapy outside of the datalabs environment and the `APPLICATION_URI`
environment variable is not set, you can set it with keyword argument `uri`.
<!-- #endregion -->

```python
from composapy.session import Session
from composapy.dataflow.api import DataFlow

session = Session("<your-api-token-here>")  # session = Session("<your-api-token-here>", uri="http://localhost/CompAnalytics/")
dataflow_api = DataFlow(session)
```

### Create/Save a DataFlow


[DataFlowObject's](#dataflowobject) can be initialized with the [DataFlow API](#dataflow) method - [create](#create). It takes either a json string (_kwarg_ `json`) or path to a json file (_kwarg_ `file_path`) as parameters. Call the `save` method on an unsaved `DataFlowObject` to save it in the Composable database. Saving it will make give it an `id`, making it available for use in the [Composable Designer](https://github.com/ComposableAnalytics/Docs/blob/master/docs/DataFlows/02.Composable-Designer.md).

```python
dataflow_object = dataflow_api.create(file_path="simple-dataflow.json")         # DataFlowObject(id=None)
dataflow_object = dataflow_api.create(file_path="simple-dataflow.json").save()  # DataFlowObject(id=123456)
```

### Run a DataFlow


To run a saved dataflow, you can retrieve the `appId` in the dataflow's url.

```python
dataflow_run = dataflow_api.run(444333)  # DataFlowRun(id=444333)
```

To run a dataflow that has external input modules, use the `external_inputs` kwarg, which is a dictionary of with key equal to the external modules name field and the value equal to what you want to pass in.

```python
dataflow_run = dataflow_api.run(444333, external_inputs={"a_string_external_input": "foo string"})   # DataFlowRun(id=444333)
```

### DataFlowObject/DataFlowRun Modules

```python
dataflow_run.modules[0]  # Module(name='Calculator', type=Calculator)
```

### DataFlowObject/DataFlowRun Input

```python
dataflow_object.modules.filter(name="calc module name")[0].inputs.first()  # Input(name=Param1, type=Double, value=1.0)
```

### DataFlowRun Result

```python
dataflow_run.modules.get(name="string module name").result           # Result(name='foo name', type=String, value='foo value')
```

## Reference


### Session

<!-- #region -->
```python
class Session(api_token: str, uri: str = None)
```
<!-- #endregion -->

```python
session = Session("<your-api-token-here>")
# session = Session("<your-api-token-here>", uri="http://localhost/CompAnalytics/")
```

### DataFlow


#### \_\_init\_\_


- DataFlow(session: Session)

```python
dataflow_api = DataFlow(session)
```

#### get


- get(id: int) -> DataFlowObject

```python
dataflow_api.get(123456)  # DataFlowObject(id=123456)
```

#### get_run


- get_run(id: int) -> DataFlowRun

```python
dataflow_api.get_run(654321)  # DataFlowRun(id=654321)
```

<!-- #region pycharm={"name": "#%% md\n"} -->
#### create
<!-- #endregion -->

- create(json: str = None, file_path: str = None) -> DataFlowObject


json **or** file_path. Supplying arguments to both will raise exception.

```python
dataflow_api.create(file_path="simple-dataflow.json")  # DataFlowObject(id=None)
```

#### run


If there are any external inputs in the dataflow, you can supply them with (_kwarg_ `external_inputs`). It takes the external input name as a key and the external input value as value. You can find more about external input modules [here](https://github.com/ComposableAnalytics/Docs/blob/master/docs/DataFlows/06.DataFlow-Reuse.md#creation).


- run(id: int) -> DataFlowRun

```python
dataflow_api.run(123456)  # DataFlowRun(id=234567)
```

- run(id: int, external_inputs: Dict[str, any]) -> DataFlowRun

```python
dataflow_api.run(123456, external_inputs={"external_int_input_name": 3})  # DataFlowRun(id=333222)
```

### DataFlowObject


#### contract -> CompAnalytics.Contracts.Application


**Note:** DataFlowObject ID's are unique and different from DataFlowRun ID's.

Using the [DataFlow](#dataflow) api, you can retrieve saved _dataflows_ as `DataFlowObject`'s.

```python
dataflow_object = dataflow_api.get(123456)  # DataFlowObject(id=123456)
```

#### save


- save() -> DataFlowObject

```python
dataflow_object = dataflow_api.create(file_path="dataflow.json")  # DataFlowObject(id=None)
dataflow_object.save()                                            # DataFlowObject(id=123456)
```

#### run


- run() -> DataFlowRun

```python
dataflow_run = dataflow_object.run()  # DataFlowRun(id=234567)
```

#### Properties


##### id -> int


##### module -> Module


##### modules -> ModuleSet


### DataFlowRun


#### contract -> CompAnalytics.Contracts.ExecutionState


#### Properties


##### id -> int


##### app_id -> int


Refers to the application id this run is a part of. This can be None if it was run with an unsaved dataflow.


##### module -> Module


##### modules -> ModuleSet


### Module


#### contract -> CompAnalytics.Contracts.Module


#### name -> str


#### type -> any


#### inputs -> InputSet


#### input -> Input


#### results -> ResultSet


#### result -> Result


### Input


#### contract -> CompAnalytics.Contracts.ModuleInput


#### to_pandas


Will raise exception if value is not of type `CompAnalytics.Contracts.Tables.Table`. More information about the Composable Table to Pandas DataFrame conversion can be found [here](#tables).


- to_pandas() -> pandas.DataFrame

```python
dataflow_object.modules[0].input.to_pandas()
```

#### to_file


Downloads file to a local specified directory and returns a new `CompAnalytics.Contracts.FileReference` to that file. If no file name is supplied, will use the name from the original file. Will raise exception if value is not of type `CompAnalytics.Contracts.FileReference`. More information about file references can be found [here](#file-references).


- to_file(save_dir: pathlib.Path, file_name: str = None) -> CompAnalytics.Contracts.FileReference

```python
dataflow_object.modules[0].input.to_file(save_dir=".", file_name="optional_file_name")
```

#### name -> str


#### type -> any


#### value -> any


### Result


#### contract -> CompAnalytics.Contracts.ModuleOutput


#### to_pandas


Will raise exception if value is not of type `CompAnalytics.Contracts.Tables.Table`. More information about the Composable Table to Pandas DataFrame conversion can be found [here](#tables).


- to_pandas() -> pandas.DataFrame

```python
dataflow_object.modules[0].result.to_pandas()
```

#### to_file


Downloads file to a local specified directory and returns a new `CompAnalytics.Contracts.FileReference` to that file. If no file name is supplied, will use the name from the original file. Will raise exception if value is not of type `CompAnalytics.Contracts.FileReference`. More information about file references can be found [here](#file-references).


- to_file(save_dir: pathlib.Path, file_name: str = None) -> CompAnalytics.Contracts.FileReference

```python
dataflow_object.modules[0].result.to_file(save_dir=".", file_name="optional_file_name")
```

#### name -> str


#### type -> any


#### value -> any


### Filtering/Retrieving for ModuleSet, ResultSet, InputSet

```python
from composapy.dataflow.models import ModuleSet, InputSet, ResultSet
```

- dataflow_object.modules -> ModuleSet
- dataflow_run.modules -> ModuleSet
- modules.inputs -> InputSet
- modules.results -> ResultSet


Set objects (`ModuleSet`/`InputSet`/`ResultSet`) all have the following available behaviors.


#### filter

- x.filter(key=value) -> SetType

Return all keys with value as a set.

```python
calculator_modules = dataflow_run.modules.filter(name="Calculator")
for module in calculator_modules:
    print(module)

# Module(name='Calculator', type=Calculator)
# Module(name='Calculator', type=Calculator)
```

#### get

- x.get(key=value) -> SingularType

Return expects exactly one key with result, otherwise will raise exception.
- `FoundMultipleError`
- `NoneFoundError`

```python
dataflow_run.modules.get(name="String Input")  # Module(name='String Input', type=String Input)
dataflow_run.modules.get(name="String Input").results.get(value="This is a test string")  # Result(name='Result', type=String, value='This is a test string')
```

#### index

- x\[index\] -> SingularType

Indexing works as you would expect it to.

```python
dataflow_run.modules[3]  # Module(name='String Formatter', type=String Formatter)
```

#### first

- x.first() -> SingularType

For convenience, instead of accessing with an index, you can also get the first result of any set with the first method.

```python
dataflow_run.modules.first()  # Module(name='Calculator', type=Calculator)
```

#### dataflow_object.module, module.result, module.input (singular nouns)

Instead of accessing `results` and using `first()` or `[0]`, you can instead use `result`. This works for `module`, `result` and `input`. Attempts to use these when there are more than one will raise an exception.

```python
dataflow_run.modules.get(name="String Formatter").result  # Result(name='Result', type=String, value='This is a test format')
```

### Tables

```python
import pandas as pd
from CompAnalytics.Contracts.Tables import Table
```

For convenience, `Result` objects that contain Composable tables are displayed as a Pandas dataframe inside of notebooks (the object is still a `Result` object, and the member `value` will still be a `Table` contract).

```python
table_run = dataflow_api.get_run(138123)
table_run.modules.first().result

# .to_markdown() was used for markdown presentation purposes
# 
# +----+-----+-----+-----+
# |    | a   | o   | e   |
# +====+=====+=====+=====+
# |  0 | a   | o   | e   |
# +----+-----+-----+-----+
# |  1 | e   |     |     |
# +----+-----+-----+-----+
# |  2 | e   |     |     |
# +----+-----+-----+-----+
```

To get the pandas dataframe `Result` of a Composable Table, use `result.to_pandas()`.

```python
result_df = table_run.modules.first().result.to_pandas()  # pd.DataFrame
```

```python
result_value = table_run.modules.first().result.value  # CompAnalytics.Contracts.Table
```

### File References


For dataflows that contain values of type `Contracts.FileReference`, the result value gives you the object with some information needed to retrieve the information of your file. Instead of accessing the `value` property, you can use the `to_file` method to download the file to your local workspace.


#### \_\_init\_\_


- FileRef(path_like: str | pathlib.Path) -> CompAnalytics.Contracts.FileReference

```python
from composapy.helper import file_ref

_ref = file_ref("path/to/file.txt")  # CompAnalytics.Contracts.FileReference
```

#### to_file


- result.to_file(save_dir: str, file_name: str = None) -> CompAnalytics.Contracts.FileReference

```python
run = dataflow_api.get_run(654321)
run.modules.first().result.to_file("relative/path/to/dir", file_name="optional_name.txt")  # file_name uses original file name if kwargs are not specified
```

## Additional Information


Also, if you want to interface with <a href="https://github.com/pythonnet/pythonnet" target="_blank">pythonnet</a> more closely -- you can find our csharp documentation <a href="https://dev.composable.ai/api/CompAnalytics.Contracts.html" target="_blank">here</a>.
