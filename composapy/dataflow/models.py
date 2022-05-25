from __future__ import annotations
from typing import Optional, Tuple, Dict

from CompAnalytics import Contracts

from .const import ExternalInput
from .web import upload_file_to_runs_dir
from ..mixins import ObjectSetMixin, SessionObjectMixin, PandasMixin, FileReferenceMixin


class ModuleMemberBase(FileReferenceMixin, PandasMixin, SessionObjectMixin):
    """Used as a base class for Input and Result."""

    contract = None  # ModuleInput | ModuleOutput    => union typing issues, leave as is

    def __init__(self, contract, *args, **kwargs):
        self.contract = contract
        super().__init__(*args, **kwargs)

    def _repr_html_(self):
        """Used to display table contracts as pandas dataframes inside of notebooks."""
        if isinstance(self.contract.ValueObj, Contracts.Tables.Table):
            return self.convert_table_to_dataframe(self.contract.ValueObj)._repr_html_()

    @property
    def type(self) -> any:
        """Returns the contract member, ArgumentType."""
        return self.contract.ArgumentType

    @property
    def type_str(self) -> str:
        """Returns the contract member, ArgumentTypeFriendlyName."""
        return self.contract.ArgumentTypeFriendlyName

    @property
    def value(self) -> any:
        """Returns the contract member, ValueObj."""
        return self.contract.ValueObj

    @value.setter
    def value(self, val):
        self.contract.ValueObj = val

    @property
    def name(self) -> str:
        """Returns the contract member, Name."""
        return self.contract.Name


class Input(ModuleMemberBase):
    """Wraps ModuleIn contract for a simplified textual user interface."""

    contract: Contracts.ModuleInput

    def __repr__(self):
        return f"<Input::{self.name}, <{self.type_str}::{self.value}>>"


class Result(ModuleMemberBase):
    """Wraps ModuleOut contract for a simplified textual user interface."""

    contract: Contracts.ModuleOutput

    def __repr__(self):
        return f"<Result::{self.name}, <{self.type_str}::{self.value}>>"


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


class Module(SessionObjectMixin):
    """The object representation of a module inside a dataflow object."""

    contract: Contracts.Module

    def __init__(self, contract: Contracts.Module, *args, **kwargs):
        self.contract = contract
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<Module::{self.name}>"

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
                Input(self.contract.ModuleInputs[name], session=self.session)
                for name in self.contract.ModuleInputs.Indexes.Keys
            )
        )

    @property
    def results(self) -> ResultSet:  # Dict[str, Result]:
        """Maps each module result, by name, to a corresponding Result object."""
        return ResultSet(
            tuple(
                Result(self.contract.ModuleOutputs[name], session=self.session)
                for name in self.contract.ModuleOutputs.Indexes.Keys
            )
        )

    @property
    def result(self) -> any:
        """Convenience property that gets the first result.value from results.
        Cannot be used if there is more than one result.
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


class DataFlowRun(SessionObjectMixin):
    """Similar to a DataFlowObject, with a couple of differences. The first difference is that
    every DataFlowRun has an id, where as a DataFlowObject only has an ID if it is saved. The second
    difference is that the modules property on a DataFlowRun returns ModuleSet<ResultModule>
    instead of ModuleSet<Module>, which has the additional functionality of viewing module
    results.
    """

    contract: Contracts.ExecutionState

    def __init__(
        self, execution_state: Contracts.ExecutionState, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.contract = execution_state

    def __repr__(self):
        return f"<DataFlowRun::Id::{self.id}>"

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
            tuple(
                Module(_module, session=self.session)
                for _module in self.contract.Application.Modules
            )
        )


class DataFlowRunSet(ObjectSetMixin):
    """Wrapper for dataflow run objects, using ObjectSetMixin convenience mixin utilities."""

    _target: Tuple[DataFlowRun]

    def __init__(self, dataflow_runs: Tuple[DataFlowRun]) -> None:
        self._target = dataflow_runs


class DataFlowObject(SessionObjectMixin):
    """DataFlowObject can be used to both model and save dataflow configurations, both saved and
    before saving. Holds a reference to the service needed to carry out operations on it's behalf.
    """

    contract: Contracts.Application

    def __init__(self, contract: Contracts.Application, *args, **kwargs):
        self.contract = contract
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<DataFlowObject::Id::{self.id}>"

    @property
    def id(self) -> Optional[int]:
        """The contract id. An unsaved DataFlowObject's id property is None."""
        return self.contract.Id

    @property
    def modules(self) -> ModuleSet:
        """A ModuleSet made up of Module's."""
        return ModuleSet(
            tuple(
                Module(_module, session=self.session)
                for _module in self.contract.Modules
            )
        )

    def save(self) -> DataFlowObject:
        """Saves the contract representation of DataFlowObject, uses server response as the newly
        updated contract object (for instance, saving an unsaved contract will give it an id).
        """
        self.contract: Contracts.Application = self.session.app_service.SaveApplication(
            self.contract
        )
        return self

    def run(self, external_inputs: Dict[str, any] = None) -> DataFlowRun:
        """Runs the dataflow represented by contained contract. Any external modules
        (external int, table, file) that require outside input to run can be added using a
        dictionary with the module input's name and corresponding contract.
        """
        for module in self.modules:
            module.contract.RequestingExecution = True

        self._write_external_inputs(external_inputs)

        execution_handle: Contracts.ExecutionHandle = (
            self.session.app_service.CreateExecutionContext(
                self.contract, Contracts.ExecutionContextOptions()
            )
        )
        pre_run_execution_state: Contracts.ExecutionState = (
            self.session.app_service.GetRun(execution_handle.Id)
        )
        self._post_context_setup_steps(external_inputs, pre_run_execution_state)

        self.session.app_service.RunExecutionContext(execution_handle)
        post_run_execution_state: Contracts.ExecutionState = (
            self.session.app_service.GetRun(execution_handle.Id)
        )

        dataflow_run = DataFlowRun(post_run_execution_state, session=self.session)
        return dataflow_run

    def _write_external_inputs(self, external_inputs: dict):
        """Update any module inputs with required external inputs. It is important that this
        function set each piece of the module input, contract, and ValueObj separately; combining
        any of these steps will result in a failure to save the csharp contract objects correctly."""
        if not external_inputs:
            return

        for module in self.modules:
            if module.type != ExternalInput.FILE and module.type in ExternalInput.ALL:
                module_input = module.contract.ModuleInputs["Name"]
                if module_input.ValueObj in external_inputs.keys():
                    cache_input = module.contract.ModuleInputs["Input"]
                    module.contract.ModuleInputs.Remove("Input")
                    cache_input.ValueObj = external_inputs[module_input.ValueObj]
                    module.contract.ModuleInputs.Add(cache_input)

    def _post_context_setup_steps(
        self, external_inputs: dict, execution_state: Contracts.ExecutionState
    ):
        """Updates necessary post-context setup item for each individual module, such as
        uploading any needed files before running the execution context."""
        if not external_inputs:
            return

        for module in self.modules:
            if module.contract.ModuleType.Name == ExternalInput.FILE:
                upload_file_to_runs_dir(
                    self.session, execution_state, module, external_inputs
                )
