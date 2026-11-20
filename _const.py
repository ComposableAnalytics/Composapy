from pathlib import Path
import xml.etree.ElementTree as ET
from dotenv import dotenv_values


def env_check():
    tf_exe = ""
    try:
        tf_exe = Path(dotenv_values(".local.env").get("TF_EXE_PATH"))
    except TypeError:
        raise NameError(".local.env is missing TF_EXE_PATH")
    return tf_exe


# Composapy Directory Paths
COMPOSAPY_ROOT_DIR = Path(__file__).parent
COMPOSAPY_DOCS_README_IPYNB = COMPOSAPY_ROOT_DIR.joinpath(
    "docs", "composapy-readme.ipynb"
)
COMPOSAPY_SPHINX_DOCS_DIR = Path(COMPOSAPY_ROOT_DIR, "docs/sphinx-docs")
COMPOSAPY_TESTS_DIR = COMPOSAPY_ROOT_DIR.joinpath("tests")
COMPOSAPY_CONSTRAINTS_DIR = COMPOSAPY_ROOT_DIR.joinpath("constraints")

# Composable Production Directory Paths
COMPOSABLE_PROD_DIR = COMPOSAPY_ROOT_DIR.parent.parent.joinpath("Product")

## Composable UnitTests Directory Paths
COMPOSABLE_UNITTESTS_DIR = COMPOSABLE_PROD_DIR.joinpath("UnitTests")
COMPOSABLE_TESTDATA_DIR = COMPOSABLE_UNITTESTS_DIR.joinpath("TestData")
COMPOSABLE_TESTDATA_COMPOSAPY_DIR = COMPOSABLE_TESTDATA_DIR.joinpath("composapy")

## DataLabService Directory Paths
DATALABSERVICE_DIR = COMPOSABLE_PROD_DIR.joinpath("CompAnalytics.DataLabService")
DATALABSERVICE_STATIC_DIR = DATALABSERVICE_DIR.joinpath("static")
DATALABSERVICE_WHEELS_DIR = DATALABSERVICE_STATIC_DIR.joinpath("wheels")
DATALABSERVICE_CSPROJ = DATALABSERVICE_DIR.joinpath(
    "CompAnalytics.DataLabService.csproj"
)

# Other
TF_EXE_PATH = env_check  # only calls/throws error if used
XML_NAMESPACE = "http://schemas.microsoft.com/developer/msbuild/2003"  # for xml nodes

# Dev
_VERSIONS = sorted(
    p.stem[len("requirements") :]
    for p in DATALABSERVICE_STATIC_DIR.glob("requirements*.txt")
)
_DATALAB_SUPPORTED_PYTHON_VERSIONS = [f"py{v}" for v in _VERSIONS]
_DEV_REQUIREMENTS_TXT = {f"py{v}": f"requirements{v}.txt" for v in _VERSIONS}


def dev_python_exe(python_version):
    """Shared environment's python.exe for 'py311' etc.; reads PythonDirectory from DataLabService's App.config."""
    config = DATALABSERVICE_DIR / "App.config"
    try:
        setting = (
            ET.parse(config).getroot().find("./appSettings/add[@key='PythonDirectory']")
        )
        directory = Path(setting.attrib["value"])
    except (OSError, ET.ParseError, AttributeError, KeyError):
        raise NameError(f"{config} has no PythonDirectory setting")
    return directory / f"python{python_version[2:]}" / "Scripts" / "python.exe"
