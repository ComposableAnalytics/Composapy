"""Offline tests for the wire codec and the operation manifest.

They need no .NET, no server, and no credentials. They read the fixtures in tests/TestFiles, the live
responses saved in tests/wire_captures, and, when the product tree is present, the service interfaces in
Product\\CompAnalytics.IServices.
"""

import copy
import importlib.util
import json
import pickle
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from composapy._wire import codec, objects
from composapy._wire.objects import ContractObject, KeyedList, NetList

TESTS_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = TESTS_DIR.parent
CAPTURES_DIR = TESTS_DIR / "wire_captures"
FIXTURES_DIR = TESTS_DIR / "TestFiles"
OPERATIONS_JSON = ROOT_DIR / "composapy" / "_wire" / "operations.json"
INTERFACES_DIR = ROOT_DIR.parent.parent / "Product" / "CompAnalytics.IServices"

needs_product = pytest.mark.skipif(
    not INTERFACES_DIR.is_dir(), reason="the product source tree is not present"
)


# ----------------------------------------------------------------------------------------------
# Round trip over every fixture and every captured JSON body
# ----------------------------------------------------------------------------------------------


def _as_json_text(body):
    """The JSON text of a captured body, or None when the body is not JSON (an HTML page, raw bytes)."""
    if isinstance(body, dict) and set(body) == {"encoding", "value"}:
        # a body that was not parsed when it was captured is stored as {"encoding": "text", "value": "..."}
        if body["encoding"] != "text":
            return None
        try:
            parsed = json.loads(body["value"])
        except ValueError:
            return None
        return body["value"] if isinstance(parsed, (dict, list)) else None
    if isinstance(body, (dict, list)):
        return json.dumps(body)
    return None


def _round_trip_cases():
    cases = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        cases.append(("TestFiles/" + path.name, path.read_text(encoding="utf-8-sig")))
    for path in sorted(CAPTURES_DIR.glob("*.json")):
        capture = json.loads(path.read_text(encoding="utf-8"))
        for part in ("RequestBody", "ResponseBody"):
            text = _as_json_text(capture.get(part))
            if text is not None:
                cases.append((path.name + ":" + part, text))
    return cases


ROUND_TRIP_CASES = _round_trip_cases()


def _ordered(text):
    """Parse so that member order is part of the comparison: each object becomes a list of pairs."""
    return json.loads(text, object_pairs_hook=lambda pairs: ("object", pairs))


def test_round_trip_inputs_are_present():
    # an empty parameter set would make the round-trip test skip itself instead of failing
    assert any(
        case_id.startswith("TestFiles/") for case_id, _ in ROUND_TRIP_CASES
    ), FIXTURES_DIR
    assert any(":" in case_id for case_id, _ in ROUND_TRIP_CASES), CAPTURES_DIR


@pytest.mark.parametrize(
    "text",
    [text for _, text in ROUND_TRIP_CASES],
    ids=[case_id for case_id, _ in ROUND_TRIP_CASES],
)
def test_encode_of_decode_reparses_to_the_same_structure(text):
    assert _ordered(codec.encode(codec.decode(text))) == _ordered(text)


# ----------------------------------------------------------------------------------------------
# Dates
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "/Date(1754179200000)/",
        "/Date(1754179200000+0000)/",
        "/Date(1623685004731+0200)/",
        "/Date(-86400000-0500)/",
        "/Date(-86400000)/",
        "/Date(0)/",
    ],
)
def test_date_text_is_written_back_unchanged(text):
    value = codec.decode(json.dumps(text))
    assert isinstance(value, datetime) and value.tzinfo is not None
    assert json.loads(codec.encode(value)) == text


def test_date_values():
    assert codec.decode('"/Date(1754179200000)/"') == datetime(
        2025, 8, 3, tzinfo=timezone.utc
    )

    offset = codec.decode('"/Date(1623685004731+0200)/"')
    assert offset.utcoffset() == timedelta(hours=2)
    assert offset == datetime(
        2021, 6, 14, 15, 36, 44, 731000, tzinfo=timezone.utc
    )  # the same instant

    assert codec.decode('"/Date(-86400000)/"') == datetime(
        1969, 12, 31, tzinfo=timezone.utc
    )


def test_a_naive_datetime_is_written_as_utc():
    assert codec.encode(datetime(2025, 8, 3)) == '"/Date(1754179200000)/"'


def test_dates_are_found_inside_nested_lists():
    value = codec.decode('{"Rows": [["/Date(0)/", "x"], [["/Date(1000)/"]]]}')
    assert value.Rows[0][0] == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert value.Rows[1][0][0] == datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize("text", ["/Date(abc)/", "Date(0)", "hello", "PT0S", "PT5M"])
def test_other_strings_are_left_alone(text):
    # an ISO duration is an ordinary string on the wire, so it stays a string
    assert codec.decode(json.dumps(text)) == text


def test_a_datetimeoffset_object_stays_a_contract_object():
    text = '{"__type":"DateTimeOffset:#System","DateTime":"/Date(1783707598856)/","OffsetMinutes":0}'
    value = codec.decode(text)
    assert type(value) is ContractObject
    assert isinstance(value.DateTime, datetime)
    assert _ordered(codec.encode(value)) == _ordered(text)


# ----------------------------------------------------------------------------------------------
# Objects, keyed lists, and the registry
# ----------------------------------------------------------------------------------------------


def test_contract_object_attributes():
    obj = ContractObject([("__type", "Thing:#X"), ("Name", "a"), ("Value", 5)])
    assert obj.Name == "a" and obj.type_name == "Thing:#X"
    assert ContractObject(Name="x").type_name is None

    obj.Value = 6
    obj.Added = 1
    assert list(obj) == [
        "__type",
        "Name",
        "Value",
        "Added",
    ]  # a new member goes at the end
    del obj.Added
    assert "Added" not in obj

    assert not hasattr(obj, "Missing")
    with pytest.raises(AttributeError):
        obj.Missing


def test_contract_object_copies_and_pickles():
    obj = ContractObject([("__type", "Thing:#X"), ("Name", "a")])
    for copied in (copy.deepcopy(obj), pickle.loads(pickle.dumps(obj))):
        assert type(copied) is ContractObject and copied == obj and copied is not obj


def test_module_inputs_and_outputs_become_keyed_lists():
    value = codec.decode(
        '{"ModuleInputs": [{"Name": "A", "ValueObj": 1}, {"Name": "B", "ValueObj": 2}],'
        ' "ModuleOutputs": [{"Name": "Result"}], "Other": [{"Name": "A"}]}'
    )
    assert (
        type(value.ModuleInputs) is KeyedList and type(value.ModuleOutputs) is KeyedList
    )
    assert (
        type(value.Other) is NetList
    )  # only the two named members are keyed, and every array is a NetList

    assert value.ModuleInputs.Indexes.Keys == ["A", "B"]
    assert value.ModuleInputs["B"].ValueObj == 2
    assert value.ModuleInputs[0].Name == "A" and value.ModuleInputs[-1].Name == "B"
    assert [item.Name for item in value.ModuleInputs] == ["A", "B"]
    with pytest.raises(KeyError):
        value.ModuleInputs["Missing"]

    value.ModuleInputs.Add(ContractObject(Name="C"))
    assert value.ModuleInputs.Indexes.Keys == ["A", "B", "C"]
    assert json.loads(codec.encode(value))["ModuleInputs"][2] == {"Name": "C"}


def test_registered_classes_are_used_and_unknown_types_fall_back(monkeypatch):
    monkeypatch.setattr(
        objects, "_registry", dict(objects._registry)
    )  # leave the real registry alone

    class Thing(ContractObject):
        pass

    objects.register("Thing:#Test", Thing)
    value = codec.decode('{"__type": "Thing:#Test", "A": 1}')
    assert type(value) is Thing and value.A == 1
    assert type(codec.decode('{"__type": "Other:#Test", "A": 1}')) is ContractObject
    assert type(codec.decode('{"A": 1}')) is ContractObject  # no __type at all


# ----------------------------------------------------------------------------------------------
# Replies and faults, from the captured responses
# ----------------------------------------------------------------------------------------------


def _captured_response(name):
    capture = json.loads((CAPTURES_DIR / (name + ".json")).read_text(encoding="utf-8"))
    return codec.decode(json.dumps(capture["ResponseBody"]))


def test_unwrap():
    assert (
        codec.unwrap(codec.decode('{"d": null}')) is None
    )  # an id that does not exist is not an error
    assert codec.unwrap(codec.decode('{"d": 6}')) == 6

    application = codec.unwrap(
        _captured_response("ApplicationService.GetApplication.SuccessfulCall")
    )
    assert application.type_name == "Application:#CompAnalytics.Contracts"
    assert isinstance(application.Modules[0].ModuleInputs, KeyedList)


@pytest.mark.parametrize(
    "capture, message, has_exception_detail",
    [
        ("ApplicationService.GetApplication.NoToken", "Authentication failed.", False),
        (
            "ApplicationService.GetApplication.BadToken",
            "Not a valid JSON Web Token (JWT).",
            True,
        ),
        (
            "ApplicationService.GetApplication.UnauthorizedAccess",
            "User does not have Read permissions",
            True,
        ),
    ],
)
def test_parse_fault_reads_every_error_shape(capture, message, has_exception_detail):
    body = _captured_response(capture)
    assert (
        "ExceptionDetail" in body
    ) is has_exception_detail  # the three shapes differ; parse_fault must not care
    fault = codec.parse_fault(body)
    assert set(fault) == {"Message", "ExceptionType", "StackTrace"}
    assert message in fault["Message"]
    assert fault["ExceptionType"]


# ----------------------------------------------------------------------------------------------
# The operation manifest
# ----------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def operations():
    return json.loads(OPERATIONS_JSON.read_text(encoding="utf-8"))


def test_manifest_entries_are_well_formed(operations):
    assert operations
    for service, entries in operations.items():
        names = [entry["name"] for entry in entries]
        assert len(names) == len(set(names)), service
        for entry in entries:
            assert set(entry) == {
                "name",
                "params",
                "verb",
                "uri",
                "request",
                "response",
            }, entry
            assert entry["verb"] in {
                "GET",
                "POST",
                "HEAD",
                "DELETE",
                "PATCH",
                "PUT",
            }, entry
            assert entry["request"] in {"raw", "json"} and entry["response"] in {
                "raw",
                "json",
            }, entry
            if entry["request"] == "raw":
                assert (
                    len(entry["params"]) == 1
                ), entry  # raw means a single Stream parameter


@pytest.mark.parametrize(
    "service, operation, expected",
    [
        (
            "AclService",
            "GetAcl",
            dict(
                verb="GET",
                uri=None,
                request="json",
                response="json",
                params=["resourceId", "aclTypeStr", "securableResourceType"],
            ),
        ),
        (
            "ApplicationService",
            "GetApplication",
            dict(
                verb="POST", uri=None, request="json", response="json", params=["appId"]
            ),
        ),
        (
            "TableService",
            "CreateTable",
            dict(
                verb="POST",
                uri=None,
                request="raw",
                response="json",
                params=["jsonStream"],
            ),
        ),
        (
            "FileUploadService",
            "StreamRunFile",
            dict(
                verb="POST",
                uri=None,
                request="json",
                response="raw",
                params=["handle", "uri"],
            ),
        ),
        (
            "WebActivationService",
            "ProcessGet",
            dict(
                verb="GET", uri="/Activate", request="json", response="raw", params=[]
            ),
        ),
        (
            "WebActivationService",
            "ProcessPut",
            dict(
                verb="PUT",
                uri="/Activate",
                request="raw",
                response="raw",
                params=["message"],
            ),
        ),
    ],
)
def test_manifest_known_operations(operations, service, operation, expected):
    entry = next(e for e in operations[service] if e["name"] == operation)
    assert {key: entry[key] for key in expected} == expected


def _without_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


@needs_product
def test_every_service_contract_interface_is_in_the_manifest(operations):
    # written separately from the generator, so the two can disagree and one of them gets noticed
    service_contract = re.compile(
        r"\[ServiceContract\b[^\]]*\](?:\s*\[[^\]]*\])*\s*public\s+interface\s+(\w+)"
    )
    expected, operation_count = set(), 0
    for path in sorted(INTERFACES_DIR.glob("I*.cs")):
        text = _without_comments(path.read_text(encoding="utf-8-sig"))
        found = service_contract.findall(text)
        expected.update(
            name[1:] for name in found
        )  # the service name drops the leading I
        if found:
            operation_count += text.count("[OperationContract")
    assert set(operations) == expected
    assert sum(len(entries) for entries in operations.values()) == operation_count


@needs_product
def test_generator_reproduces_the_committed_manifest(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "generate_operations", ROOT_DIR / "tools" / "generate_operations.py"
    )
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)

    out = tmp_path / "operations.json"
    generator.generate_ops(interface_dir=INTERFACES_DIR, out=out)
    assert out.read_bytes() == OPERATIONS_JSON.read_bytes()


# ----------------------------------------------------------------------------------------------
# Numbers the .NET serializer writes that json does not know
# ----------------------------------------------------------------------------------------------


def test_an_infinite_double_written_the_dotnet_way_decodes():
    # DataContractJsonSerializer writes double.PositiveInfinity as INF and NegativeInfinity as -INF, and NaN as NaN
    decoded = codec.decode('{"a": INF, "b": -INF, "c": NaN, "d": [1.5, INF]}')
    assert decoded["a"] == float("inf") and decoded["b"] == float("-inf")
    assert decoded["c"] != decoded["c"]  # NaN
    assert list(decoded["d"]) == [1.5, float("inf")]


def test_the_word_inf_inside_a_string_stays_text():
    decoded = codec.decode(
        '{"a": "INF", "b": "say \\"INF\\" twice", "c": INF, "d": "-INF"}'
    )
    assert decoded["a"] == "INF" and decoded["b"] == 'say "INF" twice'
    assert decoded["c"] == float("inf") and decoded["d"] == "-INF"


def test_a_body_that_is_not_json_still_says_why_it_failed():
    with pytest.raises(json.JSONDecodeError):
        codec.decode('{"a": 1,')
    with pytest.raises(json.JSONDecodeError):
        codec.decode("<html>Bad gateway</html>")


@pytest.mark.parametrize(
    "value, text",
    [
        (float("nan"), "NaN"),
        (float("inf"), "Infinity"),
        (float("-inf"), "-Infinity"),
    ],
)
def test_a_non_finite_double_is_written_as_the_literal_the_platform_reads(value, text):
    # Not strict JSON, but DataContractJsonSerializer, which reads every request, reads these literals as the double
    assert codec.encode({"x": value}) == '{"x": ' + text + "}"


def test_the_extreme_dates_a_dotnet_offset_can_have_decode():
    # An offset is never added to MinValue or taken off MaxValue: .NET cannot make a DateTimeOffset out of range
    assert codec.decode('"/Date(-62135596800000+0100)/"') == datetime(
        1, 1, 1, 1, 0, tzinfo=timezone(timedelta(hours=1))
    )
    assert codec.decode('"/Date(253402300799999-0500)/"') == datetime(
        9999, 12, 31, 18, 59, 59, 999000, tzinfo=timezone(timedelta(hours=-5))
    )
    assert codec.decode('"/Date(-62135596800000)/"') == datetime(
        1, 1, 1, tzinfo=timezone.utc
    )
    assert codec.decode('"/Date(253402300799999)/"') == datetime(
        9999, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc
    )


# ----------------------------------------------------------------------------------------------
# encode: the compact form, a value it cannot write, and the milliseconds a date keeps
# ----------------------------------------------------------------------------------------------


def test_compact_encoding_writes_no_space_after_a_colon_or_a_comma():
    value = codec.decode('{"b": [1, 2, {"z": null, "y": "x, y: z"}], "a": true}')
    assert (
        codec.encode(value, compact=True)
        == '{"b":[1,2,{"z":null,"y":"x, y: z"}],"a":true}'
    )  # the member order is the order sent, and a comma or colon inside text is left alone
    assert (
        codec.encode(value) == '{"b": [1, 2, {"z": null, "y": "x, y: z"}], "a": true}'
    )


def test_compact_encoding_of_empty_containers_dates_and_scalars():
    assert codec.encode({"a": [], "b": {}}, compact=True) == '{"a":[],"b":{}}'
    assert (
        codec.encode({"d": datetime(2025, 8, 3)}, compact=True)
        == '{"d":"/Date(1754179200000)/"}'
    )
    assert (
        codec.encode([1, "x", None, 2.5, False], compact=True)
        == '[1,"x",null,2.5,false]'
    )


def test_compact_encoding_of_every_fixture_has_the_same_structure_as_the_default():
    for case_id, text in ROUND_TRIP_CASES:
        value = codec.decode(text)
        assert _ordered(codec.encode(value, compact=True)) == _ordered(
            codec.encode(value)
        ), case_id


@pytest.mark.parametrize(
    "value, type_name",
    [
        ({1, 2}, "set"),
        (b"x", "bytes"),
        (object(), "object"),
        (Decimal("1.5"), "Decimal"),
        (date(2025, 8, 3), "date"),
    ],
)
def test_encoding_a_type_it_cannot_write_raises_type_error_naming_the_type(
    value, type_name
):
    for compact in (False, True):
        with pytest.raises(TypeError, match="Cannot encode " + type_name + "$"):
            codec.encode({"outer": [value]}, compact=compact)


def test_a_tuple_is_written_as_a_json_array():
    assert codec.encode({"a": (1, 2)}) == '{"a": [1, 2]}'


def test_a_datetime_with_microseconds_is_written_with_the_milliseconds_only():
    # the .NET date format has no finer unit; the rest is dropped, not rounded
    utc = timezone.utc
    assert (
        codec.encode(datetime(2025, 8, 3, 0, 0, 0, 999999, tzinfo=utc))
        == '"/Date(1754179200999)/"'
    )
    assert (
        codec.encode(datetime(2025, 8, 3, 0, 0, 0, 1999, tzinfo=utc))
        == '"/Date(1754179200001)/"'
    )
    assert codec.encode(datetime(2025, 8, 3, 0, 0, 0, 500)) == '"/Date(1754179200000)/"'


def test_a_datetime_with_microseconds_before_1970_is_written_as_the_millisecond_before():
    # one microsecond before the epoch is not millisecond 0; the value is floored, so it stays before 1970
    assert codec.encode(datetime(1969, 12, 31, 23, 59, 59, 999999)) == '"/Date(-1)/"'
    assert codec.decode('"/Date(-1)/"') == datetime(
        1969, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc
    )


def test_a_datetime_with_microseconds_and_an_offset_keeps_the_offset_in_the_text():
    plus_two = timezone(timedelta(hours=2))
    assert (
        codec.encode(datetime(2025, 8, 3, 2, 0, 0, 123456, tzinfo=plus_two))
        == '"/Date(1754179200123+0200)/"'
    )
    half_hour = timezone(timedelta(hours=5, minutes=30))
    assert (
        codec.encode(datetime(2025, 1, 1, tzinfo=half_hour))
        == '"/Date(1735669800000+0530)/"'
    )


# ----------------------------------------------------------------------------------------------
# decode: a repeated member and a keyed member that is null
# ----------------------------------------------------------------------------------------------


def test_a_member_written_twice_keeps_the_last_value_in_the_first_position():
    value = codec.decode('{"a": 1, "b": 0, "a": 2}')
    assert list(value.items()) == [("a", 2), ("b", 0)]


def test_a_null_module_inputs_or_outputs_stays_null():
    value = codec.decode('{"ModuleInputs": null, "ModuleOutputs": null}')
    assert value.ModuleInputs is None and value.ModuleOutputs is None
    assert json.loads(codec.encode(value)) == {
        "ModuleInputs": None,
        "ModuleOutputs": None,
    }


def test_module_inputs_that_is_an_object_and_not_an_array_is_not_keyed():
    value = codec.decode('{"ModuleInputs": {"Name": "A"}}')
    assert type(value.ModuleInputs) is ContractObject


def test_an_empty_module_inputs_is_a_keyed_list_and_a_nested_one_is_keyed_too():
    value = codec.decode(
        '{"ModuleInputs": [], "Modules": [{"ModuleOutputs": [{"Name": "x"}]}]}'
    )
    assert type(value.ModuleInputs) is KeyedList and value.ModuleInputs.Count == 0
    assert type(value.Modules[0].ModuleOutputs) is KeyedList
    assert value.Modules[0].ModuleOutputs["x"].Name == "x"


# ----------------------------------------------------------------------------------------------
# Replies and faults: bodies that are not the usual shape
# ----------------------------------------------------------------------------------------------


def test_parse_fault_gives_none_for_every_member_a_body_does_not_have():
    assert codec.parse_fault({}) == {
        "Message": None,
        "ExceptionType": None,
        "StackTrace": None,
    }
    assert codec.parse_fault({"Message": "m"}) == {
        "Message": "m",
        "ExceptionType": None,
        "StackTrace": None,
    }


def test_parse_fault_ignores_other_members_and_reads_a_decoded_object():
    body = codec.decode(
        '{"__type": "X:#Y", "Message": "m", "ExceptionType": "T", "StackTrace": "s", "Other": 1}'
    )
    assert codec.parse_fault(body) == {
        "Message": "m",
        "ExceptionType": "T",
        "StackTrace": "s",
    }


@pytest.mark.parametrize("body", ["[1]", '"text"', "null", "5"])
def test_pinned_parse_fault_of_a_body_that_is_not_an_object_raises_attribute_error(
    body,
):
    # Needs a decision: an error response whose JSON is not an object raises this from the transport's fault handling
    with pytest.raises(AttributeError):
        codec.parse_fault(codec.decode(body))


def test_pinned_unwrap_of_a_body_without_d_raises_key_error():
    # Needs a decision: a 2xx reply that is JSON but has no "d" reaches the caller as a bare KeyError
    with pytest.raises(KeyError, match="d"):
        codec.unwrap(codec.decode('{"x": 1}'))


@pytest.mark.parametrize("body", ["[1]", "5", "null", '"d"'])
def test_pinned_unwrap_of_a_body_that_is_not_an_object_raises_type_error(body):
    with pytest.raises(TypeError):
        codec.unwrap(codec.decode(body))


def test_unwrap_returns_whatever_d_holds_as_decoded():
    value = codec.unwrap(codec.decode('{"d": [1, "/Date(0)/", {"a": null}]}'))
    assert type(value) is NetList
    assert value[1] == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert value[2]["a"] is None
