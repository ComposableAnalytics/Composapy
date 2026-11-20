from __future__ import annotations
import decimal
import pandas as pd
from pathlib import Path, PureWindowsPath
from typing import Optional, Tuple, Dict

from composapy.decorators import session_required
from composapy.session import get_session
from composapy.dataflow.const import ExternalInput
from composapy.dataflow.io import upload_files_as_external_input
from composapy.mixins import (
    ObjectSetMixin,
)
from composapy.patch.table import to_table
from composapy.contracts.execution_handle import ExecutionHandle
from composapy.contracts.table import Table
from composapy.contracts.execution_context_options import ExecutionContextOptions
from composapy._wire.objects import ContractObject

EXTERNAL_INPUT_TYPES = frozenset(
    value
    for name, value in vars(ExternalInput).items()
    if not name.startswith("_") and isinstance(value, str)
)


def _as_float(value):
    return (
        float(value)
        if isinstance(value, (int, float, decimal.Decimal))
        and not isinstance(value, bool)
        else value
    )


def _as_decimal(value):
    return (
        decimal.Decimal(str(value))
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else value
    )


def _by_declared_type(contract, value):
    """The .NET serializer writes a double or a decimal that has no fraction as 3, not 3.0, so the number on the wire cannot
    say which it was, and therefore the contract declares the type"""
    declared = contract.get("ArgumentTypeName")
    if declared in ("System.Double", "System.Single"):
        convert = _as_float
    elif declared == "System.Decimal":
        convert = _as_decimal
    else:
        return value
    if contract.get("IsCollection") and isinstance(value, list):
        # Converted in place: a caller who appends to .value is appending to the stored list, as for any other type
        value[:] = [convert(item) for item in value]
        return value
    return convert(value)


# What .NET stored when a script assigned None to an input of a value type, which cannot hold null
_VALUE_TYPE_DEFAULTS = {
    **{
        f"System.{name}": 0
        for name in (
            "Int16",
            "Int32",
            "Int64",
            "UInt16",
            "UInt32",
            "UInt64",
            "Byte",
            "SByte",
        )
    },
    "System.Double": 0.0,
    "System.Single": 0.0,
    "System.Decimal": 0,
    "System.Boolean": False,
}


class ModuleMemberBase:
    """Used as a base class for a for the Input and Result members of a Module object."""

    contract = None  # ModuleInput | ModuleOutput    => union typing issues, leave as is

    def __init__(self, contract, *args, **kwargs):
        self.contract = contract
        super().__init__(*args, **kwargs)

    @property
    def type(self) -> str:
        """Returns the contract member, ArgumentTypeFriendlyName."""
        return self.contract.ArgumentTypeFriendlyName

    @property
    def value(self) -> any:
        """Adds contract result id to the ValueObj, then returns the contract member, ValueObj."""
        value_obj = _by_declared_type(self.contract, self.contract.ValueObj)
        try:
            if hasattr(self.contract, "ResultId"):
                setattr(value_obj, "_contract__result_id", self.contract.ResultId)
        except AttributeError:
            pass  # such immutable, much wow
        return value_obj

    @value.setter
    def value(self, val):
        self.contract.ValueObj = val

    @property
    def name(self) -> str:
        """Returns the contract member, Name."""
        return self.contract.Name


class Input(ModuleMemberBase):
    """Wraps ModuleInput contract for a simplified textual user interface."""

    contract: ContractObject

    def __repr__(self):
        repr_value = self.value
        if isinstance(self.value, str):
            repr_value = f"'{self.value}'"
        return f"Input(name={self.name}, type={self.type}, value={repr_value})"


class Result(ModuleMemberBase):
    """Wraps ModuleOutput contract for a simplified textual user interface."""

    contract: ContractObject

    def __repr__(self):
        repr_value = self.value
        if isinstance(self.value, str):
            repr_value = f"'{self.value}'"
        return f"Result(name='{self.name}', type={self.type}, value={repr_value})"


class InputSet(ObjectSetMixin):
    """Wrapper for objects with parent Module, for convenience methods on the set of items
    contained with self._target.
    """

    _target: Tuple[Input]

    def __init__(self, inputs: Tuple[Input]):
        self._target = inputs


class ResultSet(ObjectSetMixin):
    """Wrapper for objects with parent Module, for convenience methods on the set of items
    contained with self._target.
    """

    _target: Tuple[Result]

    def __init__(self, results: Tuple[Result]):
        self._target = results


class ModuleResultException(Exception):
    pass


class Module:
    """The object representation of a module inside a dataflow object."""

    contract: ContractObject

    def __init__(self, contract: ContractObject, *args, **kwargs):
        self.contract = contract
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"Module(name='{self.name}', type={self.type})"

    @property
    def type(self) -> str:
        """Returns the contract member, ModuleType.Name."""
        return self.contract.ModuleType.Name

    @property
    def name(self) -> str:
        """Returns the contract member, Name."""
        return self.contract.Name

    @property
    def inputs(self) -> InputSet:  # Dict[str, Input]:
        """Maps each module input, by name, to a corresponding Input object."""
        return InputSet(
            tuple(
                Input(self.contract.ModuleInputs[name])
                for name in self.contract.ModuleInputs.Indexes.Keys
            )
        )

    @property
    def input(self) -> any:
        """Convenience property that gets the first input. Cannot be used if there is more than
        one input.
        """
        if len(self.inputs) > 1:
            raise ModuleResultException(
                "Unable to retrieve singular input, multiple inputs exist. "
                "For modules that contain multiple inputs, please use "
                "inputs instead of input."
            )
        return next(iter(self.inputs))

    @property
    def results(self) -> ResultSet:  # Dict[str, Result]:
        """Maps each module result, by name, to a corresponding Result object."""
        return ResultSet(
            tuple(
                Result(self.contract.ModuleOutputs[name])
                for name in self.contract.ModuleOutputs.Indexes.Keys
            )
        )

    @property
    def result(self) -> any:
        """Convenience property that gets the first result. Cannot be used if there is more than
        one result.
        """
        if len(self.results) > 1:
            raise ModuleResultException(
                "Unable to retrieve singular result, multiple results exist. "
                "For modules that contain multiple results, please use "
                "results instead of result."
            )
        return next(iter(self.results))


class ModuleSet(ObjectSetMixin):
    """Wrapper for objects with parent Module, for convenience methods on the set of items
    contained with self._target.
    """

    _target: Tuple[Module]

    def __init__(self, modules: Tuple[Module]) -> None:
        self._target = modules


class DataFlowRun:
    """Similar to a DataFlowObject, with a couple of differences. The first difference is that
    every DataFlowRun has an id, where as a DataFlowObject only has an ID if it is saved. The second
    difference is that the modules property on a DataFlowRun returns ModuleSet<ResultModule>
    instead of ModuleSet<Module>, which has the additional functionality of viewing module
    results.
    """

    contract: ContractObject

    def __init__(self, execution_state: ContractObject) -> None:
        self.contract = execution_state

    def __repr__(self):
        return f"DataFlowRun(id={self.id})"

    @property
    def id(self) -> int:
        """Returns the id of dataflow run. Every DataFlowRun is guaranteed to have an id with a
        non-null value.
        """
        return self.contract.Handle.Id

    @property
    def app_id(self) -> int:
        """Returns the originating dataflow application id, assuming originating dataflow was
        saved.
        """
        return self.contract.Handle.AppId

    @property
    def modules(self) -> ModuleSet:
        """A ModuleSet made up of ResultModule's."""
        return ModuleSet(
            tuple(Module(_module) for _module in self.contract.Application.Modules)
        )

    @property
    def module(self) -> any:
        """Convenience property that gets the first module. Cannot be used if there is more than
        one module.
        """
        if len(self.modules) > 1:
            raise ModuleResultException(
                "Unable to retrieve singular module, multiple modules exist. "
                "For dataflow that contain multiple modules, please use "
                "modules instead of module."
            )
        return next(iter(self.modules))


class DataFlowRunSet(ObjectSetMixin):
    """Wrapper for dataflow run objects, using ObjectSetMixin convenience mixin utilities."""

    _target: Tuple[DataFlowRun]

    def __init__(self, dataflow_runs: Tuple[DataFlowRun]) -> None:
        self._target = dataflow_runs


class DataFlowObject:
    """A DataFlowObject is the controller for a Composable dataflow instance. A dataflow instance
    can manage the saved, or unsaved, state of the underlying Application contract. Typically,
    DataFlowObjects are created through the DataFlow class api, not manually instantiated by a
    user with an Application contract.

    **Note:** DataFlowObject ID's are unique and different from DataFlowRun ID's.

    .. highlight:: python
    .. code-block:: python

            from composapy.dataflow.api
            dataflow_object = DataFlow.get(123456)
            dataflow_object = DataFlow.create(file_name="path/to/json/dataflow")
    """

    contract: ContractObject

    def __init__(self, contract: ContractObject):
        self.contract = contract

    def __repr__(self):
        return f"DataFlowObject(id={self.id})"

    @property
    def id(self) -> Optional[int]:
        """The contract id. An unsaved DataFlowObject's id property is None."""
        return self.contract.Id

    @property
    def modules(self) -> ModuleSet:
        """A ModuleSet made up of Module's."""
        return ModuleSet(tuple(Module(_module) for _module in self.contract.Modules))

    @property
    def module(self) -> any:
        """Convenience property that gets the first module. Cannot be used if there is more than
        one module.
        """
        if len(self.modules) > 1:
            raise ModuleResultException(
                "Unable to retrieve singular module, multiple modules exist. "
                "For dataflow that contain multiple modules, please use "
                "modules instead of module."
            )
        return next(iter(self.modules))

    @session_required
    def save(self) -> DataFlowObject:
        """Saves the contract representation of DataFlowObject, uses server response as the newly
        updated contract object (for instance, saving an unsaved contract will give it an id).

        .. highlight:: python
        .. code-block:: python

            dataflow_object = DataFlow.create(file_path="dataflow.json")
            print(dataflow_object.id)  # returns -> None   (unsaved)
            dataflow_object.save()
            print(dataflow_object.id)  # returns -> 123456 (saved)
        """
        self.contract: ContractObject = get_session().app_service.SaveApplication(
            self.contract
        )
        return self

    @session_required
    def run(self, external_inputs: Dict[str, any] = None) -> DataFlowRun:
        """Runs the dataflow represented by contained contract. Any external modules
        (external int, table, file) that require outside input to run can be added using a
        dictionary with the module input's name and corresponding contract.

        .. highlight:: python
        .. code-block:: python

            dataflow_run = dataflow_object.run()
        """
        app_service = get_session().app_service

        # nothing is sent to the server, and no module is changed, until every file that is given is known to be there
        self._check_external_files(external_inputs)

        for module in self.modules:
            module.contract.RequestingExecution = True

        self._write_external_inputs(external_inputs)

        execution_handle: ExecutionHandle = app_service.CreateExecutionContext(
            self.contract, ExecutionContextOptions()
        )

        self._post_context_setup_steps(external_inputs, execution_handle)

        app_service.RunExecutionContext(execution_handle)
        post_run_execution_state: ContractObject = app_service.GetRun(
            execution_handle.Id
        )

        dataflow_run = DataFlowRun(post_run_execution_state)
        return dataflow_run

    def _check_external_files(self, external_inputs: dict):
        """Raises if a file given as an external input is missing or is not a file, so that run() finds out before the
        execution context is created. A file input that is not given is left as the DataFlow has it.
        """
        if not external_inputs:
            return

        for module in self.modules:
            if module.contract.ModuleType.Name != ExternalInput.FILE:
                continue
            input_name = module.contract.ModuleInputs["Name"].ValueObj
            if input_name not in external_inputs:
                continue
            # the same path the upload reads
            path = Path(str(PureWindowsPath(external_inputs[input_name])))
            if not path.exists():
                raise FileNotFoundError(
                    f"The file for the external input '{input_name}' does not exist: {path}"
                )
            if not path.is_file():
                raise ValueError(
                    f"The external input '{input_name}' takes a file, but {path} is not a file."
                )

    def _write_external_inputs(self, external_inputs: dict):
        """Update any module inputs with required external inputs."""
        if not external_inputs:
            return

        for module in self.modules:
            if module.type == ExternalInput.FILE:
                # management of external file inputs occurs after context creation
                pass
            elif module.type in EXTERNAL_INPUT_TYPES:
                input_name = module.contract.ModuleInputs["Name"].ValueObj
                if module.type == ExternalInput.TABLE and isinstance(
                    external_inputs.get(input_name), pd.DataFrame
                ):
                    # conversion of pandas dataframe to composable table occurs after context creation
                    pass
                else:
                    if input_name in external_inputs.keys():
                        value = external_inputs[input_name]
                        member = module.contract.ModuleInputs["Input"]
                        if (
                            module.type == ExternalInput.TABLE
                            and value is not None
                            and not isinstance(value, Table)
                        ):
                            raise TypeError(
                                f"The external input '{input_name}' takes a pandas DataFrame or a Table, "
                                f"not {type(value).__name__}."
                            )
                        if value is None:
                            value = _VALUE_TYPE_DEFAULTS.get(
                                member.get("ArgumentTypeName"), None
                            )
                        member.ValueObj = value

    def _post_context_setup_steps(
        self, external_inputs: dict, execution_handle: ExecutionHandle
    ):
        """Updates necessary post-context setup item for each individual module, such as
        uploading any needed files or converting any pandas dataframes to tables before running the execution context.
        """
        if not external_inputs:
            return

        for module in self.modules:
            # An input that was not given keeps what the DataFlow has, whatever its kind
            if module.contract.ModuleType.Name == ExternalInput.FILE:
                if module.contract.ModuleInputs["Name"].ValueObj in external_inputs:
                    upload_files_as_external_input(
                        execution_handle, module, external_inputs
                    )
            elif module.contract.ModuleType.Name == ExternalInput.TABLE:
                input_name = module.contract.ModuleInputs["Name"].ValueObj
                df = external_inputs.get(input_name)
                if isinstance(df, pd.DataFrame):
                    module_handle = module.contract.UiHandle
                    module_input_handle = module.contract.ModuleInputs["Input"].UiHandle
                    handles = {
                        "ModuleHandle": module_handle,
                        "ModuleInputHandle": module_input_handle,
                    }
                    to_table(df, execution_handle, external_input_handles=handles)
