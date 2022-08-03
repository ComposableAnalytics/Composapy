import importlib
import pytest


def test_datalab_env_var_unset_error(monkeypatch):
    # DATALAB_DLL_DIR is set in conftest.py for testing, so we need to delete it here to force an exception
    monkeypatch.delenv("DATALAB_DLL_DIR", raising=True)

    with pytest.raises(ImportError):
        import composapy

        importlib.reload(composapy)
