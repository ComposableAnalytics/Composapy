import os
import sys
from pathlib import Path

from composapy._wire import codec
from composapy.auth import AuthMode
from composapy.notebook import inject
from composapy.notebook.nbr_globals import EXECUTION_HANDLE_VAR, RETURN_VALUES_KEYWORD
from composapy.session import Session


def execute_script(input_script_path, serialized_params_path, token=None):
    run_directory = Path(serialized_params_path).parent
    outputs_path = run_directory / "outputs.serialized"

    with open(serialized_params_path, "r", encoding="utf-8-sig") as file:
        entries = codec.decode(file.read())

    namespace, handle = {}, None
    for entry in entries:
        if entry.key == EXECUTION_HANDLE_VAR:
            handle = entry.value
            os.environ[EXECUTION_HANDLE_VAR] = codec.encode(handle)
        else:
            namespace[entry.key] = entry.value

    if token:
        Session(auth_mode=AuthMode.TOKEN, credentials=token).register()

    with open(input_script_path, "r", encoding="utf-8-sig") as source:
        code = compile(source.read(), input_script_path, "exec")
    exec(code, namespace)

    inject.serialize_return_values(
        handle, namespace[RETURN_VALUES_KEYWORD], outputs_path
    )


if __name__ == "__main__":
    args = sys.argv
    execute_script(args[1], args[2], args[3] if len(args) > 3 else None)
