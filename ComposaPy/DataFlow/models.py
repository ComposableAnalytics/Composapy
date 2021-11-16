from CompAnalytics import Contracts


class ModuleResultError(Exception):
    pass


class Input:
    contract: Contracts.ModuleInput

    def __init__(self, module_input_contract):
        self.contract = module_input_contract

    @property
    def value(self) -> any:
        return self.contract.ValueObj


class Result:
    contract: Contracts.ModuleOutput

    def __init__(self, module_output_contract):
        self.contract = module_output_contract

    @property
    def value(self) -> any:
        return self.contract.ValueObj


class Module:
    contract: Contracts.Module

    def __init__(self, module_contract):
        self.contract = module_contract

    @property
    def id(self) -> int:
        return self.contract.Id

    @property
    def name(self) -> str:
        return self.contract.Name

    @property
    def inputs(self) -> dict[int, Input]:
        return {
            name: Input(name.ModuleInputs.GetItemForKey(name))
            for name in self.contract.ModuleInputs.Indexes.Keys
        }

    @property
    def results(self) -> dict[int, Result]:
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


class ModuleSet:
    _modules: tuple[Module]

    def __init__(self, modules: tuple[Module]) -> None:
        self._modules = modules

    def __len__(self):
        return len(self._modules)

    def __getitem__(self, index):
        return self._modules[index]

    def __iter__(self):
        return iter(self._modules)

    def first(self):
        return next(iter(self._modules))

    def first_with_name(self, name):
        """Matches by first module with occurring name."""
        return next(item for item in self._modules if item.name == name)


class RunSet:
    contract: Contracts.Application

    def __init__(self, application_contract: Contracts.Application) -> None:
        self.contract = application_contract

    @property
    def id(self) -> int:
        return self.contract.Id

    @property
    def modules(self) -> ModuleSet:
        return ModuleSet(tuple(Module(_module) for _module in self.contract.Modules))


class DataFlowObject(Contracts.Application):
    contract: Contracts.Application

    def __init__(self, application_contract: Contracts.Application):
        self.contract = application_contract

    @property
    def id(self) -> int:
        return self.contract.Id

    @property
    def modules(self) -> list[Module]:
        return [Module(_module) for _module in self.contract.Modules]
