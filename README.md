# Composapy

DataLabs comes pre-installed with Composapy, a python package that makes it easy to
programmatically interface with Composable. Composapy allows you to interactively author, execute
and retrieve results from DataFlows (Directed Acyclic Graphs, DAGs).

Visit our [ReadTheDocs](https://composapy.readthedocs.io/) page a more detailed look at
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
  - [Retrieve Key](#retrieve-key)
  - [Register Key](#register-key)
  - [Search for Key](#search-for-key)
- [QueryView](#queryview)
  - [Create and Connect to a QueryView Driver](#create-and-connect-to-a-queryview-driver)
  - [Run a Query](#run-a-query)
  - [SQL Magic Commands](#sql-magic-commands)
- [Additional Information](#additional-information)

## Session

[ReadTheDocs - Session](https://composapy.readthedocs.io/reference/composapy-session.html)

### Register a Session

Composapy looks for the environment variable `APPLICATION_URI` by default (set by DataLabs). If you are using Composapy outside of the datalabs environment and the `APPLICATION_URI`
environment variable is not set, you can set it with keyword argument `uri`. You can create a session with Windows Authentication (if you are in DataLab, this will be the same as the 
key on the DataLab edit screen), [`string`] API Token (can be generated on the composable website), or with a [`tuple[str, str]`] username/password combination.

```python pycharm={"name": "#%%\n"}
from composapy.session import Session
from composapy.auth import AuthMode

session = Session(auth_mode=AuthMode.WINDOWS)
session = Session(auth_mode=AuthMode.TOKEN, credentials="<your-api-token-here>", uri="http://localhost/CompAnalytics/")
session = Session(auth_mode=AuthMode.FORM, credentials=("username", "password"))
```

After creating a session, register it (future operations use this session by _default_). Optionally, enable the `save` flag to write to a local config file for automatical loading/registration on next Composapy import.

```python
session.register()
session.register(save=True)
```

You can also call `get_session` to get the currently registered session.

```python
from composapy.session import get_session

session = get_session()
```

## DataFlow

[ReadTheDocs - DataFlow](https://composapy.readthedocs.io/reference/composapy-dataflow/index.html)

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

[ReadTheDocs - Key](https://composapy.readthedocs.io/reference/composapy-key/index.html)

### Retrieve Key


A Composapy Key can be retrieved using the python Key API.

```python
from composapy.key.api import Key

key_object = Key.get(123456)  # KeyObject(name='some name', type='StringConnectionSettings')
```

Optionally, if your key name is unique, you can retrieve it by name.

```python
key_object = Key.get(name="a unique name")  # KeyObject(name='a unique name', type='SqlConnectionSettings')
```

### Register Key


Similar to Session, KeyObjects can be registered with the `save=True` flag. This will save the key id in the working directory's "composapy.ini" file, which will then be loaded when the Composapy package is imported.

```python
key_object.register(save=True)
```

You can retrieve the currently registered key_object with `get_key_object`.

```python
from composapy.key.models import get_key_object

get_key_object()  # KeyObject(name='a unique name', type='SqlConnectionSettings')
```

### Search for Key

Keys can be searched by name. It returns a list of key objects.

```python
key_objects = Key.search("same name")  # [KeyObject(name='same name', type='SqlConnectionSettings'), KeyObject(name='same name', type='StringConnectionSettings')]
```

## QueryView

[ReadTheDocs - QueryView](https://composapy.readthedocs.io/reference/composapy-queryview/index.html)

### Create and Connect to a QueryView Driver

```python
from composapy.queryview.api import QueryView

driver = QueryView.driver()  # you can create a driver and then connect with a key...
driver.connect(key_object)

driver = QueryView.driver(key_object)  # ... or create a driver using the key as an argument
```

If there is a currently registered key, there is no need to pass the key to the driver object; the driver will be automatically initialized with the database connection.

```python
QueryView.driver()
```

### Run a Query

```python
df = driver.run("select * from table_name")  # returns a Pandas DataFrame of your query
```

### SQL Magic Commands


In a notebook (IPython) environment, custom sql magic commands are loaded on import with Composapy. Note that both `%sql` and `%%sql` require a registered Session and KeyObject. Both can be loaded on import if saved in the "composapy.ini" config file. See [register-session](#register-a-session) and [register-key](#register-key).

```python vscode={"languageId": "sql"}
%sql select * from some_table  --returns the same result as QueryView.driver("select * from some_table")
```

Instead of doing line magic (only takes that line as input), you can alternatively do cell magic (takes entire cell as input).

```sql vscode={"languageId": "sql"}
select
    *
from
    some_table
where
    some_id is not null
```

## Additional Information

Also, if you want to interface with <a href="https://github.com/pythonnet/pythonnet" target="_blank">pythonnet</a> more closely -- you can find our csharp documentation <a href="https://dev.composable.ai/api/CompAnalytics.Contracts.html" target="_blank">here</a>.
