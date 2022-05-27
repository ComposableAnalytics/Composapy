<!-- #region tags=[] -->
## [readme] composapy
<!-- #endregion -->

DataLabs comes pre-installed with composapy, a python package that integrates and binds with the c# project.


### Setup


#### Bind DLL's

```python
from composapy.loader import load_init
load_init()
```

#### Start a session

<!-- #region -->
```python
$ Session(username_or_token: str, password: str = None, uri: str = None) => Session
```

<!-- #endregion -->

```python
from composapy.session import Session
session = Session("<your-api-token-here>")
```

#### Bind to a service object...

<!-- #region -->
```python
$ DataFlow(session: Session) => DataFlow
```
<!-- #endregion -->

```python
# the dataflow service {ApplicationService} object.
from composapy.dataflow.api import DataFlow
dataflow_api = DataFlow(session)
```

#### ...or, if you want to interface with <a href="https://github.com/pythonnet/pythonnet" target="_blank">pythonnet</a> more closely -- you can find our csharp documentation <a href="https://dev.composable.ai/api/CompAnalytics.Contracts.html" target="_blank">here</a>
- Comments which contain `{ }` are inserted for literal reference to our csharp documentation

```python
# don't forget to check out the docstrings with help() for type-hints and additional details.
```

#### Run a DataFlow


![Example Dataflow](https://raw.githubusercontent.com/ComposableAnalytics/Docs/master/docs/DataLabs/img/DataLabs_Readme_Example_Dataflow.png)

<!-- #region pycharm={"name": "#%% md\n"} -->
#### [Setup] Create a new dataflow and obtain it's ID.
<!-- #endregion -->

```python pycharm={"name": "#%%\n"}
simple_dataflow_object = dataflow_api.create(file_path="simple-dataflow.json").save()
dataflow_id = simple_dataflow_object.id
```

<!-- #region -->
#### Retrieve a DataFlowObject by id.
```python
$ DataFlow.get(id: int) => DataFlowObject
```
<!-- #endregion -->

```python tags=[]
dataflow_object = dataflow_api.get(dataflow_id)
dict_display_modules = {}                            # iterate over modules and module inputs, creating a dictionary representation
for module in dataflow_object.modules:
    dict_display_modules[module.name] = {_input.name:_input.value for _input in module.inputs}
dict_display_modules
```

<!-- #region tags=[] -->
#### You can run the dataflow by calling the DataFlowObject's run method...
```python
$ DataFlowObject.run() => DataFlowRun
```
<!-- #endregion -->

```python
dataflow_run = dataflow_object.run()
for module in dataflow_run.modules:
    print(module.result.value)
```

<!-- #region -->
#### ... or you can run a dataflow directly from the api with an id.
```python
$ DataFlow.run(id: int) => DataFlowRun
```
<!-- #endregion -->

```python
dataflow_run = dataflow_api.run(dataflow_id)
for module in dataflow_run.modules:
    print(module.result.value)
```

## Filtering


#### ModuleSet

<!-- #region -->
```python
$ DataFlowRun.ModuleSet.filter(attr: str) => tuple(Module)
```
<!-- #endregion -->

```python
calculator_modules = dataflow_object.modules.filter(name="Calculator")
calculator_modules[0].inputs[0].value
```

#### InputSet

<!-- #region -->
```python
$ DataFlowRun.Module.InputSet.filter(attr: str) => tuple(Input)
```
<!-- #endregion -->

```python
calculator_modules[0].inputs.filter(name="Operator")[0].value
```

#### ResultSet

<!-- #region -->
```python
$ DataFlowRun.Module.ResultSet.filter(attr: str) => tuple(Result)
```
<!-- #endregion -->

```python
dataflow_run.modules.filter(name="Calculator")[0].results.filter(name="Result")[0].value
```

## Contracts


- The bound contracts `{CompAnalytics.Contracts}` can be accessed from any composapy object thru it's `contract` property.
- Sometimes contract names are a bit different than expected, but they can all be found on Composable's api docs.

<!-- #region -->
```python
$ DataFlowObject.contract: CompAnalytics.Contracts.Application
```
<!-- #endregion -->

<!-- #region -->
```python
$ DataFlowRun.contract: CompAnalytics.Contracts.ExecutionState
```
<!-- #endregion -->

<!-- #region -->
```python
$ Module.contract: CompAnalytics.Contracts.Module
```
<!-- #endregion -->

<!-- #region -->
```python
$ Input.contract: CompAnalytics.Contracts.ModuleInput
```
<!-- #endregion -->

<!-- #region -->
```python
$ Result.contract: CompAnalytics.Contracts.ModuleOutput
```
<!-- #endregion -->

## Tables


- For convenience, Result objects with a value of type `{CompAnalytics.Contracts.Tables.Table}` are displayed as a Pandas dataframe

```python
table_run = dataflow_api.get_run(138123)
table_run.modules.first().result
```
