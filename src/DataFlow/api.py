from typing import Optional

import System
import System.Net
from CompAnalytics import Contracts, IServices
from CompAnalytics.IServices import *
from CompAnalytics.Contracts import *

from src.DataFlow.models import DataFlowObject, RunSet
from src.api import ComposableApi
from src.mixins import PandasMixin


class DataFlow(PandasMixin, ComposableApi):
    """A wrapper class for DataFlow operations."""

    _external_input_names = [
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
    ]
    _application_contract = None

    @property
    def application_contract(self) -> Contracts.Application:
        return self._application_contract

    @property
    def app_service(self) -> IServices.IApplicationService:
        return self.session._services["ApplicationService"]

    def create(self, json: str = None, file_name: str = None) -> DataFlowObject:
        if json and file_name:
            raise ValueError(
                "Cannot use both json and file_name arguments, please choose one."
            )

        if file_name:
            json = System.IO.File.ReadAllText(json)

        app = self.app_service.ImportApplicationFromString(json)
        return DataFlowObject(app)

    def save(self) -> Optional[Contracts.Application]:
        if not self._application_contract:
            return None
        self.app_service.SaveApplication(self._application_contract)

    def run_status(self, run_id: int):
        """
        Checks status of a run.

        Parameters
        (int) run_id: id of the run

        Return
        (int) run_id: associated run id
        """

        run = self.app_service.GetRun(run_id)
        return System.Enum.GetNames(Contracts.ExecutionStatus)[run.Status]

    def wait_for_run_execution(self, run_id: int) -> dict[str, int]:
        """
        Waits until run has finished.

        Parameters
        (int) run_id: id of the run

        Return
        (dict[str, int]) execution_status: status of the execution
        """

        run = self.app_service.GetRun(run_id)
        if run.Status == Contracts.ExecutionStatus.Running:
            self.app_service.WaitForExecutionContext(run.Handle)
        execution_names = System.Enum.GetNames(Contracts.ExecutionStatus)

        output = {}
        output["execution_status"] = execution_names[
            self.app_service.GetRun(run_id).Status
        ]
        output["run_id"] = run_id
        return output

    def import_app_from_json(self, json: str) -> int:
        """
        import and save app from a json string of an app.

        Parameters
        (string) json: json string of app.

        Return
        (int) app_id: the id of the app.
        """

        appStr = System.IO.File.ReadAllText(json)
        app = self.app_service.ImportApplicationFromString(appStr)
        saved_app = self.app_service.SaveApplication(app)
        return saved_app.Id

    def run(
        self, app_id: int, external_inputs: dict[str, any] = None
    ) -> Optional[RunSet]:
        """
        Runs a dataflow from the app id.

        Parameters
        (int) id: id of the dataflow
        (dict[str,any]) external_inputs: any external modules (external int, table,
        file, etc) that require outside input to run can be added using a dictionary
        with the module input's name and corresponding value

        Return
        (int) run_id: associated run id
        """

        app = self.app_service.GetApplication(app_id)
        if not app:
            return None

        for module in app.Modules:
            module.RequestingExecution = True
            if external_inputs and module.ModuleType.Name in self._external_input_names:
                self._overwrite_module_inputs(external_inputs, module)

        execution_context = self.app_service.CreateExecutionContext(
            app, Contracts.ExecutionContextOptions()
        )
        dataflow_run = self.app_service.RunExecutionContext(execution_context)
        return RunSet(dataflow_run)

    def _overwrite_module_inputs(
        self, external_inputs: dict[str, any], module: Contracts.Module
    ) -> None:
        module_input = module.ModuleInputs.GetItemForKey("Name")
        if module_input.ValueObj in external_inputs.keys():
            self._update_module_valueobj(external_inputs, module, module_input)

    def _update_module_valueobj(
        self, external_inputs: dict[str, any], module: Contracts.Module, module_input
    ) -> None:
        cache_input = module.ModuleInputs.GetItemForKey("Input")
        cache_input.ValueObj = external_inputs[module_input.ValueObj]
        module.ModuleInputs.Remove("Input")
        module.ModuleInputs.Add(cache_input)

    def get_run_info(self, id: int) -> None:
        return
