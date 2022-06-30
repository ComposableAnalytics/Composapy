<!-- #region tags=[] -->
# [readme] composapy

DataLabs comes pre-installed with Composapy, a python package that makes it easy to
programmatically interface with Composable. Composapy allows you to interactively author, execute
and retrieve results from DataFlows (Directed Acyclic Graphs, DAGs).

- [#Quick-Start](#quick-start) : some simple use cases and examples
- [#Reference](#reference) : more details about the components
- [#Additional-Information](#additional-information) : some other links to information outside of this repo

## Quick-Start

### Register a Session

Composapy looks for the environment variable `APPLICATION_URI` by default (set by DataLabs). If you are using Composapy outside of the datalabs environment and the `APPLICATION_URI`
environment variable is not set, you can set it with keyword argument `uri`. You can create a session with Windows Authentication (if you are in DataLab, this will be the same as the 
key on the DataLab edit screen), [`string`] API Token (can be generated on the composable website), or with a [`tuple[str, str]`] username/password combination.
<!-- #endregion -->

```python
from composapy.session import Session

# use one of the following three methods of authentication
session = Session(auth_mode=Session.AuthMode.WINDOWS)                                                                           # Windows Auth
session = Session(auth_mode=Session.AuthMode.TOKEN, credentials="<your-api-token-here>", uri="http://localhost/CompAnalytics/") # Token
session = Session(auth_mode=Session.AuthMode.FORM, credentials=("username", "password"))                                        # Form

session.register()  # register your session so that composapy uses this
```

### Create/Save a DataFlow

[DataFlowObject's](#dataflowobject) can be initialized with the [DataFlow API](#dataflow) method - [create](#create). It takes either a json string (_kwarg_ `json`) or path to a json file (_kwarg_ `file_path`) as parameters. Call the `save` method on an unsaved `DataFlowObject` to save it in the Composable database. Saving it will make give it an `id`, making it available for use in the [Composable Designer](https://github.com/ComposableAnalytics/Docs/blob/master/docs/DataFlows/02.Composable-Designer.md).

```python
from composapy.dataflow.api import DataFlow

dataflow_object = DataFlow.create(file_path="simple-dataflow.json")         # DataFlowObject(id=None)
dataflow_object = DataFlow.create(file_path="simple-dataflow.json").save()  # DataFlowObject(id=123456)
```

### Run a DataFlow

To run a saved DataFlow, you can retrieve the `appId` in the DataFlow's URL.

```python
dataflow_run = DataFlow.run(444333)  # DataFlowRun(id=444333)
```

To run a DataFlow that has external input modules, use the `external_inputs` kwarg, which is a dictionary with key equal to the external modules name field and the value equal to what you want to pass in.

```python
dataflow_run = DataFlow.run(444333, external_inputs={"a_string_external_input": "foo string"})   # DataFlowRun(id=444333)
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

#### AuthMode

- WINDOWS
- TOKEN
- FORM

#### \_\_init\_\_

- Session(auth_mode: AuthMode = Session.AuthMode.WINDOWS, credentials: Optional[str | tuple[str, str]] = None, uri: str = None)

```python
Session(auth_mode=Session.AuthMode.WINDOWS)                                                                           # Windows Auth
Session(auth_mode=Session.AuthMode.TOKEN, credentials="<your-api-token-here>")                                        # Token
Session(auth_mode=Session.AuthMode.FORM, credentials=("username", "password"), uri="http://localhost/CompAnalytics/") # Form
```

<!-- #region pycharm={"name": "#%% md\n"} -->
#### register

- session.register() -> None

Updates the current running environment to use session for authentication.
<!-- #endregion -->

```python pycharm={"name": "#%%\n"}
session = Session(auth_mode=Session.AuthMode.WINDOWS)
session.register()
```

<!-- #region pycharm={"name": "#%% md\n"} -->
#### clear_registration

- Session.clear_registration() -> None

Sets the current registered session to `None`.

### DataFlow

#### get

- get(id: int) -> DataFlowObject
<!-- #endregion -->

```python
DataFlow.get(123456)  # DataFlowObject(id=123456)
```

#### get_run

- get_run(id: int) -> DataFlowRun

```python
DataFlow.get_run(654321)  # DataFlowRun(id=654321)
```

<!-- #region pycharm={"name": "#%% md\n"} -->
#### create

- create(json: str = None, file_path: str = None) -> DataFlowObject

json **or** file_path. Supplying arguments to both will raise exception.
<!-- #endregion -->

```python
DataFlow.create(file_path="simple-dataflow.json")  # DataFlowObject(id=None)
```

#### run

If there are any external inputs in the DataFlow, you can supply them with (_kwarg_ `external_inputs`). It takes the external input name as a key and the external input value as value. You can find more about external input modules [here](https://github.com/ComposableAnalytics/Docs/blob/master/docs/DataFlows/06.DataFlow-Reuse.md#creation).

- run(id: int) -> DataFlowRun

```python
DataFlow.run(123456)  # DataFlowRun(id=234567)
```

- run(id: int, external_inputs: Dict[str, any]) -> DataFlowRun

```python
DataFlow.run(123456, external_inputs={"external_int_input_name": 3})  # DataFlowRun(id=333222)
```

### DataFlowObject


#### contract -> CompAnalytics.Contracts.Application

**Note:** DataFlowObject ID's are unique and different from DataFlowRun ID's.

Using the [DataFlow](#dataflow) api, you can retrieve saved _dataflows_ as `DataFlowObject`'s.

```python
DataFlow.get(123456)  # DataFlowObject(id=123456)
```

#### save

- save() -> DataFlowObject

```python
dataflow_object = DataFlow.create(file_path="dataflow.json")  # DataFlowObject(id=None)
dataflow_object.save()                                        # DataFlowObject(id=123456)
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

Refers to the application id this run is a part of. This can be None if it was run with an unsaved DataFlow.


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

#### name -> str

#### type -> any

#### value -> any

### Result

#### contract -> CompAnalytics.Contracts.ModuleOutput

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

### CompAnalytics.Contracts.Tables.Table

```python
from CompAnalytics.Contracts.Tables import Table
```

C# Contracts Reference - [CompAnalytics.Contracts.Tables.Table](https://dev.composable.ai/api/CompAnalytics.Contracts.Tables.Table.html)

`Table` objects are container objects for queries. For convenience, their results are displayed
as a pandas DataFrame in a notebook environment.

```python
table_run = DataFlow.get_run(138123)
table_run.modules.first().result.value

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

You can use `.to_pandas()` to get the pandas DataFrame representation of a `Table` object.

```python
table = table_run.modules.first().result.value  # CompAnalytics.Contracts.Tables.Table
table_df = table.to_pandas()                    # pandas.DataFrame
```

### CompAnalytics.Contracts.FileReference

```python pycharm={"name": "#%%\n"}
from CompAnalytics.Contracts import FileReference
```

C# Contracts Reference - [CompAnalytics.Contracts.FileReference](https://dev.composable.ai/api/CompAnalytics.Contracts.FileReference.html)

For DataFlows that contain values of type `FileReference`, the `value` property contains the
necessary information needed to retrieve the file. Composapy adds a convenience method,
`to_file`, directly on the `FileReference` class. This gives you the ability to call `to_file`
method directly on your `FileReference` object, which downloads the file to your local workspace
and returns a `FileReference` pointing to the newly created file.

#### to_file

- file_reference.to_file(save_dir: pathlib.Path | str = None, file_name: str = None) -> CompAnalytics.Contracts.FileReference

If no `save_dir` is provided, it uses the current working directory. If no `file_name` is
provided, it will use the source file name.

```python pycharm={"name": "#%%\n"}
run = DataFlow.get_run(654321)
run.modules.first().result.value.to_file(save_dir="optional/relative/path/to/dir", file_name="optional_name.txt")
```

### file_ref

If you need to create a new file reference (to pass as external inputs to a DataFlow), you can
use the `file_ref` utility function.

- file_ref(path_like: pathlib.Path | str) -> CompAnalytics.Contracts.FileReference

```python
from composapy import file_ref
_ref = file_ref("path/to/file.txt")  # CompAnalytics.Contracts.FileReference
```

<!-- #region pycharm={"name": "#%% md\n"} -->
## Additional Information

Also, if you want to interface with <a href="https://github.com/pythonnet/pythonnet" target="_blank">pythonnet</a> more closely -- you can find our csharp documentation <a href="https://dev.composable.ai/api/CompAnalytics.Contracts.html" target="_blank">here</a>.
<!-- #endregion -->
