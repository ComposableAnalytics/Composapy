"""Offline tests for composapy._wire.objects.NetList: the members of .NET's List<T> on a contract's collections.

The expected values are what the baseline wheel's List<string> and KeyedCollection returned under pythonnet, recorded by
tools/parity/corpus/net_list_members.py on 2026-10-27.
"""

import json
import pickle
import sys

import pytest

from composapy._wire import codec
from composapy._wire.objects import ContractObject, KeyedList, NetList
from composapy.contracts import Table


def names():
    return NetList(["a", "b"])


# ----------------------------------------------------------------------------------------------
# What the baseline's List<string> did
# ----------------------------------------------------------------------------------------------


def test_count_is_the_length_as_an_int():
    assert (
        names().Count == 2
        and type(names().Count) is int
        and len(names()) == 2
        and NetList().Count == 0
    )


def test_contains_and_index_of_and_last_index_of():
    h = NetList(["a", "b", "a"])
    assert (h.Contains("a"), h.Contains("zz")) == (True, False)
    assert (h.IndexOf("b"), h.IndexOf("zz")) == (1, -1)
    assert (h.IndexOf("a"), h.LastIndexOf("a"), h.LastIndexOf("zz")) == (0, 2, -1)


def test_to_array_and_get_range_return_the_items():
    h = NetList(["a", "b", "c"])
    assert (
        list(h.ToArray()) == ["a", "b", "c"]
        and list(h.GetRange(0, 1)) == ["a"]
        and list(h.GetRange(1, 2)) == ["b", "c"]
    )
    assert h.GetRange(3, 0) == []


@pytest.mark.parametrize("index, count", [(-1, 1), (0, -1), (2, 5), (3, 1)])
def test_get_range_outside_the_list_raises(index, count):
    with pytest.raises(IndexError):
        NetList(["a", "b"]).GetRange(index, count)


def test_add_add_range_insert_and_remove_follow_the_dotnet_results():
    h = names()
    assert h.Add("c") is None and h == ["a", "b", "c"]
    h.AddRange(
        ["d", "e"]
    )  # the baseline refused a Python list here; any iterable works
    assert h == ["a", "b", "c", "d", "e"]
    h.Insert(0, "z")
    assert h[0] == "z"
    assert h.Remove("z") is True and h.Remove("zz") is False
    assert h == ["a", "b", "c", "d", "e"]


def test_insert_may_append_at_the_end_but_not_past_it():
    h = names()
    h.Insert(2, "c")
    assert h == ["a", "b", "c"]
    for bad in (4, 99, -1):
        with pytest.raises(IndexError):
            h.Insert(bad, "q")  # Python's insert would have appended or wrapped


def test_remove_at_removes_the_item_and_refuses_an_index_outside_the_list():
    h = NetList(["a", "b", "c"])
    assert h.RemoveAt(0) is None and h == ["b", "c"]
    for bad in (2, 99, -1):
        with pytest.raises(IndexError):
            h.RemoveAt(bad)  # RemoveAt(-1) must not remove the last item
    assert h == ["b", "c"]


def test_reverse_sort_and_clear_work_in_place_and_return_nothing():
    h = NetList(["c", "A", "b"])
    assert h.Reverse() is None and h == ["b", "A", "c"]
    assert h.Sort() is None and h == ["A", "b", "c"]
    assert h.Clear() is None and h == [] and h.Count == 0


def test_the_members_the_baseline_sequence_wrapper_had_still_work():
    h = names()
    assert (
        "a" in h
        and list(h) == ["a", "b"]
        and h[0] == "a"
        and h.index("b") == 1
        and h.count("a") == 1
    )
    assert (
        sorted(h) == ["a", "b"]
        and ", ".join(h) == "a, b"
        and bool(h)
        and not bool(NetList())
    )
    h.append("c")
    assert h.Count == 3


# ----------------------------------------------------------------------------------------------
# It is a list in every other way
# ----------------------------------------------------------------------------------------------


def test_it_is_a_list_that_equals_lists_and_has_the_size_of_one():
    h = names()
    assert isinstance(h, list) and h == ["a", "b"] and ["a", "b"] == h and h != ["a"]
    assert sys.getsizeof(NetList()) == sys.getsizeof([]) and not hasattr(h, "__dict__")


def test_it_serializes_and_pickles_as_a_list():
    h = names()
    assert json.dumps(h) == '["a", "b"]' and codec.encode(h) == '["a", "b"]'
    loaded = pickle.loads(pickle.dumps(h))
    assert type(loaded) is NetList and loaded == h


def test_python_indexing_is_kept_where_dotnet_refused():
    h = names()
    assert h[-1] == "b" and h[0:1] == [
        "a"
    ]  # a negative index and a slice raised in the baseline


# ----------------------------------------------------------------------------------------------
# The codec makes every decoded array one
# ----------------------------------------------------------------------------------------------


def test_every_decoded_array_is_a_net_list_at_every_depth():
    value = codec.decode('{"A": [1, 2], "B": {"C": ["x"]}, "D": [[1, 2], [3]]}')
    assert type(value.A) is NetList and type(value.B.C) is NetList
    assert type(value.D) is NetList and all(type(row) is NetList for row in value.D)
    assert type(codec.decode("[1, 2]")) is NetList


def test_a_tables_headers_have_the_net_members():
    table = codec.decode(
        '{"__type":"Table:#CompAnalytics.Contracts.Tables","Headers":["a","b"],"Columns":[]}'
    )
    assert (
        isinstance(table, Table)
        and table.Headers.Count == 2
        and table.Headers.IndexOf("b") == 1
        and table.Headers.Contains("a")
    )


def test_the_two_keyed_members_stay_keyed_lists_and_are_net_lists():
    value = codec.decode(
        '{"ModuleInputs": [{"Name": "A"}], "ModuleOutputs": [], "Other": []}'
    )
    assert (
        type(value.ModuleInputs) is KeyedList
        and isinstance(value.ModuleInputs, NetList)
        and type(value.Other) is NetList
    )


def test_a_decoded_value_encodes_to_the_text_it_came_from():
    text = '{"A":[1,2.5,"x",null,true],"B":{"C":[[1],[2,3]]}}'
    assert json.loads(codec.encode(codec.decode(text))) == json.loads(text)


# ----------------------------------------------------------------------------------------------
# KeyedList: a KeyedCollection, asked by key
# ----------------------------------------------------------------------------------------------


def columns():
    return KeyedList(
        [
            ContractObject([("Name", "a"), ("Type", "VARCHAR")]),
            ContractObject([("Name", "b"), ("Type", "INTEGER")]),
        ]
    )


def test_a_keyed_list_has_count_and_is_indexed_by_name_and_position():
    c = columns()
    assert (
        c.Count == 2
        and c["b"].Type == "INTEGER"
        and c[0].Name == "a"
        and [x.Name for x in c] == ["a", "b"]
    )
    assert c.Indexes.Keys == ["a", "b"]


def test_a_keyed_list_is_asked_by_key():
    c = columns()
    assert c.Contains("a") is True and c.Contains("zz") is False
    assert (
        c.Contains(c[0]) is True
        and c.Contains(ContractObject([("Name", "q")])) is False
    )


def test_a_missing_key_raises_key_error_where_dotnet_raised_key_not_found_exception():
    with pytest.raises(KeyError):
        columns()["zz"]


def test_a_keyed_list_still_adds_and_is_a_net_list():
    c = columns()
    c.Add(ContractObject([("Name", "c"), ("Type", "BIGINT")]))
    assert (
        c.Count == 3
        and c["c"].Type == "BIGINT"
        and isinstance(c, NetList)
        and c.IndexOf(c[2]) == 2
    )


# ----------------------------------------------------------------------------------------------
# The lists of a contract composapy builds, as against one the server sent
# ----------------------------------------------------------------------------------------------


def test_the_lists_of_a_query_view_a_driver_builds_have_the_net_list_members():
    from composapy.contracts import QueryView

    contract = QueryView()
    lists = {name: value for name, value in contract.items() if isinstance(value, list)}

    assert {"LiteralInputs", "SearchInputs", "ColumnDefinitions"} <= set(lists)
    for name, value in lists.items():
        assert type(value) is NetList, name
    contract.LiteralInputs.Add("x")
    assert contract.LiteralInputs.Count == 1
    contract.LiteralInputs.Clear()
    assert contract.LiteralInputs.Count == 0


def test_a_list_given_to_a_contract_factory_becomes_a_net_list():
    from composapy.contracts import QueryView

    given = ["a"]
    contract = QueryView(LiteralInputs=given)

    assert type(contract.LiteralInputs) is NetList and contract.LiteralInputs == ["a"]
    contract.LiteralInputs.Add("b")
    assert given == ["a"]


def test_two_contracts_do_not_share_their_lists():
    from composapy.contracts import QueryView

    first, second = QueryView(), QueryView()
    first.LiteralInputs.Add("x")
    assert second.LiteralInputs.Count == 0


# ----------------------------------------------------------------------------------------------
# Keys, duplicates, and items without a Name
# ----------------------------------------------------------------------------------------------


def named(*keys):
    return KeyedList(
        [ContractObject([("Name", key), ("Order", i)]) for i, key in enumerate(keys)]
    )


def test_indexes_keys_is_a_snapshot_and_not_a_view_of_the_list():
    c = named("a")
    keys = c.Indexes.Keys
    c.Add(ContractObject(Name="b"))
    assert keys == ["a"] and c.Indexes.Keys == [
        "a",
        "b",
    ]  # the earlier result did not grow
    c.RemoveAt(0)
    assert c.Indexes.Keys == ["b"]
    assert keys == ["a"]


def test_changing_the_keys_result_does_not_change_the_list():
    c = named("a", "b")
    keys = c.Indexes.Keys
    keys.append("zz")
    keys.remove("a")
    assert c.Indexes.Keys == ["a", "b"] and c.Count == 2
    assert c.Indexes.Keys is not c.Indexes.Keys  # a new list on every call


def test_pinned_a_duplicate_key_is_kept_and_a_lookup_by_key_finds_the_first():
    # Needs a decision: .NET's KeyedCollection throws ArgumentException when an item with a key already in it is added
    # (and so cannot hold two); here Add keeps both and the key finds the first.
    c = named("a", "a")
    assert c.Count == 2 and c.Indexes.Keys == ["a", "a"]
    assert c["a"].Order == 0 and c.Contains("a") is True
    c.Add(ContractObject([("Name", "a"), ("Order", 2)]))
    assert c.Count == 3 and c["a"].Order == 0


def test_pinned_a_lookup_by_key_is_case_sensitive():
    # unlike TableColumnCollection, which compares names ignoring case
    c = named("Abc")
    assert c["Abc"].Order == 0
    with pytest.raises(KeyError):
        c["abc"]
    assert c.Contains("abc") is False


def test_pinned_an_item_without_a_name_makes_key_members_raise_attribute_error():
    # Needs a decision: the server always sends a Name, so this only happens to a list built by hand. Every member that
    # reads every key raises AttributeError, not KeyError, for the nameless item; a key found before it is returned.
    c = KeyedList([ContractObject(Name="a"), ContractObject(Value=1)])
    assert c["a"].Name == "a" and c.Contains("a") is True
    with pytest.raises(AttributeError):
        c.Indexes.Keys
    with pytest.raises(AttributeError):
        c["zz"]
    with pytest.raises(AttributeError):
        c.Contains("zz")
    assert c.Contains(c[1]) is True  # asked by item, not by key
    assert c[1].Value == 1


def test_an_item_whose_name_is_null_is_listed_with_the_key_none():
    c = KeyedList([ContractObject(Name=None)])
    assert c.Indexes.Keys == [None]


def test_pinned_removing_or_finding_a_keyed_item_by_its_key_does_nothing():
    # Needs a decision: Contains accepts a key, but Remove and IndexOf take only an item, so a key is never found.
    c = named("a", "b")
    assert c.Remove("b") is False and c.IndexOf("b") == -1
    assert c.Indexes.Keys == ["a", "b"]
    assert c.Remove(c[1]) is True and c.Indexes.Keys == ["a"]


# ----------------------------------------------------------------------------------------------
# GetRange, slices, and Sort
# ----------------------------------------------------------------------------------------------


def test_get_range_returns_a_new_net_list_that_can_be_changed_on_its_own():
    h = NetList(["a", "b", "c"])
    part = h.GetRange(0, 2)
    assert type(part) is NetList and part == ["a", "b"] and part.Count == 2
    part.Add("q")
    part.Clear()
    assert h == ["a", "b", "c"]
    assert h.GetRange(0, 3) == h and h.GetRange(0, 3) is not h


def test_pinned_get_range_of_a_keyed_list_is_a_plain_net_list_that_is_not_keyed():
    # .NET's KeyedCollection has no GetRange; the list it returns here has lost the by-key members
    part = named("a", "b").GetRange(0, 1)
    assert type(part) is NetList
    assert part[0].Name == "a" and part.Contains("a") is False


def test_pinned_a_slice_is_a_plain_list_and_not_a_net_list():
    h = NetList(["a", "b", "c"])
    assert type(h[0:2]) is list and h[0:2] == ["a", "b"]
    assert type(named("a", "b")[0:1]) is list


def test_sort_orders_numbers_and_all_lower_case_text():
    numbers = NetList([3, 1, 2])
    numbers.Sort()
    assert numbers == [1, 2, 3]
    words = NetList(["pear", "apple", "fig"])
    words.Sort()
    assert words == ["apple", "fig", "pear"]


def test_pinned_sort_orders_text_by_code_point_not_by_the_cultures_order():
    # Deliberately not changed: List<string>.Sort on .NET Framework 4.8 gives a, b, B for these, but the culture that
    # decides that order is the machine's, so composapy keeps Python's order, which is the same everywhere.
    h = NetList(["b", "B", "a"])
    h.Sort()
    assert h == ["B", "a", "b"]


def test_pinned_sort_of_items_that_cannot_be_compared_raises_type_error():
    # .NET raises InvalidOperationException for a type that is not IComparable
    with pytest.raises(TypeError):
        NetList([ContractObject(a=1), ContractObject(a=0)]).Sort()
    with pytest.raises(TypeError):
        NetList([1, "a"]).Sort()
