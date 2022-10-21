import sys
import os
import logging
from pathlib import Path
import clr
import configparser


def load_init() -> None:
    """Composapy startup behavior function."""
    from composapy.config import get_config_path, read_config

    config = None
    if get_config_path().exists():
        _, config = read_config()

    if config and config.has_section("environment"):
        os.environ["DATALAB_DLL_DIR"] = config["environment"].get(
            "DATALAB_DLL_DIR", fallback=os.getenv("DATALAB_DLL_DIR")
        )

    if not os.getenv("DATALAB_DLL_DIR"):
        raise ImportError(
            "DATALAB_DLL_DIR environment variable is unset. "
            "This variable must be set manually when using Composapy outside of a "
            "DataLabs notebook. "
            "See the Composapy documentation for more details: "
            "https://composapy.readthedocs.io/reference/environment-variables.html"
        )

    _load_dlls()
    _load_and_register_composapy_config(config)
    _load_ipython_magics()


def _load_dlls() -> None:
    """Uses DATALAB_DLL_DIR to find and load needed dll's in order to create a session."""
    DATALAB_DLL_DIR = os.getenv("DATALAB_DLL_DIR")

    # necessary non-composable dll's
    add_dll_reference("System.Runtime")
    add_dll_reference("System")
    add_dll_reference("System.Net")
    # by adding to sys.path, ensure directory will be available for all users
    sys.path.append(DATALAB_DLL_DIR)
    DLLs = list(Path(DATALAB_DLL_DIR).rglob("*.dll"))
    composable_DLLs = [dll for dll in DLLs if dll.name.startswith("CompAnalytics")]
    for dll in composable_DLLs:
        add_dll_reference(str(dll))


def add_dll_reference(path: str) -> None:
    """Attempts to connect to csharp language runtime library at specified path."""

    try:
        clr.AddReference(path)
    except:
        logging.warning(f"Failed to load .dll : {path}.")


def _load_and_register_composapy_config(config: configparser.ConfigParser) -> None:
    """If a composapy.ini file exists, load and register any saved session and key."""
    from composapy.config import ConfigException

    if not config:
        return

    try:
        _load_and_register_session(config)
        _load_and_register_key(config)
    except ConfigException as ex:
        print(f"Failed to load and register config file settings: {ex}")


def _load_and_register_session(config: configparser.ConfigParser) -> None:
    from composapy.session import Session
    from composapy.config import (
        get_config_session,
        FormSession,
        TokenSession,
        WindowsSession,
    )

    config_session = get_config_session(config)

    _credentials = None
    if isinstance(config_session, FormSession):
        _credentials = (
            getattr(config_session, "username"),
            getattr(config_session, "password"),
        )
    elif isinstance(config_session, TokenSession):
        _credentials = getattr(config_session, "token")
    elif isinstance(config_session, WindowsSession):
        _credentials = None

    Session(
        auth_mode=config_session.auth_mode,
        credentials=_credentials,
        uri=config_session.uri,
    ).register()

    print(f"Successfully registered {config_session.auth_mode.value} session.")


def _load_and_register_key(config: configparser.ConfigParser) -> None:
    from composapy.key.api import Key
    from composapy.config import get_config_key_id

    config_key_id = get_config_key_id(config)
    Key.get(config_key_id).register()

    print(f"Successfully registered key with id: {config_key_id}.")


def _load_ipython_magics() -> None:
    if _is_ipython():
        import composapy.magics


def _is_ipython() -> bool:
    try:
        cfg = get_ipython()
        return True
    except Exception:
        return False


if __name__ == "__main__":
    run_path = Path.cwd()
    os.chdir(os.path.dirname(Path(__file__)))

    try:
        load_init()
    finally:
        os.chdir(run_path)
