from typing import Optional, Dict

from composapy.dataflow.models import DataFlowObject, DataFlowRun

import System
from CompAnalytics import Contracts

from composapy.session import get_session


class DataFlow:
    """A wrapper class for dataflow service-level operations."""

    @staticmethod
    def get(dataflow_id: int) -> DataFlowObject:
        """Returns wrapped dataflow contract inside a dataflow object."""
        dataflow = get_session().app_service.GetApplication(dataflow_id)
        return DataFlowObject(dataflow)

    @staticmethod
    def create(json: str = None, file_path: str = None) -> DataFlowObject:
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

        app = get_session().app_service.ImportApplicationFromString(json)
        return DataFlowObject(app)

    @staticmethod
    def get_run(run_id: int) -> DataFlowRun:
        """Returns wrapped dataflow contract inside of a DataFlowRun object."""
        execution_state = get_session().app_service.GetRun(run_id)
        return DataFlowRun(execution_state)

    @staticmethod
    def run(
        dataflow_id: int, external_inputs: Dict[str, any] = None
    ) -> Optional[DataFlowRun]:
        """Runs a dataflow from the dataflow id (an invalid id will cause this method to return None).
        Any external modules (external int, table, file) that require outside input to run can be
        added using a dictionary with the module input's name and corresponding contract.
        """

        dataflow = get_session().app_service.GetApplication(dataflow_id)
        if not dataflow:
            return None

        dataflow_object = DataFlowObject(dataflow)
        dataflow_run = dataflow_object.run(external_inputs=external_inputs)
        return dataflow_run

    @staticmethod
    def run_status(run_id: int):
        """Retrieves run status.

        Parameters
        (int) run_id: id of the run
        """

        run = get_session().app_service.GetRun(run_id)
        return System.Enum.GetNames(Contracts.ExecutionStatus)[run.Status]

    @staticmethod
    def wait_for_run_execution(run_id: int) -> Dict[str, int]:
        """
        Waits until run has finished.

        Parameters
        (int) run_id: id of the run

        Return
        (dict[str, int]) execution_status: status of the execution
        """

        session = get_session()

        run = session.app_service.GetRun(run_id)
        if run.Status == Contracts.ExecutionStatus.Running:
            session.app_service.WaitForExecutionContext(run.Handle)
        execution_names = System.Enum.GetNames(Contracts.ExecutionStatus)

        output = {}
        output["execution_status"] = execution_names[
            session.app_service.GetRun(run_id).Status
        ]
        output["run_id"] = run_id
        return output
