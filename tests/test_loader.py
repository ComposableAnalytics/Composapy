import configparser
import importlib
import os
import pytest

from composapy.config import get_config_path


def test_datalab_env_var_from_config():
    config_path = get_config_path()
    config_path.unlink(missing_ok=True)

    dll_path = os.environ["DATALAB_DLL_DIR"]
    os.environ["DATALAB_DLL_DIR"] = "/some/invalid/dir"

    config = configparser.ConfigParser()
    config["environment"] = {"DATALAB_DLL_DIR": dll_path}
    with open(config_path, "w") as f:
        config.write(f)

    import composapy

    importlib.reload(composapy)

    assert os.environ["DATALAB_DLL_DIR"] == dll_path


def test_datalab_env_var_unset_error(monkeypatch):
    # DATALAB_DLL_DIR is set in conftest.py for testing, so we need to delete it here to force an exception
    monkeypatch.delenv("DATALAB_DLL_DIR", raising=True)

    with pytest.raises(ImportError):
        import composapy

        importlib.reload(composapy)
