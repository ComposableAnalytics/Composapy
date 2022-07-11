# [readme] composapy

DataLabs comes pre-installed with Composapy, a python package that makes it easy to
programmatically interface with Composable. Composapy allows you to interactively author, execute
and retrieve results from DataFlows (Directed Acyclic Graphs, DAGs).

- [#Quick-Start](#quick-start) : some simple use cases and examples
- [#Documentation](#documentation) : more details about the components
- [#Additional-Information](#additional-information) : some other links to information outside of this repo

## Quick-Start

### Register a Session

Composapy looks for the environment variable `APPLICATION_URI` by default (set by DataLabs). If you are using Composapy outside of the datalabs environment and the `APPLICATION_URI`
environment variable is not set, you can set it with keyword argument `uri`. You can create a session with Windows Authentication (if you are in DataLab, this will be the same as the 
key on the DataLab edit screen), [`string`] API Token (can be generated on the composable website), or with a [`tuple[str, str]`] username/password combination.

```python pycharm={"name": "#%%\n"}
from composapy.session import Session

# use one of the following three methods of authentication
session = Session(auth_mode=Session.AuthMode.WINDOWS)                                                                           # Windows Auth
session = Session(auth_mode=Session.AuthMode.TOKEN, credentials="<your-api-token-here>", uri="http://localhost/CompAnalytics/") # Token
session = Session(auth_mode=Session.AuthMode.FORM, credentials=("username", "password"))                                        # Form

session.register()  # register your session so that composapy uses this
```

### Create/Save a DataFlow

[DataFlowObject's](#dataflowobject) can be initialized with the [DataFlow API](#dataflow) method - [create](#create). It takes either a json string (_kwarg_ `json`) or path to a json file (_kwarg_ `file_path`) as parameters. Call the `save` method on an unsaved `DataFlowObject` to save it in the Composable database. Saving it will make give it an `id`, making it available for use in the [Composable Designer](https://github.com/ComposableAnalytics/Docs/blob/master/docs/DataFlows/02.Composable-Designer.md).

```python pycharm={"name": "#%%\n"}
from composapy.dataflow.api import DataFlow

dataflow_object = DataFlow.create(file_path="simple-dataflow.json")         # DataFlowObject(id=None)
dataflow_object = DataFlow.create(file_path="simple-dataflow.json").save()  # DataFlowObject(id=123456)
```

### Run a DataFlow

To run a saved DataFlow, you can retrieve the `appId` in the DataFlow's URL.

```python pycharm={"name": "#%%\n"}
dataflow_run = DataFlow.run(444333)  # DataFlowRun(id=444333)
```

To run a DataFlow that has external input modules, use the `external_inputs` kwarg, which is a dictionary with key equal to the external modules name field and the value equal to what you want to pass in.

```python pycharm={"name": "#%%\n"}
dataflow_run = DataFlow.run(444333, external_inputs={"a_string_external_input": "foo string"})   # DataFlowRun(id=444333)
```

### DataFlowObject/DataFlowRun Modules

```python pycharm={"name": "#%%\n"}
dataflow_run.modules[0]  # Module(name='Calculator', type=Calculator)
```

### DataFlowObject/DataFlowRun Input

```python pycharm={"name": "#%%\n"}
dataflow_object.modules.filter(name="calc module name")[0].inputs.first()  # Input(name=Param1, type=Double, value=1.0)
```

### DataFlowRun Result

```python pycharm={"name": "#%%\n"}
dataflow_run.modules.get(name="string module name").result           # Result(name='foo name', type=String, value='foo value')
```

## Documentation

You can find more detailed documentation on our [readthedocs](https://composapy.readthedocs.io/).


### CompAnalytics.Contracts.Tables.Table

```python pycharm={"name": "#%%\n"}
from CompAnalytics.Contracts.Tables import Table
```

C# Contracts Reference - [CompAnalytics.Contracts.Tables.Table](https://dev.composable.ai/api/CompAnalytics.Contracts.Tables.Table.html)

`Table` objects are container objects for queries. For convenience, their results are displayed
as a pandas DataFrame in a notebook environment.

```python pycharm={"name": "#%%\n"}
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

```python pycharm={"name": "#%%\n"}
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

```python pycharm={"name": "#%%\n"}
from composapy import file_ref
_ref = file_ref("path/to/file.txt")  # CompAnalytics.Contracts.FileReference
```

## Additional Information

Also, if you want to interface with <a href="https://github.com/pythonnet/pythonnet" target="_blank">pythonnet</a> more closely -- you can find our csharp documentation <a href="https://dev.composable.ai/api/CompAnalytics.Contracts.html" target="_blank">here</a>.
