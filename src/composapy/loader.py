import os
import logging
from pathlib import Path
from typing import Dict


def add_dll_reference(path: Path) -> None:
    """Attempts to connect to csharp language runtime library at specified path."""
    try:
        import clr

        clr.AddReference(str(path))
    except:
        logging.warning(f"Failed to load .dll : {path}.")


def _is_project_dll(path: Path) -> bool:
    return (
        path.is_file()
        and path.name.endswith(".dll")
        and path.name.startswith("CompAnalytics")
    )


def load_init(environment_variables: Dict = None) -> None:
    """Either get environment variable "ROOT_PATH_COMPOSABLE", or attempt to load into
    environment variables using dotenv (for testing or custom load strategy). Afterward, uses root
    path to find and load needed dll's to use a session.
    """
    if environment_variables:
        for key, val in environment_variables.items():
            os.environ[key] = val

    if not os.getenv("ROOT_PATH_COMPOSABLE"):
        try:
            from dotenv import load_dotenv

            load_dotenv("../../.local.env")
        except Exception:
            logging.warning(f"failed to load_dotenv with local environment settings")

    copy_plugins_path = Path(
        os.getenv("ROOT_PATH_COMPOSABLE"), "CopyPlugins", "bin", "Debug"
    )
    for _path in copy_plugins_path.iterdir():
        if _is_project_dll(_path):
            add_dll_reference(_path)


if __name__ == "__main__":
    run_path = Path.cwd()
    os.chdir(os.path.dirname(Path(__file__)))

    try:
        load_init()
    finally:
        os.chdir(run_path)
