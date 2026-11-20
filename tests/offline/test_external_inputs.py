"""Offline tests for what DataFlowObject writes into a module's input before a run, using the real DataFlow test files.

No server is called: the values are written into the contract and read back, which is what the request would carry.
"""

import decimal
import json
from pathlib import Path

import pandas as pd
import pytest

from composapy._wire import codec
from composapy.contracts import Table
from composapy.dataflow.models import (
    _VALUE_TYPE_DEFAULTS,
    DataFlowObject,
    Input,
    Result,
    _by_declared_type,
)

FILES = Path(__file__).resolve().parent.parent / "TestFiles"


def flow(name):
    return DataFlowObject(codec.decode((FILES / name).read_text(encoding="utf-8-sig")))


def external(flow_object, input_name):
    """The module that takes the external input with this name (other modules have no Name input)."""
    for module in flow_object.modules:
        if (
            "Name" in module.contract.ModuleInputs.Indexes.Keys
            and module.contract.ModuleInputs["Name"].ValueObj == input_name
        ):
            return module
    raise KeyError(input_name)


def input_value(flow_object, input_name):
    return external(flow_object, input_name).contract.ModuleInputs["Input"].ValueObj


def test_the_int_input_files_input_is_declared_as_an_int32():
    assert (
        external(flow("external_input_int.json"), "IntInput")
        .contract.ModuleInputs["Input"]
        .ArgumentTypeName
        == "System.Int32"
    )


@pytest.mark.parametrize("value", [0, 5, -3, 2147483647, 5.5, "7", True, [1, 2]])
def test_a_value_is_written_as_it_was_given(value):
    f = flow("external_input_int.json")
    f._write_external_inputs({"IntInput": value})
    written = input_value(f, "IntInput")
    assert written == value and type(written) is type(value)


def test_none_for_an_int32_input_becomes_zero_as_it_did_in_dotnet():
    f = flow("external_input_int.json")
    f._write_external_inputs({"IntInput": None})
    assert input_value(f, "IntInput") == 0 and type(input_value(f, "IntInput")) is int


def test_none_for_a_string_input_stays_none():
    f = flow("table_column_dtypes.json")
    f._write_external_inputs({"ColumnType": None, "ColumnData": ["a"]})
    assert input_value(f, "ColumnType") is None


@pytest.mark.parametrize(
    "declared, expected",
    [
        ("System.Int64", 0),
        ("System.Double", 0.0),
        ("System.Single", 0.0),
        ("System.Boolean", False),
        ("System.Decimal", 0),
        ("System.Byte", 0),
    ],
)
def test_each_value_type_has_its_default(declared, expected):
    f = flow("external_input_int.json")
    external(f, "IntInput").contract.ModuleInputs["Input"][
        "ArgumentTypeName"
    ] = declared
    f._write_external_inputs({"IntInput": None})
    assert input_value(f, "IntInput") == expected and type(
        input_value(f, "IntInput")
    ) is type(expected)


def test_a_data_frame_is_left_for_the_conversion_after_the_context_is_created():
    f = flow("external_input_table.json")
    before = input_value(f, "TableInput")
    f._write_external_inputs({"TableInput": pd.DataFrame({"a": [1]})})
    assert input_value(f, "TableInput") == before


@pytest.mark.parametrize(
    "value", [[1, 2, 3], "text", 5, {"a": 1}, pd.Series([1, 2]), (1, 2), b"x"]
)
def test_a_table_input_refuses_anything_that_is_not_a_data_frame_or_a_table(value):
    f = flow("external_input_table.json")
    with pytest.raises(TypeError, match="takes a pandas DataFrame or a Table"):
        f._write_external_inputs({"TableInput": value})


def test_a_table_input_accepts_a_table_and_none():
    f = flow("external_input_table.json")
    table = codec.decode(
        '{"__type":"Table:#CompAnalytics.Contracts.Tables","Headers":["a"],"Columns":[]}'
    )
    assert isinstance(table, Table)
    f._write_external_inputs({"TableInput": table})
    assert input_value(f, "TableInput") is table
    f._write_external_inputs({"TableInput": None})
    assert input_value(f, "TableInput") is None


def test_the_refusal_names_the_input_and_the_type_given():
    f = flow("external_input_table.json")
    with pytest.raises(TypeError) as error:
        f._write_external_inputs({"TableInput": [1]})
    assert "'TableInput'" in str(error.value) and "list" in str(error.value)


# ----------------------------------------------------------------------------------------------
# An input that was not given
# ----------------------------------------------------------------------------------------------


def test_a_table_input_that_was_not_given_is_left_as_it_is():
    f = flow("external_input_table.json")
    before = input_value(f, "TableInput")

    f._write_external_inputs({"SomethingElse": 1})  # was a KeyError for 'TableInput'

    assert input_value(f, "TableInput") == before


def test_a_run_with_other_inputs_given_leaves_the_missing_table_and_file_inputs_alone():
    for name in ("external_input_table.json", "external_input_file.json"):
        f = flow(name)
        # Nothing is converted or uploaded for an input that was not given, so no session or run is needed
        f._post_context_setup_steps({"SomethingElse": 1}, execution_handle=None)


# ----------------------------------------------------------------------------------------------
# The other value types that None becomes a default for
# ----------------------------------------------------------------------------------------------


def declare(f, input_name, declared):
    external(f, input_name).contract.ModuleInputs["Input"][
        "ArgumentTypeName"
    ] = declared


def test_the_types_that_have_a_default_are_the_dotnet_value_types_that_cannot_hold_null():
    assert _VALUE_TYPE_DEFAULTS == {
        "System.Int16": 0,
        "System.Int32": 0,
        "System.Int64": 0,
        "System.UInt16": 0,
        "System.UInt32": 0,
        "System.UInt64": 0,
        "System.Byte": 0,
        "System.SByte": 0,
        "System.Double": 0.0,
        "System.Single": 0.0,
        "System.Decimal": 0,
        "System.Boolean": False,
    }


@pytest.mark.parametrize(
    "declared",
    ["System.Int16", "System.UInt16", "System.UInt32", "System.UInt64", "System.SByte"],
)
def test_none_for_the_remaining_integer_types_becomes_an_integer_zero(declared):
    f = flow("external_input_int.json")
    declare(f, "IntInput", declared)
    f._write_external_inputs({"IntInput": None})
    assert input_value(f, "IntInput") == 0 and type(input_value(f, "IntInput")) is int


@pytest.mark.parametrize(
    "declared",
    [
        "System.String",
        "System.DateTime",
        "System.Object",
        "System.Nullable`1[[System.Int32, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]]",
        "System.Collections.Generic.List`1[[System.Object, mscorlib]]",
        "",
        None,
    ],
    ids=["string", "datetime", "object", "nullable-int", "list", "empty", "undeclared"],
)
def test_none_stays_none_for_a_type_that_can_hold_null(declared):
    f = flow("external_input_int.json")
    declare(f, "IntInput", declared)
    f._write_external_inputs({"IntInput": None})
    assert input_value(f, "IntInput") is None


@pytest.mark.parametrize(
    "declared, value",
    [
        ("System.Int32", 2**31),
        ("System.Int32", 2**70),
        ("System.Int32", -(2**70)),
        ("System.UInt16", -1),
        ("System.Byte", 300),
    ],
)
def test_a_number_the_declared_type_cannot_hold_is_written_as_it_is_for_the_server_to_refuse(
    declared, value
):
    # The 0.13.x client raised OverflowError for it; the decision (Decision Log, 2026-10-27) is that the server refuses it
    f = flow("external_input_int.json")
    declare(f, "IntInput", declared)
    f._write_external_inputs({"IntInput": value})
    written = input_value(f, "IntInput")
    assert written == value and type(written) is int
    member = external(f, "IntInput").contract.ModuleInputs["Input"]
    assert codec.encode(member).endswith(
        f'"ValueObj": {value}}}'
    )  # exactly, not as a float


def test_a_value_written_into_a_double_input_stays_an_int_in_the_request_but_reads_as_a_float():
    f = flow("external_input_int.json")
    declare(f, "IntInput", "System.Double")
    f._write_external_inputs({"IntInput": 3})
    member = external(f, "IntInput").contract.ModuleInputs["Input"]
    assert member.ValueObj == 3 and type(member.ValueObj) is int
    read = Input(member).value
    assert read == 3.0 and type(read) is float


# ----------------------------------------------------------------------------------------------
# Reading a value by its declared type
# ----------------------------------------------------------------------------------------------


def member(declared, value, collection=False, kind=Input, **more):
    return kind(
        codec.decode(
            json.dumps(
                {
                    "Name": "x",
                    "ArgumentTypeName": declared,
                    "ArgumentTypeFriendlyName": declared.split(".")[-1],
                    "IsCollection": collection,
                    "ValueObj": value,
                    **more,
                }
            )
        )
    )


@pytest.mark.parametrize("kind", [Input, Result], ids=["input", "result"])
@pytest.mark.parametrize("declared", ["System.Double", "System.Single"])
def test_a_double_or_single_that_the_wire_wrote_without_a_fraction_reads_as_a_float(
    kind, declared
):
    extra = {"ResultId": 5} if kind is Result else {}
    read = member(declared, 3, kind=kind, **extra).value
    assert read == 3.0 and type(read) is float


@pytest.mark.parametrize("kind", [Input, Result], ids=["input", "result"])
def test_a_decimal_reads_as_a_decimal_from_an_int_or_a_float(kind):
    extra = {"ResultId": 5} if kind is Result else {}
    assert member("System.Decimal", 3, kind=kind, **extra).value == decimal.Decimal(3)
    assert (
        type(member("System.Decimal", 3, kind=kind, **extra).value) is decimal.Decimal
    )
    # through the text of the float, so 0.1 is Decimal("0.1") and not its binary expansion
    assert member("System.Decimal", 0.1, kind=kind, **extra).value == decimal.Decimal(
        "0.1"
    )


def test_a_decimal_collection_reads_as_a_list_of_decimals():
    read = member("System.Decimal", [1, 2.5, 3], collection=True).value
    assert read == [decimal.Decimal(1), decimal.Decimal("2.5"), decimal.Decimal(3)]
    assert all(type(item) is decimal.Decimal for item in read)


def test_a_double_collection_reads_as_a_list_of_floats_and_an_empty_one_as_an_empty_list():
    read = member("System.Double", [1, 2, 2.5], collection=True).value
    assert read == [1.0, 2.0, 2.5] and all(type(item) is float for item in read)
    assert member("System.Double", [], collection=True).value == []


def test_pinned_a_none_or_a_bool_inside_a_decimal_or_double_collection_is_left_as_it_is():
    # Pinned, needs a decision: _as_float and _as_decimal pass None and bool through, so a bool stays True and not 1.0
    assert member("System.Decimal", [None, True, 1], collection=True).value == [
        None,
        True,
        decimal.Decimal(1),
    ]
    assert member("System.Double", [None, False, 1], collection=True).value == [
        None,
        False,
        1.0,
    ]


@pytest.mark.parametrize("value", [None, "7", (1, 2)])
def test_pinned_a_collection_whose_value_is_not_a_list_is_not_converted_item_by_item(
    value,
):
    # Pinned, needs a decision: a tuple of ints for a Double collection stays a tuple of ints
    contract = {"ArgumentTypeName": "System.Double", "IsCollection": True}
    read = _by_declared_type(contract, value)
    assert read == value and type(read) is type(value)


@pytest.mark.parametrize("value", [None, True, "text", [1]])
def test_a_scalar_that_is_not_a_number_is_left_as_it_is(value):
    read = member("System.Double", value).value
    assert read == value and not isinstance(read, float)


def test_by_declared_type_leaves_other_types_alone():
    for declared in ("System.Int32", "System.String", None):
        assert _by_declared_type({"ArgumentTypeName": declared}, 3) == 3
        assert _by_declared_type({"ArgumentTypeName": declared}, [1]) == [1]


def test_an_int_collection_is_the_stored_list_and_an_append_to_it_persists():
    m = member("System.Int32", [1, 2], collection=True)
    m.value.append(3)
    assert m.value == [1, 2, 3] and m.contract.ValueObj == [1, 2, 3]


@pytest.mark.parametrize(
    "declared", ["System.Double", "System.Single", "System.Decimal"]
)
def test_an_append_to_a_double_single_or_decimal_collection_persists(declared):
    m = member(declared, [1, 2], collection=True)
    m.value.append(3)
    assert len(m.value) == 3
