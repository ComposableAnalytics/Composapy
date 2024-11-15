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
  - [Run a Saved QueryView](#run-a-saved-queryview)
- [Interactive Table Output](#interactive-table-output)
  - [QueryView Driver Output](#queryview-driver-output)
  - [SQL Cell Magic Output](#sql-cell-magic-output)
  - [Saved QueryView Output](#saved-queryview-output)
  - [Table Contract Output](#table-contract-output)
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

`%%sql` cell magic also supports options to customize the query execution, such as setting a timeout value or capturing the output of the query into a Python variable. Run %%sql? for detailed documentation.


### Run a Saved QueryView

To run a saved QueryView, you can retrieve the ID in the QueryView's URL and invoke the static `run` method without needing to create a driver object.

```python
from composapy.queryview.api import QueryView

QueryView.run(123456) # returns a Pandas DataFrame with the query results
```

If the QueryView has literal or filter inputs, you can optionally pass values and operators to the `run` method using the `inputs` argument. This argument must be a dictionary whose keys are the display name of the input. There are two possible formats for the dictionary values, depending on the kind of input:

1. [LITERAL, FILTER] A single Python primitive (`int`, `bool`, `str`, `float`). The default operator will be used for filter inputs in this case.
2. [FILTER] A tuple of size two in the form `(val, operator)` where `val` is the primitive input value and `operator` is one of the acceptable QueryView input operators (=, !=, >, <, >=, <=, LIKE)

As of Composapy 0.13.1, multi-choice inputs are supported. To pass a multi-choice input, sets, tuples, and lists that contain primitive values are accepted. Due to the current nature of filter inputs requiring tuple format, literal multi-choice inputs must be passed as a tuple containing a set, tuple, or list of primitive values, like so, for instance: [{item1,item2}]. This is in order to preserve parsing logic for filter inputs, which would follow a similar format: [{item1,item2},operator].

```python
QueryView.run(123456, inputs={"displayName1": "val1", "displayName2": (100, "!=")})
```

## Interactive Table Output

Some operations that return Pandas DataFrames can also be run in interactive mode, which renders the data as an interactive DataTable with server-side processing for pagination. There are four main operations that can return interactive tables:
1. QueryView driver output
2. `%%sql` cell magic output
3. Saved QueryView output
4. Table contract output



#### QueryView Driver Output
When creating a QueryView driver, set `interactive=True`:

```python
from composapy.queryview.api import QueryView
QueryView.driver(interactive=True)
driver.run("select * from table")
```

Note that unlike other QueryView driver settings, `interactive` can only be set when `driver()` is called, not when `run()` is called.


#### SQL Cell Magic Output
Simply pass the `-i` flag to the `%%sql` magic command:

```sql vscode={"languageId": "sql"} magic_args="-i"
select * from table
```

#### Saved QueryView Output
When running a saved QueryView, pass the `interactive=True` argument to `run()`:

```python
from composapy.queryview.api import QueryView
QueryView.run(12345, interactive=True)
```

Note that the paging options set in the QueryView will be respected. If no paging options are set, Auto Paging will be used.


#### Table Contract Output
When a table contract is passed into a DataLab (either via running a DataFlow or as a notebook runner input), it can be viewed interactively by setting a global option. The below example runs a DataFlow that contains an Odbc Query module, which has a Table output: 

```python
import composapy.interactive.options as iopts
iopts.SHOW_INTERACTIVE_TABLES = True

from composapy.dataflow.api import DataFlow
table_contract = DataFlow.run(1234).modules.get(name="Odbc Query").result.value
table_contract # NOTE: you can also use display(table_contract), but don't use print(table_contract)
```

## Additional Information

Also, if you want to interface with <a href="https://github.com/pythonnet/pythonnet" target="_blank">pythonnet</a> more closely, you can find our csharp documentation <a href="https://dev.composable.ai/api/CompAnalytics.Contracts.html" target="_blank">here</a>.
