"""What the DLNBR wrapper cases need from the instance: a real execution handle, a Table, a FileReference, a saved DataFlow.

Made with the candidate library by run_wrappers.py, once for each variant, so the two variants never share a run. A
notebook that returns a DataFrame or a file uploads it to the run its handle names, and one that reads a file reference
streams it from there, so the handle has to exist on the server.
"""

import json
import tempfile
from pathlib import Path

from composapy._wire import codec
from composapy.contracts import ExecutionContextOptions
from composapy.dataflow.api import DataFlow
from composapy.dataflow.io import upload_files_to_runs_dir

TEST_FILES = Path(__file__).resolve().parent.parent.parent / "tests" / "TestFiles"
FILE_TEXT = "hello from the parity harness\n"


def _plain(contract):
    """A contract as the JSON the C# side writes into inputs.serialized."""
    return json.loads(codec.encode(contract))


def create(session):
    created = {"saved_app_ids": []}

    # calculator_test.json has two modules named Calculator, and the test notebooks ask for the Calculator by name
    app = json.loads(
        (TEST_FILES / "calculator_test.json").read_text(encoding="utf-8-sig")
    )
    app["Modules"][1]["Name"] = "Calculator 2"
    calculator = DataFlow.create(json=json.dumps(app)).save()
    created["saved_app_ids"].append(calculator.id)
    handle = session.app_service.CreateExecutionContext(
        calculator.contract, ExecutionContextOptions()
    )

    table_flow = DataFlow.create(file_path=str(TEST_FILES / "tablecreator.json"))
    table = table_flow.run().modules.first_with_name("Table Creator").result.value

    folder = Path(tempfile.mkdtemp(prefix="parity-wrapper-"))
    source = folder / "parity-input.txt"
    source.write_text(FILE_TEXT, encoding="utf-8")
    file_reference = upload_files_to_runs_dir(handle, source)

    created.update(
        handle=_plain(handle),
        table=_plain(table),
        file_ref=_plain(file_reference),
        app_id=calculator.id,
    )
    return created


def delete(session, created):
    for app_id in created.get("saved_app_ids", []):
        try:
            session.app_service.DeleteApplication(app_id)
        except Exception as error:  # best effort: report it and keep cleaning up
            print(f"could not delete application {app_id}: {error}")
