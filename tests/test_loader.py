import os
import subprocess
import sys
from pathlib import Path

from composapy.auth import AuthMode
from composapy.config import get_config_path, write_config_session
from composapy.loader import load_init
from composapy.session import Session, get_session

REPO_ROOT = Path(__file__).resolve().parent.parent

# stand-ins that make "import clr", "import System", and "import CompAnalytics" fail, even where pythonnet is installed
BLOCK_DOTNET = (
    "import sys\n"
    "sys.modules['clr'] = None\n"
    "sys.modules['System'] = None\n"
    "sys.modules['CompAnalytics'] = None\n"
)


def run_python(code, env_without=("DATALAB_DLL_DIR", "DATALAB_DLL_DIR_EXCLUDE")):
    """Runs code in a fresh interpreter, because the test process already imported composapy."""
    env = {k: v for k, v in os.environ.items() if k not in env_without}
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_composapy_imports_without_the_datalab_dll_dir_setting():
    result = run_python("import composapy; print('imported')")
    assert result.returncode == 0, result.stderr
    assert "imported" in result.stdout


def test_composapy_does_not_need_dotnet_to_import():
    result = run_python(
        BLOCK_DOTNET
        + "import composapy, composapy.dataflow.api, composapy.queryview.api, composapy.key.api"
    )
    assert result.returncode == 0, result.stderr


def test_importing_composapy_does_not_load_clr_or_papermill():
    result = run_python(
        "import sys, composapy\n"
        "loaded = sorted(n for n in ('clr', 'pythonnet', 'clr_loader', 'System', 'papermill') if n in sys.modules)\n"
        "print('LOADED:' + ','.join(loaded))"
    )
    assert result.returncode == 0, result.stderr
    assert "LOADED:" in result.stdout and result.stdout.strip().endswith(
        "LOADED:"
    ), result.stdout


def test_the_saved_session_in_composapy_ini_is_registered_on_load(capsys):
    Session.clear_registration()
    config_path = get_config_path()
    config_path.unlink(missing_ok=True)

    saved = Session(
        uri="http://example.test/CompApp/",
        auth_mode=AuthMode.TOKEN,
        credentials="token-for-tests",
    )
    write_config_session(saved)
    assert config_path.exists()

    try:
        load_init()

        session = get_session()
        assert session.uri == "http://example.test/CompApp/"
        assert session.auth_mode == AuthMode.TOKEN
        assert "Successfully registered Token session." in capsys.readouterr().out
    finally:
        Session.clear_registration()


def test_load_init_without_a_config_file_registers_nothing():
    Session.clear_registration()
    get_config_path().unlink(missing_ok=True)
    load_init()
    assert get_session(raise_exception=False) is None
