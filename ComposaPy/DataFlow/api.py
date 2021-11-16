from typing import Optional

import System
import System.Net
from CompAnalytics import Contracts, IServices
from CompAnalytics.IServices import *
from CompAnalytics.Contracts import *

from ComposaPy.DataFlow.models import DataFlowObject, DataFlowRun, DataFlowRunSet
from ComposaPy.api import ComposableApi
from ComposaPy.mixins import PandasMixin


class DataFlow(PandasMixin, ComposableApi):
    """A wrapper class for DataFlow service-level operations.
    """

    @property
    def service(self) -> IServices.IApplicationService:
        """A composable analytics csharp binding to the IServices.IApplicationService (otherwise
        known as a DataFlow service) object.
        """
        return self.session._services["ApplicationService"]

    def get(self, dataflow_id: int) -> DataFlowObject:
        """Returns wrapped dataflow contract inside a dataflow object.
        """
        dataflow = self.service.GetApplication(dataflow_id)
        return DataFlowObject(dataflow, self.service)

    def create(self, json: str = None, file_path: str = None) -> DataFlowObject:
        """Takes a json formatted string or a local file path containing a valid json. Imports
        the dataflow using the dataflow service binding, and returns a DataFlowObject.
        Note that creating does not save the dataflow, the .save() method must be called on
        DataFlowObject to save it in your composable database."""
        if json and file_path:
            raise ValueError(
                "Cannot use both json and file_name arguments, please choose one."
            )

        if file_path:
            json = System.IO.File.ReadAllText(file_path)

        app = self.service.ImportApplicationFromString(json)
        return DataFlowObject(app, self.service)

    def get_run(self, run_id: int) -> DataFlowRun:
        """Returns wrapped dataflow contract inside of a DataFlowRun object.
        """
        run = self.service.GetRun(run_id)
        return DataFlowRun(run)

    def get_runs(self, dataflow_id) -> DataFlowRunSet:
        """Returns a DataFlowRunSet -- a wrapped set of DataFlowRun.
        """
        runs = self.service.GetAppRuns(dataflow_id)
        return DataFlowRunSet(tuple(DataFlowRun(run) for run in runs))

    def run(
        self, dataflow_id: int, external_inputs: dict[str, any] = None
    ) -> Optional[DataFlowRun]:
        """
        Runs a dataflow from the dataflow id (an invalid id will cause this method to return None).
        Any external modules (external int, table, file) that require outside input to run can be
        added using a dictionary with the module input's name and corresponding contract.
        """

        dataflow = self.service.GetApplication(dataflow_id)
        if not dataflow:
            return None

        dataflow_object = DataFlowObject(dataflow, self.service)
        dataflow_rs = dataflow_object.run(external_inputs=external_inputs)
        return dataflow_rs

    def run_status(self, run_id: int):
        """
        """

        run = self.service.GetRun(run_id)
        return System.Enum.GetNames(Contracts.ExecutionStatus)[run.Status]

    def wait_for_run_execution(self, run_id: int) -> dict[str, int]:
        """
        Waits until run has finished.

        Parameters
        (int) run_id: id of the run

        Return
        (dict[str, int]) execution_status: status of the execution
        """

        run = self.service.GetRun(run_id)
        if run.Status == Contracts.ExecutionStatus.Running:
            self.service.WaitForExecutionContext(run.Handle)
        execution_names = System.Enum.GetNames(Contracts.ExecutionStatus)

        output = {}
        output["execution_status"] = execution_names[self.service.GetRun(run_id).Status]
        output["run_id"] = run_id
        return output
