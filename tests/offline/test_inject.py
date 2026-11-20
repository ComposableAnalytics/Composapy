"""Offline tests for composapy.notebook.inject: how return values are written to outputs.serialized.

The format is the one in Appendix A.5: a JSON list of KeyValuePairOfstringanyType entries, which the C# side
reads back. The expected output for floats and strings was checked against what the .NET
DataContractJsonSerializer wrote for the same values.
"""

import datetime
import decimal
import enum
import json
import math

import numpy as np
import pandas as pd
import pytest

from composapy._wire import codec
from composapy.auth import AuthMode
from composapy.contracts import ExecutionHandle, FileReference, Table
from composapy.contracts.file_reference import (
    CsvFileReference,
    ImageReference,
    KmlReference,
)
from composapy.notebook.inject import (
    KEY_VALUE_PAIR_TYPE,
    TypeNotSupportedError,
    serialize_return_values,
)
from composapy.session import Session

URI = "http://example.test/CompApp/"
HANDLE_JSON = {
    "__type": "ExecutionHandle:#CompAnalytics.Contracts",
    "AppId": None,
    "HandleId": "b509b089-1b5c-4c09-8a4b-0dd2d1a1c2aa",
    "Id": 671892,
}
UPLOADED_URI = "/CompApp/runs/b509b089-1b5c-4c09-8a4b-0dd2d1a1c2aa/5f051543-bf10-482a-8be1-7b11e87d2009/note.txt"
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
    "SqlQuery": "SELECT * FROM [t]",
    "TableName": "t",
}


class FakeTableService:
    def __init__(self):
        self.bodies = []

    def CreateTable(self, body):
        self.bodies.append(body)
        return codec.decode(json.dumps(TABLE_JSON))


class FakeFileUploadService:
    def __init__(self):
        self.calls = []

    def UploadFilesToRuns(self, body, _content_type=None, _query=None):
        self.calls.append((body, _content_type, _query))
        return [
            codec.decode(
                json.dumps(
                    {
                        "__type": "FileReference:#CompAnalytics.Contracts",
                        "Uri": UPLOADED_URI,
                    }
                )
            )
        ]


@pytest.fixture
def services():
    session = Session(uri=URI, auth_mode=AuthMode.TOKEN, credentials="token-for-tests")
    session.register()
    tables, uploads = FakeTableService(), FakeFileUploadService()
    session.services["TableService"] = tables
    session.services["FileUploadService"] = uploads
    yield tables, uploads
    Session.clear_registration()


@pytest.fixture
def handle():
    return codec.decode(json.dumps(HANDLE_JSON))


@pytest.fixture
def out(tmp_path):
    return tmp_path / "outputs.serialized"


def write_and_read(handle, out, values):
    serialize_return_values(handle, values, out)
    return json.loads(out.read_text(encoding="utf-8"))


def entry(key, value):
    return {"__type": KEY_VALUE_PAIR_TYPE, "key": key, "value": value}


# ----------------------------------------------------------------------------------------------
# The file format
# ----------------------------------------------------------------------------------------------


def test_the_appendix_a5_example_is_written_exactly(handle, out):
    serialize_return_values(handle, {"sum": 3}, out)
    assert json.loads(out.read_text(encoding="utf-8")) == [
        {
            "__type": "KeyValuePairOfstringanyType:#System.Collections.Generic",
            "key": "sum",
            "value": 3,
        }
    ]


def test_members_are_written_type_first_then_key_then_value(handle, out):
    serialize_return_values(handle, {"a": 1}, out)
    (item,) = json.loads(out.read_text(encoding="utf-8"), object_pairs_hook=list)
    assert [name for name, _ in item] == ["__type", "key", "value"]


def test_entries_keep_the_order_of_the_return_values(handle, out):
    written = write_and_read(handle, out, {"z": 1, "a": 2, "m": 3})
    assert [item["key"] for item in written] == ["z", "a", "m"]


def test_no_return_values_gives_an_empty_list(handle, out):
    assert write_and_read(handle, out, {}) == []


def test_the_file_has_no_byte_order_mark(handle, out):
    serialize_return_values(handle, {"a": 1}, out)
    assert out.read_bytes().startswith(b'[{"')  # .NET wrote none either


def test_the_output_path_can_be_text_or_a_path_and_an_old_file_is_replaced(handle, out):
    out.write_text("old contents", encoding="utf-8")
    serialize_return_values(handle, {"a": 1}, str(out))
    assert json.loads(out.read_text(encoding="utf-8")) == [entry("a", 1)]


def test_the_written_file_reads_back_through_the_codec(handle, out):
    serialize_return_values(handle, {"sum": 3, "name": "x"}, out)
    items = codec.decode(out.read_text(encoding="utf-8"))
    assert [(i.key, i.value) for i in items] == [("sum", 3), ("name", "x")]


# ----------------------------------------------------------------------------------------------
# The plain values
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        3,
        -7,
        0,
        "text",
        "",
        True,
        False,
        None,
        5.5,
        -0.25,
        "café 中文",
        "a/b \\ c",
        2147483648,
    ],
    ids=[
        "int",
        "negative",
        "zero",
        "str",
        "empty",
        "true",
        "false",
        "none",
        "float",
        "negative-float",
        "non-ascii",
        "slash-and-backslash",
        "above-int32",
    ],
)
def test_plain_values_are_written_as_json_values(handle, out, value):
    assert write_and_read(handle, out, {"v": value}) == [entry("v", value)]


def test_a_bool_stays_a_bool_and_is_not_turned_into_a_number(handle, out):
    serialize_return_values(handle, {"v": True}, out)
    assert out.read_text(encoding="utf-8").endswith('"value":true}]')


def test_an_integer_above_the_int32_range_is_now_written(handle, out):
    # System.Int32(x) raised OverflowError here in 0.13.x
    assert write_and_read(handle, out, {"big": 2**40}) == [entry("big", 2**40)]


@pytest.mark.parametrize(
    "value, text", [(3.0, "3"), (-2.0, "-2"), (0.0, "0"), (1234567.0, "1234567")]
)
def test_a_whole_number_float_is_written_without_a_point_as_dotnet_did(
    handle, out, value, text
):
    # .NET wrote 3.0 as 3, which the C# side reads as an Int32; 3.0 would read as a Decimal
    serialize_return_values(handle, {"v": value}, out)
    assert out.read_text(encoding="utf-8").endswith(f'"value":{text}}}]')


@pytest.mark.parametrize(
    "value", [5.5, 0.00001, 1e22, 1e16, 123456789012345680000.0, -1.5e-7]
)
def test_other_floats_are_written_unchanged(handle, out, value):
    written = write_and_read(handle, out, {"v": value})
    assert written == [entry("v", value)] and isinstance(written[0]["value"], float)


# ----------------------------------------------------------------------------------------------
# Types that are not supported
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        [1, 2],
        (1, 2),
        {"a": 1},
        {1, 2},
        b"bytes",
        np.float64(1.5),
        np.int64(3),
        object(),
        complex(1, 2),
    ],
    ids=[
        "list",
        "tuple",
        "dict",
        "set",
        "bytes",
        "numpy-float",
        "numpy-int",
        "object",
        "complex",
    ],
)
def test_an_unsupported_type_raises_and_names_the_type(handle, out, value):
    with pytest.raises(
        TypeNotSupportedError, match="is not currently supported"
    ) as error:
        serialize_return_values(handle, {"v": value}, out)
    assert str(type(value)) in str(error.value)


def test_an_unsupported_value_stops_the_whole_write(handle, out):
    with pytest.raises(TypeNotSupportedError):
        serialize_return_values(handle, {"good": 1, "bad": [1, 2], "also_good": 2}, out)
    assert (
        not out.exists()
    )  # as before: the file is written only if every value is fine


def test_a_file_reference_subclass_that_was_not_supported_before_is_still_refused(
    handle, out, tmp_path
):
    reference = FileReference.Create(str(tmp_path / "a.kml"), "/CompApp/runs/x/a.kml")
    assert type(reference) is KmlReference
    with pytest.raises(TypeNotSupportedError):
        serialize_return_values(handle, {"v": reference}, out)


# ----------------------------------------------------------------------------------------------
# Tables, data frames, and files
# ----------------------------------------------------------------------------------------------


def test_a_table_is_written_as_it_is(handle, out):
    table = codec.decode(json.dumps(TABLE_JSON))
    assert write_and_read(handle, out, {"t": table}) == [entry("t", TABLE_JSON)]


def test_a_data_frame_is_sent_to_a_new_table_and_that_table_is_written(
    handle, out, services
):
    tables, _ = services
    written = write_and_read(handle, out, {"df": pd.DataFrame({"a": [1, 2]})})
    assert written == [entry("df", TABLE_JSON)]
    (body,) = tables.bodies
    sent = json.loads(body, object_pairs_hook=list)
    assert [key for key, _ in sent] == ["ExecutionHandle", "Columns", "Rows"]
    assert dict(sent)["ExecutionHandle"] == [(k, v) for k, v in HANDLE_JSON.items()]


@pytest.mark.parametrize(
    "kind, name",
    [
        (FileReference, "note.txt"),
        (CsvFileReference, "data.csv"),
        (ImageReference, "pic.png"),
    ],
)
def test_a_local_file_reference_is_uploaded_and_the_servers_reference_is_written(
    handle, out, services, tmp_path, kind, name
):
    _, uploads = services
    local = tmp_path / name
    local.write_bytes(b"hello\n")
    reference = FileReference.Create(
        str(local), "/CompApp/runs/x/" + name, as_type=kind
    )

    written = write_and_read(handle, out, {"f": reference})

    assert written == [
        entry(
            "f",
            {"__type": "FileReference:#CompAnalytics.Contracts", "Uri": UPLOADED_URI},
        )
    ]
    ((body, content_type, query),) = uploads.calls
    assert (
        content_type.startswith("multipart/form-data; boundary=")
        and b"hello" not in body
    )  # the bytes go up Base64-encoded
    assert query == {"HandleId": HANDLE_JSON["HandleId"], "Id": "671892"}


def test_a_file_reference_that_is_already_on_the_server_is_written_unchanged(
    handle, out, services
):
    _, uploads = services
    reference = codec.decode(
        json.dumps(
            {"__type": "FileReference:#CompAnalytics.Contracts", "Uri": UPLOADED_URI}
        )
    )
    assert reference.LocalFile is None
    assert write_and_read(handle, out, {"f": reference}) == [
        entry(
            "f",
            {"__type": "FileReference:#CompAnalytics.Contracts", "Uri": UPLOADED_URI},
        )
    ]
    assert uploads.calls == []


def test_a_mix_of_values_is_written_in_order(handle, out, services, tmp_path):
    local = tmp_path / "note.txt"
    local.write_bytes(b"x")
    values = {
        "n": 1,
        "s": "two",
        "f": 3.5,
        "b": False,
        "nothing": None,
        "df": pd.DataFrame({"a": [1]}),
        "file": FileReference.Create(str(local), "/CompApp/runs/x/note.txt"),
    }
    written = write_and_read(handle, out, values)
    assert [item["key"] for item in written] == list(values)
    assert [item["value"] for item in written[:5]] == [1, "two", 3.5, False, None]
    assert (
        written[5]["value"]["__type"].startswith("Table:")
        and written[6]["value"]["Uri"] == UPLOADED_URI
    )


# ----------------------------------------------------------------------------------------------
# The inputs file (Appendix A.5), which the wrappers read
# ----------------------------------------------------------------------------------------------


def test_the_appendix_a5_inputs_example_decodes_with_a_typed_execution_handle():
    text = (
        '[{"__type":"KeyValuePairOfstringanyType:#System.Collections.Generic","key":"test1","value":1},'
        ' {"__type":"KeyValuePairOfstringanyType:#System.Collections.Generic","key":"_execution_handle",'
        '  "value":{"__type":"ExecutionHandle:#CompAnalytics.Contracts","AppId":null,'
        '"HandleId":"b509b089-1b5c-4c09-8a4b-0dd2d1a1c2aa","Id":671892}}]'
    )
    first, second = codec.decode(text)
    assert (first.key, first.value) == ("test1", 1)
    assert second.key == "_execution_handle" and type(second.value) is ExecutionHandle
    assert second.value.Id == 671892
    assert (
        json.loads(codec.encode(second.value)) == HANDLE_JSON
    )  # what the wrapper puts in the environment variable


def test_the_file_has_no_space_after_a_colon_or_a_comma_as_dotnet_wrote_it(handle, out):
    serialize_return_values(handle, {"a": 1, "b": 2.5, "c": True, "d": None}, out)
    text = out.read_text(encoding="utf-8")
    assert ": " not in text and ", " not in text
    assert text == (
        '[{"__type":"KeyValuePairOfstringanyType:#System.Collections.Generic","key":"a","value":1},'
        '{"__type":"KeyValuePairOfstringanyType:#System.Collections.Generic","key":"b","value":2.5},'
        '{"__type":"KeyValuePairOfstringanyType:#System.Collections.Generic","key":"c","value":true},'
        '{"__type":"KeyValuePairOfstringanyType:#System.Collections.Generic","key":"d","value":null}]'
    )


# ----------------------------------------------------------------------------------------------
# NaN, infinity, and the other edges of a float
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, text",
    [
        (float("nan"), "NaN"),
        (float("inf"), "Infinity"),
        (float("-inf"), "-Infinity"),
        (np.nan, "NaN"),
    ],
    ids=["nan", "inf", "-inf", "numpy-nan"],
)
def test_nan_and_infinity_are_written_bare_as_the_platforms_serializer_reads_them(
    handle, out, value, text
):
    # not "NaN" in quotes and not null: DataContractJsonSerializer reads the bare words into a double
    serialize_return_values(handle, {"v": value}, out)
    assert out.read_text(encoding="utf-8").endswith(f'"value":{text}}}]')


def test_nan_and_infinity_read_back_as_the_same_floats_through_the_codec(handle, out):
    serialize_return_values(
        handle, {"a": float("nan"), "b": float("inf"), "c": float("-inf")}, out
    )
    a, b, c = (item.value for item in codec.decode(out.read_text(encoding="utf-8")))
    assert math.isnan(a) and b == float("inf") and c == float("-inf")


@pytest.mark.parametrize(
    "value, text",
    [(-0.0, "0"), (1e15, "1000000000000000"), (float(2**53), "9007199254740992")],
)
def test_a_whole_number_float_below_1e16_is_written_as_an_integer_even_at_the_edges(
    handle, out, value, text
):
    serialize_return_values(handle, {"v": value}, out)
    assert out.read_text(encoding="utf-8").endswith(f'"value":{text}}}]')


# ----------------------------------------------------------------------------------------------
# Booleans, None, and strings that look like them
# ----------------------------------------------------------------------------------------------


def test_booleans_none_and_strings_that_look_like_them_keep_their_kind(handle, out):
    values = {
        "t": True,
        "f": False,
        "n": None,
        "empty": "",
        "zero_text": "0",
        "zero": 0,
        "none_text": "None",
        "true_text": "true",
        "null_text": "null",
        "nan_text": "NaN",
    }
    written = write_and_read(handle, out, values)
    assert [item["value"] for item in written] == list(values.values())
    assert [type(item["value"]) for item in written] == [
        type(v) for v in values.values()
    ]


def test_a_key_is_written_as_text_whatever_characters_it_has(handle, out):
    keys = ['quote"d', "back\\slash", "café", "", "line\nbreak", "a/b"]
    written = write_and_read(handle, out, {key: 1 for key in keys})
    assert [item["key"] for item in written] == keys


class Color(enum.IntEnum):
    RED = 1


class Label(str):
    pass


@pytest.mark.parametrize(
    "value",
    [Color.RED, Label("x"), decimal.Decimal("1.5"), datetime.date(2025, 1, 2)],
    ids=["int-subclass", "str-subclass", "decimal", "date"],
)
def test_pinned_only_the_exact_supported_types_are_accepted_so_a_subclass_is_refused(
    handle, out, value
):
    # Pinned, needs a decision: the check is on the exact type, so an IntEnum member or a str subclass is refused although
    # it is an int or a str
    with pytest.raises(TypeNotSupportedError):
        serialize_return_values(handle, {"v": value}, out)


# ----------------------------------------------------------------------------------------------
# Without an execution handle
# ----------------------------------------------------------------------------------------------


def test_plain_values_and_a_server_side_file_reference_need_no_execution_handle(out):
    reference = codec.decode(
        json.dumps(
            {"__type": "FileReference:#CompAnalytics.Contracts", "Uri": UPLOADED_URI}
        )
    )
    written = write_and_read(
        None, out, {"n": 1, "s": "x", "none": None, "f": reference}
    )
    assert [item["key"] for item in written] == ["n", "s", "none", "f"]
    assert written[3]["value"]["Uri"] == UPLOADED_URI


def test_pinned_a_data_frame_without_an_execution_handle_is_sent_with_a_null_handle(
    out, services
):
    # Pinned, needs a decision: a script run with no _execution_handle entry sends ExecutionHandle: null, and what the
    # server makes of that is the server's to say
    tables, _ = services
    write_and_read(None, out, {"df": pd.DataFrame({"a": [1]})})
    (body,) = tables.bodies
    assert json.loads(body)["ExecutionHandle"] is None


def test_pinned_a_local_file_without_an_execution_handle_fails_with_an_attribute_error_and_writes_nothing(
    out, services, tmp_path
):
    # Pinned, needs a decision: the error is "'NoneType' object has no attribute 'HandleId'", not a message that says
    # there is no run to upload the file to
    _, uploads = services
    local = tmp_path / "note.txt"
    local.write_bytes(b"x")
    reference = FileReference.Create(str(local), "/CompApp/runs/x/note.txt")
    with pytest.raises(AttributeError, match="HandleId"):
        serialize_return_values(None, {"f": reference}, out)
    assert uploads.calls == [] and not out.exists()


# ----------------------------------------------------------------------------------------------
# When a later value is refused
# ----------------------------------------------------------------------------------------------


def test_a_refused_value_leaves_an_earlier_outputs_file_as_it_was(handle, out):
    out.write_text("previous run", encoding="utf-8")
    with pytest.raises(TypeNotSupportedError):
        serialize_return_values(handle, {"ok": 1, "bad": [1]}, out)
    assert out.read_text(encoding="utf-8") == "previous run"


def test_every_value_is_checked_before_any_is_sent_so_an_earlier_data_frame_is_not_made_a_table(
    handle, out, services, tmp_path
):
    tables, uploads = services
    local = tmp_path / "note.txt"
    local.write_bytes(b"x")
    reference = FileReference.Create(str(local), "/CompApp/runs/x/note.txt")
    with pytest.raises(TypeNotSupportedError):
        serialize_return_values(
            handle,
            {"df": pd.DataFrame({"a": [1]}), "file": reference, "bad": {1, 2}},
            out,
        )
    assert tables.bodies == [] and uploads.calls == [] and not out.exists()
