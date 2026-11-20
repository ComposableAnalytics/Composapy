"""Offline tests for how a module's input or result value follows the type its contract declares.

The calculator result 3.0 comes back from the server as the JSON number 3, so without the declared type it is an int.
"""

import decimal
import json

import pytest

from composapy._wire import codec
from composapy.dataflow.models import Input, Result


def contract(declared, value, collection=False, kind="ModuleOutputOfdouble"):
    return codec.decode(
        json.dumps(
            {
                "__type": f"{kind}:#CompAnalytics.Contracts",
                "ArgumentTypeName": declared,
                "ArgumentTypeFriendlyName": declared.split(".")[-1],
                "IsCollection": collection,
                "Name": "Result",
                "ValueObj": value,
            }
        )
    )


@pytest.mark.parametrize("declared", ["System.Double", "System.Single"])
@pytest.mark.parametrize("value", [3, 0, -7, 5.5, 2**40])
def test_a_double_or_single_is_a_float_whatever_the_wire_number_looked_like(
    declared, value
):
    result = Result(contract(declared, value)).value
    assert type(result) is float and result == value


def test_a_decimal_is_a_decimal_and_keeps_its_digits():
    for value, expected in (
        (3, decimal.Decimal("3")),
        (1.5, decimal.Decimal("1.5")),
        (-0.1, decimal.Decimal("-0.1")),
    ):
        result = Result(contract("System.Decimal", value)).value
        assert type(result) is decimal.Decimal and result == expected


def test_a_collection_of_doubles_is_converted_element_by_element():
    result = Result(contract("System.Double", [1, 2.5, None, 3], collection=True)).value
    assert result == [1.0, 2.5, None, 3.0] and [type(v) for v in result] == [
        float,
        float,
        type(None),
        float,
    ]


@pytest.mark.parametrize(
    "declared",
    [
        "System.Int32",
        "System.Int64",
        "System.String",
        "System.Boolean",
        "System.Object",
        "System.DateTime",
    ],
)
def test_every_other_declared_type_is_left_as_it_came(declared):
    for value in (3, 2.5, "text", True, None):
        assert Result(contract(declared, value)).value == value
        assert type(Result(contract(declared, value)).value) is type(value)


def test_a_missing_value_and_a_bool_are_not_turned_into_numbers():
    assert Result(contract("System.Double", None)).value is None
    assert Result(contract("System.Double", True)).value is True


def test_an_input_follows_its_declared_type_too_and_assigning_a_value_does_not_convert_it():
    item = Input(contract("System.Double", 4, kind="ModuleInputOfdouble"))
    assert type(item.value) is float
    item.value = 9
    assert (
        item.contract.ValueObj == 9 and type(item.contract.ValueObj) is int
    )  # what is sent is what was assigned


def test_a_contract_without_a_declared_type_is_unchanged():
    bare = codec.decode(
        json.dumps(
            {
                "__type": "ModuleOutput:#CompAnalytics.Contracts",
                "Name": "x",
                "ValueObj": 3,
            }
        )
    )
    assert Result(bare).value == 3 and type(Result(bare).value) is int


def test_a_table_result_is_untouched():
    table = codec.decode(
        json.dumps(
            {
                "__type": "ModuleOutputOfTable:#CompAnalytics.Contracts",
                "ArgumentTypeName": "CompAnalytics.Contracts.Tables.Table",
                "ValueObj": {
                    "__type": "Table:#CompAnalytics.Contracts.Tables",
                    "Headers": ["a"],
                    "Columns": [],
                },
            }
        )
    )
    assert type(Result(table).value).__name__ == "Table"
