import os
import clr
import logging
from dotenv import load_dotenv
from pathlib import Path


def add_dll_reference(path: Path) -> None:
    try:
        clr.AddReference(str(path))
    except:
        logging.warning(f"Failed to load .dll : {path}.")


def is_project_dll(path: Path) -> bool:
    return (
        path.is_file()
        and path.name.endswith(".dll")
        and path.name.startswith("CompAnalytics")
    )


def load_init() -> None:
    SETUP_ENV = "../.setup.env"
    LOCAL_ENV = "../.local.env"

    load_dotenv(SETUP_ENV)
    load_dotenv(LOCAL_ENV)

    copy_plugins_path = Path(
        os.getenv("ROOT_PATH_COMPOSABLE"), "CopyPlugins", "bin", "Debug"
    )
    for _path in copy_plugins_path.iterdir():
        if is_project_dll(_path):
            add_dll_reference(_path)

    from src.DataFlow.api import DataFlow
    from src.QueryView.api import QueryView
    from src.session import Session


run_path = Path.cwd()
os.chdir(os.path.dirname(Path(__file__)))

try:
    load_init()
finally:
    os.chdir(run_path)
