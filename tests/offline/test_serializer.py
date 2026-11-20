"""Offline tests for composapy.contracts.ContractSerializer, the stand-in for CompAnalytics.Core.ContractSerializer.

It is used as a class, never instantiated: ContractSerializer.Serialize(x), ContractSerializer.Deserialize(text, T),
and the form the papermill translators emit, ContractSerializer.Deserialize[T](text).
"""

import json

import pytest

from composapy._wire import codec
from composapy.contracts import (
    ContractSerializer,
    ExecutionHandle,
    FileReference,
    ImageReference,
    Table,
)

HANDLE_JSON = {
    "__type": "ExecutionHandle:#CompAnalytics.Contracts",
    "AppId": None,
    "HandleId": "b509b089-1b5c-4c09-8a4b-0dd2d1a1c2aa",
    "Id": 671892,
}
FILE_JSON = {
    "__type": "FileReference:#CompAnalytics.Contracts",
    "Uri": '/CompApp/runs/x/it\'s "a" \\ b.txt',
}
TABLE_JSON = {
    "__type": "Table:#CompAnalytics.Contracts.Tables",
    "Columns": [
        {
            "__type": "TableColumn:#CompAnalytics.Contracts.Tables",
            "Name": "a",
            "Type": "BIGINT",
        }
    ],
    "Headers": ["a"],
    "RootExecutionHandle": HANDLE_JSON,
    "SqlQuery": "SELECT * FROM [t] WHERE a = 'x\\y'",
    "TableName": "t",
}
CASES = [
    (ExecutionHandle, HANDLE_JSON),
    (FileReference, FILE_JSON),
    (Table, TABLE_JSON),
]
IDS = ["handle", "file-reference", "table"]


def test_the_class_is_exported_from_composapy_contracts():
    import composapy.contracts

    assert composapy.contracts.ContractSerializer is ContractSerializer


@pytest.mark.parametrize("wire", [wire for _, wire in CASES], ids=IDS)
def test_serialize_is_the_codecs_encode(wire):
    obj = codec.decode(json.dumps(wire))
    assert ContractSerializer.Serialize(obj) == codec.encode(obj)
    assert json.loads(ContractSerializer.Serialize(obj)) == wire


@pytest.mark.parametrize("kind, wire", CASES, ids=IDS)
def test_deserialize_with_the_type_as_an_argument(kind, wire):
    obj = ContractSerializer.Deserialize(json.dumps(wire), kind)
    assert type(obj) is kind and obj == codec.decode(json.dumps(wire))


@pytest.mark.parametrize("kind, wire", CASES, ids=IDS)
def test_deserialize_with_the_type_in_square_brackets(kind, wire):
    obj = ContractSerializer.Deserialize[kind](json.dumps(wire))
    assert type(obj) is kind and obj == codec.decode(json.dumps(wire))


def test_the_bracket_form_is_what_the_papermill_translators_emit():
    text = json.dumps(HANDLE_JSON)
    obj = eval(f"ContractSerializer.Deserialize[ExecutionHandle]({text!r})")
    assert obj.Id == 671892


def test_a_value_of_another_type_is_refused_in_both_forms():
    text = json.dumps(HANDLE_JSON)
    with pytest.raises(ValueError, match="Table"):
        ContractSerializer.Deserialize(text, Table)
    with pytest.raises(ValueError, match="Table"):
        ContractSerializer.Deserialize[Table](text)


def test_a_file_reference_subclass_is_accepted_as_its_base():
    text = json.dumps(
        {
            "__type": "ImageReference:#CompAnalytics.Contracts",
            "Uri": "/CompApp/runs/x/a.png",
        }
    )
    obj = ContractSerializer.Deserialize(text, FileReference)
    assert type(obj) is ImageReference and isinstance(obj, FileReference)


def test_a_round_trip_through_a_file_has_no_byte_order_mark(tmp_path):
    path = tmp_path / "out.json"
    obj = codec.decode(json.dumps(FILE_JSON))
    ContractSerializer.SerializeToFile(obj, path)
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert (
        ContractSerializer.Deserialize(path.read_text(encoding="utf-8"), FileReference)
        == obj
    )


def test_the_path_can_be_text_too(tmp_path):
    path = tmp_path / "out.json"
    ContractSerializer.SerializeToFile(codec.decode(json.dumps(HANDLE_JSON)), str(path))
    assert json.loads(path.read_text(encoding="utf-8")) == HANDLE_JSON
