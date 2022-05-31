from typing import Dict
import sys
import os
import logging
from pathlib import Path


def add_dll_reference(path: str) -> None:
    """Attempts to connect to csharp language runtime library at specified path."""
    try:
        import clr

        clr.AddReference(path)
    except:
        logging.warning(f"Failed to load .dll : {path}.")


def load_init(environment_variables: Dict = None) -> None:
    """Either get environment variable "DATALAB_DLL_DIR", or attempt to load into
    environment variables using dotenv (for testing or custom load strategy). Afterward, uses root
    path to find and load needed dll's to use a session.
    """
    if environment_variables:
        for key, val in environment_variables.items():
            os.environ[key] = val

    #  assume dev environment if datalab environment variable has not been set
    DATALAB_DLL_DIR = (
        Path(os.getenv("DATALAB_DLL_DIR"))
        if os.getenv("DATALAB_DLL_DIR")
        else Path(__file__).parent.parent.parent.parent.joinpath(
            "Product", "CompAnalytics.DataLabService", "bin", "Debug"
        )
    )

    add_dll_reference("System.Runtime")
    add_dll_reference("System")
    add_dll_reference("System.Net")

    sys.path.append(str(DATALAB_DLL_DIR))

    DLLs = list(DATALAB_DLL_DIR.rglob("*.dll"))
    composable_DLLs = [dll for dll in DLLs if dll.name.startswith("CompAnalytics")]
    for dll in composable_DLLs:
        add_dll_reference(str(dll))


if __name__ == "__main__":
    run_path = Path.cwd()
    os.chdir(os.path.dirname(Path(__file__)))

    try:
        load_init()
    finally:
        os.chdir(run_path)
