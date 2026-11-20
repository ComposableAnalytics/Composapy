"""Offline tests for what `import composapy` loads: no .NET runtime and no papermill (docs: Migrating to 1.0).

These count modules in a clean interpreter, so unlike the import-time comparison they do not depend on the clock or on
how busy the machine is.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FORBIDDEN = ("clr", "papermill", "pythonnet", "clr_loader")

# Defines loaded(): the forbidden modules that are in sys.modules now, as top-level names
PREAMBLE = (
    "import sys\n"
    f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"  # -I leaves cwd off the path, and the environment may hold an older composapy
    f"FORBIDDEN = {FORBIDDEN!r}\n"
    "def loaded():\n"
    "    return sorted({m.split('.')[0] for m in sys.modules if m.split('.')[0] in FORBIDDEN and sys.modules[m] is not None})\n"
)


def run_isolated(code, tmp_path, environ=None):
    """Runs the code in `python -I`: no PYTHON* variables, no user site folder, nothing from the current folder."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("DATALAB_")}
    env["COMPOSAPY_INI_DIR"] = str(
        tmp_path
    )  # a folder with no composapy.ini, unless the test writes one
    env.update(environ or {})
    result = subprocess.run(
        [sys.executable, "-I", "-c", PREAMBLE + code],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


def test_importing_composapy_loads_none_of_the_dotnet_or_papermill_modules(tmp_path):
    assert run_isolated("import composapy\nprint(loaded())", tmp_path) == "[]"


def test_the_check_does_see_papermill_when_the_notebook_runner_is_imported(tmp_path):
    pytest.importorskip("papermill")
    # a control: without it a check that can never fail would look the same as one that passes
    answer = run_isolated(
        "import composapy\nimport composapy.notebook.nb_wrap\nprint(loaded())", tmp_path
    )
    assert answer == "['papermill']"


def test_the_names_a_script_imports_from_companalytics_load_none_of_them_either(
    tmp_path,
):
    code = (
        "import composapy\n"
        "from CompAnalytics.Contracts import FileReference, ExecutionHandle\n"
        "from CompAnalytics.Contracts.Tables import Table\n"
        "from CompAnalytics.Contracts.QueryView import LiteralInput, SearchInput\n"
        "from CompAnalytics.Core import ContractSerializer\n"
        "print(loaded())"
    )
    assert run_isolated(code, tmp_path) == "[]"


def test_every_module_of_the_package_but_the_notebook_runner_loads_none_of_them(
    tmp_path,
):
    code = (
        "import importlib, json, pkgutil, composapy\n"
        "seen, first_loaded_by, errors, count = set(), {}, {}, 0\n"
        "for info in pkgutil.walk_packages(composapy.__path__, 'composapy.'):\n"
        "    count += 1\n"
        "    try:\n"
        "        importlib.import_module(info.name)\n"
        "    except Exception as error:\n"
        "        errors[info.name] = type(error).__name__\n"
        "    for name in loaded():\n"
        "        if name not in seen:\n"
        "            seen.add(name)\n"
        "            first_loaded_by[name] = info.name\n"
        "print(json.dumps([count, first_loaded_by, errors]))"
    )
    count, first_loaded_by, errors = json.loads(run_isolated(code, tmp_path))
    assert count > 30  # the walk found the package, so an empty answer means something
    # only the notebook runner (which imports the translators that patch papermill) may bring papermill in
    assert set(first_loaded_by) <= {"papermill"}
    assert set(first_loaded_by.values()) <= {
        "composapy.notebook.nb_wrap",
        "composapy.notebook.translators",
    }
    # composapy.magics registers IPython magics and needs a running IPython, so it cannot be imported on its own
    assert set(errors) <= {"composapy.magics"}


def test_datalab_dll_dir_is_accepted_and_ignored(tmp_path):
    missing = str(tmp_path / "no such folder")
    answer = run_isolated(
        "import composapy\nprint(loaded())",
        tmp_path,
        environ={"DATALAB_DLL_DIR": missing, "DATALAB_DLL_DIR_EXCLUDE": "Some.dll"},
    )
    assert answer == "[]"


def test_a_saved_configuration_with_an_environment_section_still_loads_its_session(
    tmp_path,
):
    (tmp_path / "composapy.ini").write_text(
        "[session]\n"
        "uri = http://example.test/CompApp/\n"
        "auth_mode = Token\n"
        "token = token-for-tests\n"
        "username = \n"
        "password = \n"
        "\n"
        "[environment]\n"
        "dll_dir = C:\\no such folder\n"
        "dll_dir_exclude = Some.dll\n",
        encoding="utf-8",
    )
    code = (
        "import composapy\n"
        "from composapy.session import get_session\n"
        "print(get_session().uri, loaded())"
    )
    assert run_isolated(code, tmp_path) == "http://example.test/CompApp/ []"
