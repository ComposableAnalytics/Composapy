<!-- #region tags=[] -->
# [readme] composapy
<!-- #endregion -->

DataLabs comes pre-installed with composapy, a python package that integrates and binds with the c# project.


## Setup


```python
from composapy.session import Session
from composapy.dataflow.api import DataFlow
```

### Start a session

<!-- #region -->
```python
class Session(api_token: str, uri: str = None)
```
<!-- #endregion -->

<!-- #region pycharm={"name": "#%% md\n"} -->
Composapy looks for the environment variable `APPLICATION_URI` by default (set by DataLabs).
<!-- #endregion -->

```python
session = Session("<your-api-token-here>")
```

<!-- #region pycharm={"name": "#%% md\n"} -->
If you are using Composapy outside of the datalabs environment and the `APPLICATION_URI`
environment variable is not set, you can set it with keyword argument `uri`.
<!-- #endregion -->

```python pycharm={"name": "#%%\n"}
session = Session("<your-api-token-here>", uri="http://localhost/CompAnalytics/")
```

### DataFlow API

<!-- #region -->
```python
class DataFlow(session: Session)
```
<!-- #endregion -->

```python
dataflow_api = DataFlow(session)
```

Also, if you want to interface with <a href="https://github.com/pythonnet/pythonnet" target="_blank">pythonnet</a> more closely -- you can find our csharp documentation <a href="https://dev.composable.ai/api/CompAnalytics.Contracts.html" target="_blank">here</a>.


## Run a DataFlow (Example)


_simple-dataflow.json_

![simple-dataflow.json](https://raw.githubusercontent.com/ComposableAnalytics/Docs/master/docs/DataLabs/img/DataLabs_Readme_Example_Dataflow.png)

<!-- #region pycharm={"name": "#%% md\n"} -->
### Setup
<!-- #endregion -->

Create a new DataFlowObject with dataflow_api.

```python
new_dataflow_object = dataflow_api.create(file_path="simple-dataflow.json")

print(new_dataflow_object)
```

```shell
DataFlowObject(id=None)
```


Notice that simple_dataflow_object does not have an id. In order to set the id, you can call `DataFlowObject`'s save method. Note, you do **not** need to save a `DataFlowObject` to call it's run method.

```python pycharm={"name": "#%%\n"}
saved_dataflow_object = new_dataflow_object.save()
dataflow_id = saved_dataflow_object.id  # for tutorial convenience

print(saved_dataflow_object)
```

```shell
DataFlowObject(id=206777)  # your id will be different
```


### DataFlowObject

You can retrieve a `DataFlowObject` by using the `DataFlow` api to retrieve a saved dataflow.

<!-- #region -->
```python
$ dataflow_api.get(id: int) -> DataFlowObject
```
<!-- #endregion -->

```python
dataflow_object = dataflow_api.get(dataflow_id)

for module in dataflow_object.modules:
    print(module)
```

```shell
Module(name='Calculator', type=Calculator)
Module(name='Calculator', type=Calculator)
Module(name='String Input', type=String Input)
Module(name='String Formatter', type=String Formatter)
Module(name='String Formatter 2', type=String Formatter)
```

```python
for module in dataflow_object.modules:
    for module_input in module.inputs:
        print(module_input)
```

<!-- #region -->
```python
Input(name=Param1, type=Double, value=1.0)
Input(name=Operator, type=String, value='+')
Input(name=Param2, type=Double, value=2.0)
Input(name=Param1, type=Double, value=0.0)
Input(name=Operator, type=String, value='+')
Input(name=Param2, type=Double, value=2.0)
Input(name=Input, type=String, value='This is a test string')
Input(name=Format, type=String, value='This is a test format')
Input(name=Parameters, type=List<Object>, value=None)
Input(name=Format, type=String, value='This is a bad format')
Input(name=Parameters, type=List<Object>, value=None)
```
<!-- #endregion -->

<!-- #region tags=[] -->
### Run DataFlowObject
```python
$ dataflow_object.run() -> DataFlowRun
```
<!-- #endregion -->

```python
dataflow_run = dataflow_object.run()

for module in dataflow_run.modules:
    for module_result in module.results:
        print(module_result)
```

<!-- #region -->
```python
Result(name='Result', type=Double, value=3.0)
Result(name='Result', type=Double, value=5.0)
Result(name='Result', type=String, value='This is a test string')
Result(name='Result', type=String, value='This is a test format')
Result(name='Result', type=String, value='This is a bad format')
```
<!-- #endregion -->

<!-- #region -->
Instead of retrieving a `DataFlowObject` and calling it's run method, you can instead run a saved dataflow using the `DataFlow` api.
```python
$ dataflow_api.run(id: int) -> DataFlowRun
```
<!-- #endregion -->

```python
dataflow_run = dataflow_api.run(dataflow_id)

for module in dataflow_run.modules:
    for module_result in module.results:
        print(module_result)
```

<!-- #region -->
```python
Result(name='Result', type=Double, value=3.0)
Result(name='Result', type=Double, value=5.0)
Result(name='Result', type=String, value='This is a test string')
Result(name='Result', type=String, value='This is a test format')
Result(name='Result', type=String, value='This is a bad format')
```
<!-- #endregion -->

<!-- #region -->
### External Inputs

[External module](https://github.com/ComposableAnalytics/Docs/blob/master/docs/DataFlows/06.DataFlow-Reuse.md#creation) inputs can be passed to your dataflow by using the `external_inputs` keyword argument in `run`.

```python
$ dataflow_api.run(id: int, external_inputs: Dict[str, any]) -> DataFlowRun
```
<!-- #endregion -->

```python
dataflow_api.run(123456, parameters={
    "external_string_input_name": "string",
    "external_int_input_name": 3
})
```

## Filtering/Retrieving

```python
from composapy.dataflow.models import ModuleSet, InputSet, ResultSet
```

<!-- #region -->
```python
$ dataflow_object.modules -> ModuleSet
$ dataflow_run.modules -> ModuleSet
$ modules.inputs -> InputSet
$ modules.results -> ResultSet
```
<!-- #endregion -->

Set objects (`ModuleSet`/`InputSet`/`ResultSet`) all have the following available behaviors.

<!-- #region -->
```python
x.filter(key=value)
```

---

Return all keys with value as a set.
<!-- #endregion -->

```python
calculator_modules = dataflow_run.modules.filter(name="Calculator")
for module in calculator_modules:
    print(module)
```

<!-- #region -->
```python
Module(name='Calculator', type=Calculator)
Module(name='Calculator', type=Calculator)
```
<!-- #endregion -->

<!-- #region -->
```python
x.get(key=value)
```

---

Return expects exactly one key with result, otherwise will raise exception.
- `FoundMultipleError`
- `NoneFoundError`
<!-- #endregion -->

```python
dataflow_run.modules.get(name="String Input")
```

<!-- #region -->
```python
Module(name='String Input', type=String Input)
```
<!-- #endregion -->

```python
dataflow_run.modules.get(name="String Input").results.get(value="This is a test string")
```

<!-- #region -->
```python
Result(name='Result', type=String, value='This is a test string')
```
<!-- #endregion -->

<!-- #region -->
```python
x[index]
```

---

Indexing works as you would expect it to.
<!-- #endregion -->

```python
dataflow_run.modules[3]
```

<!-- #region -->
```python
Module(name='String Formatter', type=String Formatter)
```
<!-- #endregion -->

<!-- #region -->
```python
x.first()
```

---

For convenience, instead of accessing with an index, you can also get the first result of any set with the first method.
<!-- #endregion -->

```python
dataflow_run.modules.first()
```

<!-- #region -->
```python
Module(name='Calculator', type=Calculator)
```
<!-- #endregion -->

<!-- #region -->
```python
dataflow_object.module, module.result, module.input  # singular nouns
```

---

Instead of accessing `results` and using `first()` or `[0]`, you can instead use `result`. This works for `module`, `result` and `input`. Attempts to use these when there are more than one will raise an exception.
<!-- #endregion -->

```python
dataflow_run.modules.get(name="String Formatter").result
```

<!-- #region -->
```python
Result(name='Result', type=String, value='This is a test format')
```
<!-- #endregion -->

## Object Members/Properties

Most commonly used member properties (`name`/`type`/`value`) can be accessed as python object properties.

```python
dataflow_run.modules.get(name="String Formatter").results.first().value
```

<!-- #region -->
```python
'This is a test format'
```
<!-- #endregion -->

### Contract


If you need to interact more closely with Composable object types, the c#/python binding contracts can be accessed on composapy objects thru the `contract` member.

```python
type(dataflow_run.contract)
```

<!-- #region -->
```python
CompAnalytics.Contracts.ExecutionState
```
<!-- #endregion -->

```python
type(dataflow_run.modules.get(name="String Formatter")).contract
```

<!-- #region -->
```python
CompAnalytics.Contracts.Module
```
<!-- #endregion -->

```python
type(dataflow_run.modules.get(name="String Formatter")).results.first().contract
```

<!-- #region -->
```python
CompAnalytics.Contracts.ModuleOutput
```
<!-- #endregion -->

## Tables

```python
import pandas as pd
from CompAnalytics.Contracts.Tables import Table
```

For convenience, `Result` objects that contain Composable tables are displayed as a Pandas dataframe inside of notebooks (the object is still a `Result` object, and the member `value` will still be a `Table` contract).

```python
table_run = dataflow_api.get_run(138123)

table_run.modules.first().result
```

```python vscode={"languageId": "plaintext"}
+----+-----+-----+-----+
|    | a   | o   | e   |
+====+=====+=====+=====+
|  0 | a   | o   | e   |
+----+-----+-----+-----+
|  1 | e   |     |     |
+----+-----+-----+-----+
|  2 | e   |     |     |
+----+-----+-----+-----+
```

To get the pandas dataframe `Result` of a Composable Table, use `result.to_pandas()`.

```python
result_df = table_run.modules.first().result.to_pandas()
print(isinstance(df, pd.DataFrame))
```

<!-- #region -->
```python
True
```
<!-- #endregion -->

```python
result_value = table_run.modules.first().result.value
print(isinstance(result_value, pd.DataFrame))
```

<!-- #region -->
```python
False
```
<!-- #endregion -->

```python
print(isinstance(result_value, Table))
```

<!-- #region -->
```python
True
```
<!-- #endregion -->

## File References

```python
from composapy.helper import file_ref
```

For dataflows that contain values of type `Contracts.FileReference`, the result value gives you the object with some information needed to retrieve the information of your file. Instead of accessing the `value` property, you can use the `to_file` method to download the file to your local workspace.

<!-- #region -->
```python
$ x.result.to_file(save_dir: str, file_name: str = None)
```
<!-- #endregion -->

```python
run = dataflow_api.get_run(654321)
run.modules.first().result.to_file("relative/path/to/dir", file_name="optional_name.txt")  # file_name uses original file name if kwargs are not specified
```
