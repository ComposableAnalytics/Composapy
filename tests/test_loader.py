import configparser
import importlib
import os
from pathlib import Path
import pytest

from composapy.config import get_config_path
from composapy.loader import _find_dlls


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


def test_find_dlls_exclude_dirs():
    # dlls found by composapy should be same as the dlls in the top-level DATALAB_DLL_DIR via non-recursive glob
    DATALAB_DLL_DIR = os.getenv("DATALAB_DLL_DIR")
    composapy_dlls = _find_dlls(
        Path(DATALAB_DLL_DIR), exclude=[Path(DATALAB_DLL_DIR).joinpath("plugins")]
    )
    file_dlls = set(
        [
            p
            for p in Path(DATALAB_DLL_DIR).glob("*.dll")
            if p.name.lower().startswith("companalytics")
        ]
    )
    assert len(composapy_dlls) == len(file_dlls)


def test_find_dlls_no_exclude_dirs():
    # dlls found by composapy without specifying any exclusions should match the full recursive glob in DATALAB_DLL_DIR
    DATALAB_DLL_DIR = os.getenv("DATALAB_DLL_DIR")
    composapy_dlls = _find_dlls(Path(DATALAB_DLL_DIR), exclude=[])
    file_dlls = set(
        [
            p
            for p in Path(DATALAB_DLL_DIR).rglob("*.dll")
            if p.name.lower().startswith("companalytics")
        ]
    )
    assert len(composapy_dlls) == len(file_dlls)


def test_loader_exclude_fake_dll(dll_exclude, caplog):
    import composapy

    importlib.reload(composapy)

    # there should be no warnings in the log because the fake DLL was properly excluded from the load
    assert len(caplog.records) == 0


def test_loader_exclude_unset(monkeypatch, dll_exclude, caplog):
    monkeypatch.delenv("DATALAB_DLL_DIR_EXCLUDE", raising=False)

    import composapy

    importlib.reload(composapy)

    # there should be 1 warning for failed load of CompAnalytics.MockExclude.dll
    assert len(caplog.records) == 1
    assert "Failed to load .dll" in caplog.messages[0]
    assert "CompAnalytics.MockExclude.dll" in caplog.messages[0]
