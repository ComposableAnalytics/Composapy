from typing import Optional, Dict

from composapy.dataflow.models import DataFlowObject, DataFlowRun, DataFlowRunSet
from composapy.api import ComposableApi
from composapy.mixins import PandasMixin

import System
from CompAnalytics import Contracts


class DataFlow(PandasMixin, ComposableApi):
    """A wrapper class for dataflow service-level operations."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get(self, dataflow_id: int) -> DataFlowObject:
        """Returns wrapped dataflow contract inside a dataflow object."""
        dataflow = self.session.app_service.GetApplication(dataflow_id)
        return DataFlowObject(dataflow, session=self.session)

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

        app = self.session.app_service.ImportApplicationFromString(json)
        return DataFlowObject(app, session=self.session)

    def get_run(self, run_id: int) -> DataFlowRun:
        """Returns wrapped dataflow contract inside of a DataFlowRun object."""
        execution_state = self.session.app_service.GetRun(run_id)
        return DataFlowRun(execution_state, session=self.session)

    def get_runs(self, dataflow_id) -> DataFlowRunSet:
        """Returns a DataFlowRunSet -- a wrapped set of DataFlowRun."""
        execution_states = self.session.app_service.GetAppRuns(dataflow_id)
        return DataFlowRunSet(
            tuple(
                DataFlowRun(execution_state, session=self.session)
                for execution_state in execution_states
            )
        )

    def run(
        self, dataflow_id: int, external_inputs: Dict[str, any] = None
    ) -> Optional[DataFlowRun]:
        """Runs a dataflow from the dataflow id (an invalid id will cause this method to return None).
        Any external modules (external int, table, file) that require outside input to run can be
        added using a dictionary with the module input's name and corresponding contract.
        """

        dataflow = self.session.app_service.GetApplication(dataflow_id)
        if not dataflow:
            return None

        dataflow_object = DataFlowObject(dataflow, session=self.session)
        dataflow_run = dataflow_object.run(external_inputs=external_inputs)
        return dataflow_run

    def run_status(self, run_id: int):
        """Retrieves run status.

        Parameters
        (int) run_id: id of the run
        """

        run = self.session.app_service.GetRun(run_id)
        return System.Enum.GetNames(Contracts.ExecutionStatus)[run.Status]

    def wait_for_run_execution(self, run_id: int) -> Dict[str, int]:
        """
        Waits until run has finished.

        Parameters
        (int) run_id: id of the run

        Return
        (dict[str, int]) execution_status: status of the execution
        """

        run = self.session.app_service.GetRun(run_id)
        if run.Status == Contracts.ExecutionStatus.Running:
            self.session.app_service.WaitForExecutionContext(run.Handle)
        execution_names = System.Enum.GetNames(Contracts.ExecutionStatus)

        output = {}
        output["execution_status"] = execution_names[
            self.session.app_service.GetRun(run_id).Status
        ]
        output["run_id"] = run_id
        return output
