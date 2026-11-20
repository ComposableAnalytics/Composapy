"""Offline tests for the typed ExecutionHandle contract (composapy.contracts).

They need no .NET and no server. The expected JSON and the old pickles come from tests/baseline/pickles,
which were written by the 0.13.3 wheel DataLabs ran before this project.
"""

import copy
import json
import pickle
from pathlib import Path

import pytest

from composapy._wire import codec
from composapy._wire.objects import ContractObject
from composapy.contracts import ExecutionHandle, ExecutionHandlePickleBehavior

TESTS_DIR = Path(__file__).resolve().parent.parent
BASELINE_DIR = TESTS_DIR / "baseline" / "pickles"
CAPTURES_DIR = TESTS_DIR / "wire_captures"

EXPECTED = json.loads((BASELINE_DIR / "manifest.json").read_text(encoding="utf-8"))[
    "execution_handle.pkl"
]["json"]
TYPE = "ExecutionHandle:#CompAnalytics.Contracts"


def _handle():
    return codec.decode(json.dumps(EXPECTED))


def test_decoding_the_wire_json_gives_an_execution_handle():
    handle = _handle()
    assert type(handle) is ExecutionHandle
    assert handle.type_name == TYPE
    assert (
        handle.HandleId == EXPECTED["HandleId"]
        and handle.Id == EXPECTED["Id"]
        and handle.AppId is None
    )


def test_a_decoded_handle_inside_another_object_is_also_an_execution_handle():
    outer = codec.decode(
        json.dumps({"RootExecutionHandle": EXPECTED, "Other": [EXPECTED]})
    )
    assert type(outer.RootExecutionHandle) is ExecutionHandle
    assert type(outer.Other[0]) is ExecutionHandle


def test_json_matches_what_the_dotnet_serializer_wrote():
    out = json.loads(codec.encode(_handle()))
    assert out == EXPECTED
    assert list(out) == list(
        EXPECTED
    )  # the same members in the same order: __type, AppId, HandleId, Id


def test_json_dumps_works_on_a_handle():
    assert json.loads(json.dumps(_handle())) == EXPECTED


def test_a_handle_built_by_hand_has_the_serializer_member_order():
    handle = ExecutionHandle(HandleId="be733cc6-df15-4cd6-8f37-73d1c8def3f7", Id=685692)
    assert list(handle) == ["__type", "AppId", "HandleId", "Id"]
    assert handle.type_name == TYPE and handle.AppId is None
    assert json.loads(codec.encode(handle)) == EXPECTED


def test_members_can_be_read_and_changed_as_attributes():
    handle = _handle()
    handle.Id = 7
    handle.AppId = 3
    assert (handle.Id, handle.AppId) == (7, 3)
    assert json.loads(codec.encode(handle))["Id"] == 7


def test_equality_and_hashing_follow_the_handle_id():
    a = ExecutionHandle(HandleId="11111111-1111-1111-1111-111111111111", Id=1)
    same_handle_other_run = ExecutionHandle(
        HandleId="11111111-1111-1111-1111-111111111111", Id=2
    )
    other = ExecutionHandle(HandleId="22222222-2222-2222-2222-222222222222", Id=1)
    assert a == same_handle_other_run and hash(a) == hash(same_handle_other_run)
    assert a != other
    assert len({a, same_handle_other_run, other}) == 2


def test_deepcopy_returns_the_same_object():
    handle = _handle()
    assert copy.deepcopy(handle) is handle


def test_a_new_pickle_round_trips():
    handle = _handle()
    loaded = pickle.loads(pickle.dumps(handle))
    assert type(loaded) is ExecutionHandle and loaded == handle
    assert json.loads(codec.encode(loaded)) == EXPECTED


def test_the_pickle_behavior_class_can_be_assigned_and_pickled():
    handle = _handle()
    handle.__class__ = ExecutionHandlePickleBehavior  # what the DataLab wrappers do to the objects they receive
    loaded = pickle.loads(pickle.dumps(handle))
    assert loaded == handle and isinstance(loaded, ExecutionHandle)
    assert json.loads(codec.encode(loaded)) == EXPECTED


def test_a_pickle_written_by_the_baseline_behavior_class_loads():
    # execution_handle_behavior.pkl records composapy.patch.execution_handle.ExecutionHandlePickleBehavior;
    # 0.13.3 could not load it back (Appendix A.8)
    loaded = pickle.loads((BASELINE_DIR / "execution_handle_behavior.pkl").read_bytes())
    assert isinstance(loaded, ExecutionHandle)
    assert json.loads(codec.encode(loaded)) == EXPECTED


def test_a_pickle_written_by_the_baseline_plain_class_loads():
    loaded = pickle.loads((BASELINE_DIR / "execution_handle.pkl").read_bytes())
    assert isinstance(loaded, ExecutionHandle)
    assert json.loads(codec.encode(loaded)) == EXPECTED


@pytest.mark.skipif(
    not CAPTURES_DIR.is_dir(), reason="tests/wire_captures is not present"
)
def test_the_handle_inside_a_captured_table_decodes_as_an_execution_handle():
    capture = json.loads(
        (CAPTURES_DIR / "TableService.CreateTable.OctetStream.json").read_text(
            encoding="utf-8"
        )
    )
    table = codec.unwrap(codec.decode(json.dumps(capture["ResponseBody"])))
    assert type(table.RootExecutionHandle) is ExecutionHandle
    assert (
        table.RootExecutionHandle.HandleId
        == capture["ResponseBody"]["d"]["RootExecutionHandle"]["HandleId"]
    )


NO_HANDLE_ID = '{"__type": "ExecutionHandle:#CompAnalytics.Contracts", "Id": 1}'
WITH_EXTRA = (
    '{"__type": "ExecutionHandle:#CompAnalytics.Contracts", "AppId": 1, "HandleId": "a", "Id": 2,'
    ' "Extra": "x"}'
)


# ----------------------------------------------------------------------------------------------
# A handle built by hand, and a member the contract does not list
# ----------------------------------------------------------------------------------------------


def test_a_handle_built_with_no_members_has_every_member_null():
    handle = ExecutionHandle()
    assert dict(handle) == {
        "__type": TYPE,
        "AppId": None,
        "HandleId": None,
        "Id": None,
    }
    assert list(handle) == ["__type", "AppId", "HandleId", "Id"]


def test_pinned_an_extra_member_given_as_a_keyword_is_dropped_without_a_message():
    # Needs a decision: a hand-built handle is rebuilt from the four members the serializer writes, so a fifth is lost
    handle = ExecutionHandle(HandleId="a", Id=1, Extra=5)
    assert "Extra" not in handle and list(handle) == [
        "__type",
        "AppId",
        "HandleId",
        "Id",
    ]
    with pytest.raises(AttributeError):
        handle.Extra


def test_pinned_an_extra_member_given_as_a_dict_without_a_type_is_dropped_too():
    handle = ExecutionHandle({"HandleId": "a", "Id": 3, "Extra": 1})
    assert dict(handle) == {"__type": TYPE, "AppId": None, "HandleId": "a", "Id": 3}


def test_an_extra_member_in_decoded_json_is_kept_and_written_back():
    # the server's JSON is not rebuilt (it has a __type), so a member added to the contract later is not lost
    handle = codec.decode(WITH_EXTRA)
    assert type(handle) is ExecutionHandle and handle.Extra == "x"
    assert list(json.loads(codec.encode(handle))) == [
        "__type",
        "AppId",
        "HandleId",
        "Id",
        "Extra",
    ]
    assert pickle.loads(pickle.dumps(handle)).Extra == "x"


def test_a_handle_given_pairs_with_a_type_is_taken_as_it_is():
    handle = ExecutionHandle([("__type", TYPE), ("HandleId", "a")])
    assert dict(handle) == {"__type": TYPE, "HandleId": "a"}  # nothing is filled in


def test_a_handle_given_its_json_text_is_decoded():
    text = json.dumps({"__type": TYPE, "AppId": None, "HandleId": "z", "Id": 3})
    handle = ExecutionHandle(text)
    assert handle.HandleId == "z" and handle.Id == 3 and handle.AppId is None


def test_a_handle_given_text_that_is_not_json_raises_a_value_error():
    # the environment variable a notebook run sets is the handle's JSON; a bare id is not that
    with pytest.raises(ValueError):
        ExecutionHandle("be733cc6-df15-4cd6-8f37-73d1c8def3f7")


# ----------------------------------------------------------------------------------------------
# Equality and hashing
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "other",
    [
        {"HandleId": "a"},
        {"__type": TYPE, "AppId": None, "HandleId": "a", "Id": None},
        ContractObject(HandleId="a"),
        "a",
        None,
        5,
    ],
    ids=["dict", "dict with all members", "ContractObject", "str", "None", "int"],
)
def test_a_handle_is_never_equal_to_an_object_that_is_not_a_handle(other):
    handle = ExecutionHandle(HandleId="a")
    assert (handle == other) is False and (other == handle) is False


def test_a_handle_equals_a_subclass_with_the_same_id_and_itself():
    handle = ExecutionHandle(HandleId="a")
    assert handle == handle
    behavior = ExecutionHandlePickleBehavior(HandleId="a")
    assert handle == behavior and behavior == handle and hash(handle) == hash(behavior)
    assert handle in {behavior}


def test_pinned_two_hand_built_handles_with_no_handle_id_are_equal_whatever_their_ids():
    # Needs a decision: both HandleIds are None, and equality looks at nothing else
    one, two = ExecutionHandle(Id=1), ExecutionHandle(Id=2)
    assert one == two and hash(one) == hash(two)
    assert one != ExecutionHandle(HandleId="a", Id=1)


def test_the_handle_id_is_compared_exactly():
    assert ExecutionHandle(HandleId="a") != ExecutionHandle(HandleId="A")
    assert ExecutionHandle(HandleId="a") != ExecutionHandle(HandleId=" a")


def test_a_decoded_handle_with_no_handle_id_member_can_be_compared():
    handle = codec.decode(NO_HANDLE_ID)
    assert (handle == handle) is True
    assert (handle == ExecutionHandle(HandleId="a")) is False


def test_a_decoded_handle_with_no_handle_id_member_can_be_hashed():
    assert isinstance(hash(codec.decode(NO_HANDLE_ID)), int)


def test_not_equal_is_the_opposite_of_equal():
    one = ExecutionHandle(HandleId="x", Id=1)
    other_run = ExecutionHandle(HandleId="x", Id=2)
    assert one == other_run and (one != other_run) is False
    same_members = {
        "__type": TYPE,
        "AppId": None,
        "HandleId": "x",
        "Id": 1,
    }
    assert (one == same_members) is False and (one != same_members) is True
