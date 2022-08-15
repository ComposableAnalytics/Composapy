# Composapy

DataLabs comes pre-installed with Composapy, a python package that makes it easy to
programmatically interface with Composable. Composapy allows you to interactively author, execute
and retrieve results from DataFlows (Directed Acyclic Graphs, DAGs).

Visit our [ReadTheDocs](https://composapy.readthedocs.io/html/) page a more detailed look at
Composapy.

- [Session](#session)
  - [Register a Session](#register-a-session)
- [DataFlow](#dataflow)
  - [Create and Save a DataFlow](#create-and-save-a-dataflow)
  - [Run a DataFlow](#run-a-dataflow)
  - [DataFlowObject and DataFlowRun Modules](#dataflowobject-and-dataflowrun-modules)
  - [DataFlowObject and DataFlowRun Input](#dataflowobject-and-dataflowrun-input)
  - [DataFlowRun Result](#dataflowrun-result)
- [Key](#key)
  - [Retrieve a Composable Key](#retrieve-a-composable-key)
  - [Search for a Composable Key](#search-for-a-composable-key)
- [QueryView](#queryview)
  - [Create and Connect to a QueryView Driver](#create-and-connect-to-a-queryview-driver)
  - [Run a Query](#run-a-query)
- [Additional Information](#additional-information)

## Session

[ReadTheDocs - Session](https://composapy.readthedocs.io/html/reference/composapy-session.html)

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

You can also call `get_session` to get the currently registered session.

```python
from composapy.session import get_session
session = get_session()
```

## DataFlow

[ReadTheDocs - DataFlow](https://composapy.readthedocs.io/html/reference/composapy-dataflow/index.html)

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
dataflow_run = DataFlow.run(444333, external_inputs={"a_string_external_input": "foo string"})  # DataFlowRun(id=444333)
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
dataflow_run.modules.get(name="string module name").result  # Result(name='foo name', type=String, value='foo value')
```

## Key

[ReadTheDocs - Key](https://composapy.readthedocs.io/html/reference/composapy-key/index.html)

### Retrieve a Composable Key

```python
from composapy.key.api import Key

key_object = Key.get(123456)  # KeyObject(name='some name', type='StringConnectionSettings')

# optionally, if your key has a unique name, you can retrieve with its name
key_object = Key.get(name="a unique name")  # KeyObject(name='a unique name', type='SqlConnectionSettings')
```

### Search for a Composable Key

Keys can be searched by name. It returns a list of key objects.

```python
key_objects = Key.search("same name")  # [KeyObject(name='same name', type='SqlConnectionSettings'), KeyObject(name='same name', type='StringConnectionSettings')]
```

## QueryView

[ReadTheDocs - QueryView](https://composapy.readthedocs.io/html/reference/composapy-queryview/index.html)

### Create and Connect to a QueryView Driver

```python
from composapy.queryview.api import QueryView

driver = QueryView.driver()  # you can create a driver and then connect with a key...
driver.connect(key_object)

driver = QueryView.driver(key_object)  # ... or create a driver using the key as an argument
```

### Run a Query

```python
df = driver.run("select * from some_table")  # returns a Pandas DataFrame of your query
```

## Additional Information

Also, if you want to interface with <a href="https://github.com/pythonnet/pythonnet" target="_blank">pythonnet</a> more closely -- you can find our csharp documentation <a href="https://dev.composable.ai/api/CompAnalytics.Contracts.html" target="_blank">here</a>.
