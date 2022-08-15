from pathlib import Path

from dotenv import dotenv_values


# Composapy Directory Paths

COMPOSAPY_ROOT_DIR = Path(__file__).parent
COMPOSAPY_DOCS_README_IPYNB = COMPOSAPY_ROOT_DIR.joinpath(
    "docs", "composapy-readme.ipynb"
)
COMPOSAPY_SPHINX_DOCS_DIR = Path(COMPOSAPY_ROOT_DIR, "docs/sphinx-docs")
COMPOSAPY_TESTS_DIR = COMPOSAPY_ROOT_DIR.joinpath("tests")

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


## DataLab Directory Paths
DATALAB_DLL_DIR = Path(__file__).parent.parent.parent.joinpath(
    "Product", "CompAnalytics.DataLabService", "bin", "Debug"
)


# Other
TF_EXE_PATH = Path(dotenv_values(".local.env").get("TF_EXE_PATH"))
XML_NAMESPACE = "http://schemas.microsoft.com/developer/msbuild/2003"  # for xml nodes
