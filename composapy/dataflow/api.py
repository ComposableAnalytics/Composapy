from typing import Optional, Dict

from composapy.decorators import session_required
from composapy.dataflow.models import DataFlowObject, DataFlowRun

import System
from CompAnalytics import Contracts

from composapy.session import get_session


class DataFlow:
    """DataFlow static wrapper for the ApplicationService contract. It is used to
    service user-level operations on an application-level library.

    .. highlight:: python
    .. code-block:: python

        from composapy.dataflow.api import DataFlow

    """

    @staticmethod
    @session_required
    def get(dataflow_id: int) -> DataFlowObject:
        """Returns the wrapped Application contract inside a DataFlowObject.

        .. highlight:: python
        .. code-block:: python

            dataflow_object = DataFlow.get(123456)

        :param dataflow_id: a valid(saved) Composable dataflow id

        :return: the Application contract wrapped in a DataFlowObject
        """
        dataflow = get_session().app_service.GetApplication(dataflow_id)
        return DataFlowObject(dataflow)

    @staticmethod
    @session_required
    def create(json: str = None, file_path: str = None) -> DataFlowObject:
        """Takes a json formatted string **or** a local file path containing a valid json
        (supplying arguments to both will raise exception). Imports the dataflow using the
        dataflow service binding, and returns a DataFlowObject.
        Note that creating does not save the dataflow, the .save() method must be called on
        DataFlowObject to save it in your Composable database.

        .. highlight:: python
        .. code-block:: python

            dataflow_object = DataFlow.create(file_path="simple-dataflow.json")

        :param json: a json-formatted string
        :param file_path: path to json-formatted file

        :return: the unsaved Application contract wrapped in a DataFlowObject
        """
        if json and file_path:
            raise ValueError(
                "Cannot use both json and file_name arguments, please choose one."
            )

        if file_path:
            json = System.IO.File.ReadAllText(file_path)

        app = get_session().app_service.ImportApplicationFromString(json)
        return DataFlowObject(app)

    @staticmethod
    @session_required
    def get_run(run_id: int) -> DataFlowRun:
        """
        .. highlight:: python
        .. code-block:: python

            dataflow_run = DataFlow.get_run(654321)

        :param run_id: Composable dataflow run id

        :return: the wrapped ExecutionState contract inside a DataFlowRun
        """
        execution_state = get_session().app_service.GetRun(run_id)
        return DataFlowRun(execution_state)

    @staticmethod
    @session_required
    def run(
        dataflow_id: int, external_inputs: Dict[str, any] = None
    ) -> Optional[DataFlowRun]:
        """Runs a dataflow from the dataflow id (an invalid id will cause this method to return None).
        Any external modules (external int, table, file) that require outside input to run can be
        added using a dictionary with the module input's name and corresponding contract.

        .. highlight:: python
        .. code-block:: python

            dataflow_run = DataFlow.run(123456)
            dataflow_run = DataFlow.run(123456, external_inputs={"external_int_input_name": 3})

        :param dataflow_id: a valid(saved) Composable dataflow id
        :param external_inputs: If there are any external inputs in the DataFlow, you can supply
            them via `external_inputs["key"] = value`. It takes the external input name as a key and the
            external input value as value. You can find more about external input modules
            `here <https://docs.composable.ai/en/latest/DataFlows/06.DataFlow-Reuse/#creation>`_.

        :return: the wrapped ExecutionState contract inside a DataFlowRun
        """
        dataflow = get_session().app_service.GetApplication(dataflow_id)
        if not dataflow:
            return None

        dataflow_object = DataFlowObject(dataflow)
        dataflow_run = dataflow_object.run(external_inputs=external_inputs)
        return dataflow_run

    @staticmethod
    @session_required
    def run_status(run_id: int):
        """Retrieves run status.

        :param run_id: Composable dataflow run id
        """

        run = get_session().app_service.GetRun(run_id)
        return System.Enum.GetNames(Contracts.ExecutionStatus)[run.Status]

    @staticmethod
    @session_required
    def wait_for_run_execution(run_id: int) -> Dict[str, int]:
        """Waits until run has finished. Returns a dict with keys "execution_status"
        and "run_id".

        :param run_id: Composable dataflow run id

        :return: status of the execution, ExecutionStatus
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
