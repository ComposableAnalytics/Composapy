from __future__ import annotations
from typing import Optional

from CompAnalytics import Contracts, IServices


class ModuleResultError(Exception):
    pass


EXTERNAL_INPUT_NAMES = (
    "External String Input",
    "External Line Input",
    "External Private Input",
    "External Int Input",
    "External Double Input",
    "External Table Input",
    "External Image Input",
    "External Object Input",
    "External Object List Input",
    "External Bool Input",
    "External DateTime Input",
    "External Date Input",
    "External Error Input",
)


class Input:
    """Wraps ModuleIn contract for a simplified textual user interface.
    """

    contract: Contracts.ModuleInput

    def __init__(self, contract: Contracts.ModuleInput):
        self.contract = contract

    @property
    def value(self) -> any:
        """Returns the contract member, ValueObj (value).
        """
        return self.contract.ValueObj


class Result:
    """Wraps ModuleOut contract for a simplified textual user interface.
    """

    contract: Contracts.ModuleOutput

    def __init__(self, contract: Contracts.ModuleOutput):
        self.contract = contract

    @property
    def value(self) -> any:
        """Returns the contract member, ValueObj (value).
        """
        return self.contract.ValueObj


class Module:
    """The object representation of a module inside a dataflow object.
    """

    contract: Contracts.Module

    def __init__(self, contract: Contracts.Module):
        self.contract = contract

    @property
    def name(self) -> str:
        """Returns the module name.
        """
        return self.contract.Name

    @property
    def inputs(self) -> dict[int, Input]:
        """Maps each module input, by name, to a corresponding Input object.
        """
        return {
            name: Input(name.ModuleInputs.GetItemForKey(name))
            for name in self.contract.ModuleInputs.Indexes.Keys
        }


class ResultModule(Module):
    """Extends Module to give the ability to retrieve module results.
    """

    @property
    def results(self) -> dict[int, Result]:
        """Maps each module result, by name, to a corresponding Result object.
        """
        return {
            name: Result(self.contract.ModuleOutputs.GetItemForKey(name))
            for name in self.contract.ModuleOutputs.Indexes.Keys
        }

    @property
    def result(self) -> any:
        """Convenience property that gets the first result.value from results.
        Cannot be used if there is more than one result.
        """
        if len(self.results) > 1:
            raise ModuleResultError(
                "Unable to retrieve singular result, multiple results exist. "
                "For modules that contain multiple results, please use "
                "results instead of result."
            )
        return next(iter(self.results.values())).value


class ModuleRunSet:
    """Wrapper for objects with parent Module, for convenience methods on the set of items
    contained with self._modules.
    """

    _modules: tuple[Module] | tuple[ResultModule]

    def __init__(self, modules: tuple[Module] | tuple[ResultModule]) -> None:
        self._modules = modules

    def __len__(self):
        return len(self._modules)

    def __getitem__(self, index):
        return self._modules[index]

    def __iter__(self):
        return iter(self._modules)

    def first(self):
        """Returns first module in self._modules.
        """
        return next(iter(self._modules))

    def first_with_name(self, name):
        """Matches by first module in self._modules with given name.
        """
        return next(item for item in self._modules if item.name == name)


class RunSet:
    """Similar to a DataFlowObject, with a couple of differences. The first difference is that 
    every RunSet has an id, where as a DataFlowObject only has an ID if it is saved. The second 
    difference is that the modules property on a RunSet returns ModuleRunSet<ResultModule> 
    instead of ModuleRunSet<Module>, which has the additional functionality of viewing module 
    results.
    """

    contract: Contracts.Application

    def __init__(self, contract: Contracts.Application) -> None:
        self.contract = contract

    @property
    def id(self) -> int:
        """Returns the id of dataflow run. Every RunSet is guaranteed to have an id with non-null 
        value.
        """
        return self.contract.Id

    @property
    def modules(self) -> ModuleRunSet:
        """A ModuleRunSet made up of ResultModule's.
        """
        return ModuleRunSet(
            tuple(ResultModule(_module) for _module in self.contract.Modules)
        )


class DataFlowObject(Contracts.Application):
    """DataFlowObject can be used to both model and save dataflow configurations, both saved and 
    before saving. Holds a reference to the service needed to carry out operations on it's behalf.
    """

    contract: Contracts.Application
    _service: IServices.IApplicationService

    def __init__(
        self, contract: Contracts.Application, service: IServices.IApplicationService
    ):
        self.contract = contract
        self._service = service

    @property
    def id(self) -> Optional[int]:
        """The contract id. An unsaved DataFlowObject's id property is None.
        """
        return self.contract.Id

    @property
    def modules(self) -> ModuleRunSet:
        """A ModuleRunSet made up of Module's.
        """
        return ModuleRunSet(tuple(Module(_module) for _module in self.contract.Modules))

    def save(self) -> DataFlowObject:
        """Saves the contract representation of DataFlowObject, uses server response as the newly
        updated contract object (for instance, saving an unsaved contract will give it an id).
        """
        self.contract = self._service.SaveApplication(self.contract)
        return self

    def run(self, external_inputs: dict[str, any] = None) -> RunSet:
        """Runs the dataflow represented by contained contract. Any external modules
        (external int, table, file) that require outside input to run can be added using a
        dictionary with the module input's name and corresponding contract.
        """
        for module in self.modules:
            module.RequestingExecution = True
            if (
                external_inputs
                and module.contract.ModuleType.Name in EXTERNAL_INPUT_NAMES
            ):
                _overwrite_module_inputs(external_inputs, module.contract)

        execution_context = self._service.CreateExecutionContext(
            self.contract, Contracts.ExecutionContextOptions()
        )
        run = self._service.RunExecutionContext(execution_context)
        return RunSet(run)


def _overwrite_module_inputs(
    external_inputs: dict[str, any], module: Contracts.Module
) -> None:
    module_input = module.ModuleInputs.GetItemForKey("Name")
    if module_input.ValueObj in external_inputs.keys():
        _update_module_valueobj(external_inputs, module, module_input)


def _update_module_valueobj(
    external_inputs: dict[str, any], module: Contracts.Module, module_input
) -> None:
    cache_input = module.ModuleInputs.GetItemForKey("Input")
    cache_input.ValueObj = external_inputs[module_input.ValueObj]
    module.ModuleInputs.Remove("Input")
    module.ModuleInputs.Add(cache_input)
