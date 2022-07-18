<!-- #region -->
# Composapy

DataLabs comes pre-installed with Composapy, a python package that makes it easy to
programmatically interface with Composable. Composapy allows you to interactively author, execute
and retrieve results from DataFlows (Directed Acyclic Graphs, DAGs).

Visit our [ReadTheDocs](https://composapy.readthedocs.io/html/) page a more detailed look at
Composapy.

- [Examples](#examples)
  - [Register a Session](#register-a-session)
  - [Create and Save a DataFlow](#create-and-save-a-dataflow)
  - [Run a DataFlow](#run-a-dataflow)
  - [DataFlowObject and DataFlowRun Modules](#dataflowobject-and-dataflowrun-modules)
  - [DataFlowObject and DataFlowRun Input](#dataflowobject-and-dataflowrun-input)
  - [DataFlowRun Result](#dataflowrun-result)


[Additional Information](#additional-information)

## Examples

### Register a Session

Composapy looks for the environment variable `APPLICATION_URI` by default (set by DataLabs). If you are using Composapy outside of the datalabs environment and the `APPLICATION_URI`
environment variable is not set, you can set it with keyword argument `uri`. You can create a session with Windows Authentication (if you are in DataLab, this will be the same as the 
key on the DataLab edit screen), [`string`] API Token (can be generated on the composable website), or with a [`tuple[str, str]`] username/password combination.
<!-- #endregion -->

```python pycharm={"name": "#%%\n"}
from composapy.session import Session

# use one of the following three methods of authentication
session = Session(auth_mode=Session.AuthMode.WINDOWS)                                                                           # Windows Auth
session = Session(auth_mode=Session.AuthMode.TOKEN, credentials="<your-api-token-here>", uri="http://localhost/CompAnalytics/") # Token
session = Session(auth_mode=Session.AuthMode.FORM, credentials=("username", "password"))                                        # Form

session.register()  # register your session so that composapy uses this
```

### Create and Save a DataFlow

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

### DataFlowObject and DataFlowRun Modules

```python pycharm={"name": "#%%\n"}
dataflow_run.modules[0]  # Module(name='Calculator', type=Calculator)
```

### DataFlowObject and DataFlowRun Input

```python pycharm={"name": "#%%\n"}
dataflow_object.modules.filter(name="calc module name")[0].inputs.first()  # Input(name=Param1, type=Double, value=1.0)
```

### DataFlowRun Result

```python pycharm={"name": "#%%\n"}
dataflow_run.modules.get(name="string module name").result           # Result(name='foo name', type=String, value='foo value')
```

## Additional Information

Also, if you want to interface with <a href="https://github.com/pythonnet/pythonnet" target="_blank">pythonnet</a> more closely -- you can find our csharp documentation <a href="https://dev.composable.ai/api/CompAnalytics.Contracts.html" target="_blank">here</a>.
