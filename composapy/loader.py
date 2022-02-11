import sys
import os
import logging
from pathlib import Path
from typing import Dict


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

    if not os.getenv("DATALAB_DLL_DIR"):
        try:
            from dotenv import load_dotenv

            load_dotenv("../../.local.env")
        except Exception:
            logging.warning(f"failed to load_dotenv with local environment settings")

    add_dll_reference("System.Runtime")
    add_dll_reference("System")
    add_dll_reference("System.Net")

    sys.path.append(os.getenv("DATALAB_DLL_DIR"))

    DLLs = list(Path(os.getenv("DATALAB_DLL_DIR")).rglob("*.dll"))
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
