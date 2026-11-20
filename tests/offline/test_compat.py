"""Offline tests for composapy.compat: the CompAnalytics names that scripts, notebooks, and old pickles import.

Each test that needs a clean interpreter runs one, because the names are cached in sys.modules after the first import.
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import composapy
import composapy.compat
from composapy.contracts import (
    AudioReference,
    ContractSerializer,
    CsvFileReference,
    ExecutionHandle,
    FileReference,
    ImageReference,
    KmlReference,
    KmzReference,
    LiteralInput,
    Mp3Reference,
    SearchInput,
    StlReference,
    Table,
    TableColumn,
    TableColumnCollection,
    VideoReference,
    WavReference,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SERVED = [
    ("CompAnalytics.Contracts", "FileReference", FileReference),
    ("CompAnalytics.Contracts", "CsvFileReference", CsvFileReference),
    ("CompAnalytics.Contracts", "ImageReference", ImageReference),
    ("CompAnalytics.Contracts", "KmlReference", KmlReference),
    ("CompAnalytics.Contracts", "KmzReference", KmzReference),
    ("CompAnalytics.Contracts", "StlReference", StlReference),
    ("CompAnalytics.Contracts", "Mp3Reference", Mp3Reference),
    ("CompAnalytics.Contracts", "WavReference", WavReference),
    ("CompAnalytics.Contracts", "VideoReference", VideoReference),
    ("CompAnalytics.Contracts", "AudioReference", AudioReference),
    ("CompAnalytics.Contracts", "ExecutionHandle", ExecutionHandle),
    ("CompAnalytics.Contracts.Tables", "Table", Table),
    ("CompAnalytics.Contracts.Tables", "TableColumn", TableColumn),
    ("CompAnalytics.Contracts.Tables", "TableColumnCollection", TableColumnCollection),
    ("CompAnalytics.Contracts.QueryView", "LiteralInput", LiteralInput),
    ("CompAnalytics.Contracts.QueryView", "SearchInput", SearchInput),
    ("CompAnalytics.Core", "ContractSerializer", ContractSerializer),
]


def run_python(code):
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("DATALAB_DLL_DIR", "DATALAB_DLL_DIR_EXCLUDE")
    }
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    "module, name, expected", SERVED, ids=[f"{m}.{n}" for m, n, _ in SERVED]
)
def test_each_served_name_is_the_composapy_contract(module, name, expected):
    imported = __import__(module, fromlist=[name])
    assert getattr(imported, name) is expected


def test_the_import_forms_a_notebook_uses_all_work():
    namespace = {}
    exec(
        "from CompAnalytics.Core import ContractSerializer\n"
        "from CompAnalytics.Contracts import FileReference, ExecutionHandle\n"
        "from CompAnalytics.Contracts.Tables import Table\n"
        "import CompAnalytics.Contracts.Tables\n"
        "import CompAnalytics.Core as core\n",
        namespace,
    )
    assert (
        namespace["Table"] is Table
        and namespace["core"].ContractSerializer is ContractSerializer
    )
    assert namespace["CompAnalytics"].Contracts.Tables.Table is Table


def test_the_query_view_inputs_import_the_way_the_baseline_scripts_did():
    namespace = {}
    exec(
        "from CompAnalytics.Contracts.QueryView import LiteralInput, SearchInput\n"
        "import CompAnalytics.Contracts.QueryView\n",
        namespace,
    )
    assert namespace["LiteralInput"] is LiteralInput
    assert namespace["SearchInput"] is SearchInput
    assert namespace["CompAnalytics"].Contracts.QueryView.LiteralInput is LiteralInput


def test_an_input_a_script_builds_has_the_members_the_dotnet_class_had():
    literal = LiteralInput()
    search = SearchInput()

    assert list(literal)[0] == "__type"  # the .NET serializer reads the type first
    assert literal.type_name == "LiteralInput:#CompAnalytics.Contracts.QueryView"
    assert search.type_name == "SearchInput:#CompAnalytics.Contracts.QueryView"
    dynamic_input = {
        "AcceptParentOverride",
        "ChoiceQuery",
        "DataType",
        "Default",
        "DisplayName",
        "Id",
        "IsHidden",
        "IsVertical",
        "IsVisibleAsChild",
        "Order",
        "TemplateName",
        "Value",
    }
    assert set(literal) - {"__type"} == dynamic_input | {"IsMultiChoice"}
    assert set(search) - {"__type"} == dynamic_input | {
        "Column",
        "Custom",
        "DefaultOperator",
        "IsMultiChoice",
        "OperatorOptional",
    }
    # DynamicInput's constructor sets these two to an empty string; every other string is null
    assert literal.Default == "" and literal.Value == ""
    assert literal.DisplayName is None and literal.IsMultiChoice is False
    assert search.OperatorOptional is False and search.DefaultOperator is None


def test_a_script_sets_members_on_an_input_by_assignment_or_keyword():
    literal = LiteralInput()
    literal.DisplayName = "FullApplicationId"
    literal.DataType = "Number"
    literal.Value = "42"
    same = LiteralInput(DisplayName="FullApplicationId", DataType="Number", Value="42")

    assert literal == same
    assert SearchInput(Column="age", DefaultOperator=">").Column == "age"


def test_every_input_is_a_new_object():
    assert LiteralInput() is not LiteralInput()
    assert SearchInput() == SearchInput()


def test_a_script_can_put_an_input_it_built_into_a_drivers_contract():
    # The calls the baseline scripts made on `driver.contract`, as one did to parameterize a query
    from composapy.queryview.api import QueryView

    from CompAnalytics.Contracts.QueryView import LiteralInput as BaselineLiteralInput

    driver = QueryView.driver()
    literal = BaselineLiteralInput()
    literal.DisplayName = "FullApplicationId"
    literal.TemplateName = "FullApplicationId"
    literal.DataType = "Number"
    literal.IsMultiChoice = False
    literal.Value = "42"

    driver.contract.LiteralInputs.Clear()
    driver.contract.LiteralInputs.Add(literal)

    assert driver.contract.LiteralInputs.Count == 1
    assert driver.contract.LiteralInputs[0] is literal
    assert driver.contract.SearchInputs.Count == 0


def test_an_input_survives_the_wire_format():
    from composapy._wire import codec

    literal = LiteralInput(DisplayName="x", Value="1")
    search = SearchInput(Column="age", DefaultOperator=">", OperatorOptional=True)

    assert codec.decode(codec.encode(literal)) == literal
    assert codec.decode(codec.encode(search)) == search
    assert codec.encode(literal).startswith(
        '{"__type": "LiteralInput:#CompAnalytics.Contracts.QueryView"'
    )


def test_the_parent_packages_can_be_imported_on_their_own():
    import CompAnalytics
    import CompAnalytics.Contracts

    assert CompAnalytics.Contracts.ExecutionHandle is ExecutionHandle


@pytest.mark.parametrize(
    "name",
    [
        "CompAnalytics.Anything",
        "CompAnalytics.Contracts.Tables.Anything",
        "CompAnalytics.Contracts.QueryView.Anything",
        "CompAnalytics.Data",
    ],
)
def test_any_other_module_under_companalytics_names_what_is_supported(name):
    with pytest.raises(ImportError) as error:
        __import__(name)
    message = str(error.value)
    assert name in message
    served = message.split("serves only:", 1)[1].strip().split(", ")
    assert served == [
        "CompAnalytics.Contracts",
        "CompAnalytics.Contracts.Tables",
        "CompAnalytics.Contracts.QueryView",
        "CompAnalytics.Core",
    ]


def test_a_name_that_is_not_served_in_a_served_module_is_an_import_error():
    with pytest.raises(ImportError):
        from CompAnalytics.Contracts import Nope  # noqa: F401


def test_the_finder_is_installed_once_and_after_the_standard_finders():
    composapy.compat.install()
    composapy.compat.install()
    finders = [f for f in sys.meta_path if type(f).__name__ == "CompatFinder"]
    assert len(finders) == 1
    position = sys.meta_path.index(finders[0])
    # a finder another package adds later may follow it (importlib_metadata's, on 3.9), but none that was there first
    for standard in (
        importlib.machinery.BuiltinImporter,
        importlib.machinery.FrozenImporter,
        importlib.machinery.PathFinder,
    ):
        assert sys.meta_path.index(standard) < position


def test_the_finder_does_not_answer_for_other_names():
    for name in ("composapy_not_a_module", "numpy_not_a_module", "System_not_a_module"):
        with pytest.raises(ModuleNotFoundError):
            __import__(name)


def test_importing_composapy_installs_the_names_without_pythonnet():
    result = run_python(
        "import sys\n"
        "sys.modules['clr'] = None\n"
        "import composapy\n"
        "from CompAnalytics.Contracts.Tables import Table\n"
        "import composapy.contracts\n"
        "assert Table is composapy.contracts.Table\n"
        "print('ok')"
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_the_names_are_not_served_before_composapy_is_imported():
    result = run_python("import CompAnalytics")
    assert result.returncode != 0 and "ModuleNotFoundError" in result.stderr


# ----------------------------------------------------------------------------------------------
# Names that look like the package but are not
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "CompAnalyticsFoo",
        "CompAnalytics_Contracts",
        "CompAnalytics2",
        "compAnalytics",
        "companalytics.Contracts",
        "XCompAnalytics.Contracts",
    ],
)
def test_a_name_that_only_starts_like_the_package_is_not_served_and_is_not_refused_by_it(
    name,
):
    finder = next(f for f in sys.meta_path if type(f).__name__ == "CompatFinder")
    assert (
        finder.find_spec(name) is None
    )  # left for the other finders, with no message of its own
    with pytest.raises(ModuleNotFoundError) as error:
        __import__(name)
    assert "composapy serves only" not in str(error.value)


def test_the_package_name_itself_and_each_served_module_have_a_spec_without_being_imported():
    for name in (
        "CompAnalytics",
        "CompAnalytics.Contracts",
        "CompAnalytics.Contracts.Tables",
        "CompAnalytics.Contracts.QueryView",
        "CompAnalytics.Core",
    ):
        spec = importlib.util.find_spec(name)
        assert spec is not None and spec.name == name
        assert (
            spec.submodule_search_locations == []
        )  # a package, so children are looked for through the finder


def test_pinned_find_spec_raises_for_an_unserved_child_instead_of_returning_none():
    # Pinned, needs a decision: importlib.util.find_spec is documented to return None for a module that is not found, and
    # a tool that probes for modules this way gets the ModuleNotFoundError instead
    with pytest.raises(ModuleNotFoundError, match="composapy serves only"):
        importlib.util.find_spec("CompAnalytics.Anything")


def test_a_contract_class_is_not_a_module_so_importing_it_as_one_names_what_is_served():
    with pytest.raises(
        ModuleNotFoundError, match="CompAnalytics.Contracts.FileReference"
    ):
        import CompAnalytics.Contracts.FileReference  # noqa: F401


def test_from_the_package_import_an_unserved_name_is_an_import_error():
    with pytest.raises(ImportError):
        from CompAnalytics import Nope  # noqa: F401


def test_from_the_package_import_the_served_modules():
    from CompAnalytics import Contracts, Core

    assert Contracts.ExecutionHandle is ExecutionHandle
    assert Core.ContractSerializer is ContractSerializer


def test_every_served_name_is_in_the_list_these_tests_check():
    served = {
        (module, name)
        for module, names in composapy.compat._SERVED.items()
        for name in names
    }
    assert served == {(module, name) for module, name, _ in SERVED}


# ----------------------------------------------------------------------------------------------
# What a served module holds
# ----------------------------------------------------------------------------------------------


def test_a_served_module_has_no_all_and_a_star_import_takes_exactly_the_served_names():
    result = run_python(
        "import composapy\n"
        "import json\n"
        "out = {}\n"
        "for module in ('CompAnalytics.Contracts', 'CompAnalytics.Contracts.Tables',\n"
        "               'CompAnalytics.Contracts.QueryView', 'CompAnalytics.Core'):\n"
        "    namespace = {}\n"
        "    exec('from ' + module + ' import *', namespace)\n"
        "    namespace.pop('__builtins__')\n"
        "    imported = __import__(module, fromlist=['x'])\n"
        "    out[module] = [sorted(namespace), hasattr(imported, '__all__')]\n"
        "print(json.dumps(out))"
    )
    assert result.returncode == 0, result.stderr
    found = json.loads(result.stdout)
    for module, (star_names, has_all) in found.items():
        expected = sorted(name for m, name, _ in SERVED if m == module)
        assert star_names == expected, module
        assert has_all is False, module


def test_the_package_has_no_names_of_its_own_and_dir_of_a_served_module_lists_its_classes():
    import CompAnalytics.Contracts

    public = [n for n in dir(CompAnalytics.Contracts) if not n.startswith("_")]
    served = [name for m, name, _ in SERVED if m == "CompAnalytics.Contracts"]
    assert set(served) <= set(public)
    # a child module that was imported is an attribute too, and that is all that can be added
    assert set(public) - set(served) <= {"Tables", "QueryView"}


def test_a_served_module_is_a_package_with_no_file():
    import CompAnalytics.Core

    assert CompAnalytics.Core.__path__ == []
    assert not hasattr(CompAnalytics.Core, "__file__")
    assert CompAnalytics.Core.__spec__.name == "CompAnalytics.Core"
