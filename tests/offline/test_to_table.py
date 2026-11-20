"""Offline tests for to_table and the pieces it uses: the column-type map, the column-name sanitizer, and the
TableColumn and TableColumnCollection contracts. A fake TableService records the body that to_table sends.
"""

import json

import numpy as np
import pandas as pd
import pytest

from composapy._wire import codec
from composapy.auth import AuthMode
from composapy.contracts.table import (
    COLUMN_TYPE,
    ColumnNameSanitizer,
    Table,
    TableColumn,
    TableColumnCollection,
    _column_type,
    sanitize_all,
    to_table,
)
from composapy.session import Session

URI = "http://example.test/CompApp/"
HANDLE = {
    "__type": "ExecutionHandle:#CompAnalytics.Contracts",
    "AppId": None,
    "HandleId": "be733cc6-df15-4cd6-8f37-73d1c8def3f7",
    "Id": 685692,
}


class FakeTableService:
    """Records the raw body CreateTable receives and answers with a table, as the real service does."""

    def __init__(self):
        self.bodies = []

    def CreateTable(self, body):
        self.bodies.append(body)
        return codec.decode(
            json.dumps(
                {
                    "__type": "Table:#CompAnalytics.Contracts.Tables",
                    "Columns": [],
                    "Headers": [],
                    "RootExecutionHandle": HANDLE,
                    "SqlQuery": "SELECT * FROM [t]",
                    "TableName": "t",
                }
            )
        )


@pytest.fixture
def service():
    session = Session(uri=URI, auth_mode=AuthMode.TOKEN, credentials="token-for-tests")
    session.register()
    fake = FakeTableService()
    session.services["TableService"] = fake
    yield fake
    Session.clear_registration()


def sent(service):
    """The body to_table sent, parsed so that member order is kept: every object is a list of pairs."""
    assert len(service.bodies) == 1
    assert isinstance(service.bodies[0], str)
    return json.loads(service.bodies[0], object_pairs_hook=list)


def as_dicts(pairs):
    return {key: value for key, value in pairs}


# ----------------------------------------------------------------------------------------------
# The column-type map
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dtype, expected",
    [
        ("int8", "INT"),
        ("uint8", "INT"),
        ("int16", "INT"),
        ("uint16", "INT"),
        ("int32", "INTEGER"),
        ("uint32", "INTEGER"),
        ("int64", "BIGINT"),
        ("uint64", "UNSIGNED BIG INT"),
        ("float16", "FLOAT"),
        ("float32", "FLOAT"),
        ("float64", "DOUBLE"),
        ("bool", "BOOLEAN"),
        ("object", "VARCHAR"),
        ("datetime64[ns]", "DATETIMEOFFSET"),
        ("timedelta64[ns]", "DURATION"),
        # the nullable dtypes report the same scalar types
        ("Int8", "INT"),
        ("UInt8", "INT"),
        ("Int16", "INT"),
        ("UInt16", "INT"),
        ("Int32", "INTEGER"),
        ("UInt32", "INTEGER"),
        ("Int64", "BIGINT"),
        ("UInt64", "UNSIGNED BIG INT"),
        ("Float32", "FLOAT"),
        ("Float64", "DOUBLE"),
        ("boolean", "BOOLEAN"),
        ("string", "VARCHAR"),
    ],
)
def test_every_supported_dtype_maps_to_its_column_type(dtype, expected):
    assert _column_type(pd.Series([], dtype=dtype).dtype) == expected


@pytest.mark.parametrize("dtype", ["datetime64[ns, UTC]", "category"])
def test_an_unsupported_dtype_raises_the_same_error_as_before(dtype):
    with pytest.raises(
        NotImplementedError, match="are not supported yet in the table conversion"
    ):
        _column_type(pd.Series([], dtype=dtype).dtype)


# ----------------------------------------------------------------------------------------------
# The column-name sanitizer
# ----------------------------------------------------------------------------------------------


def sanitize_in_order(names):
    sanitizer = ColumnNameSanitizer()
    return [sanitizer.sanitize_name(i, name) for i, name in enumerate(names)]


@pytest.mark.parametrize(
    "names, expected",
    [
        (["a", "A", "a"], ["a", "A_2", "a_3"]),  # duplicates are found ignoring case
        (
            ["a", "a", "a_2"],
            ["a", "a_2", "a_2_2"],
        ),  # a later real column can't collide with a made-up name
        (["a", "b", "a_2", "a"], ["a", "b", "a_2", "a_3"]),
        (
            ["a b", "a   b", "  a b "],
            ["a b", "a b_2", "a b_3"],
        ),  # whitespace runs collapse to one space, then trim
        (["", " ", "x"], ["col0", "col1", "x"]),  # a blank name becomes col<index>
        (["id", "ID", "Id"], ["id", "ID_2", "Id_3"]),
    ],
)
def test_sanitizer_matches_the_dotnet_rules(names, expected):
    assert sanitize_in_order(names) == expected


def test_sanitize_all_maps_each_original_name_to_its_clean_name():
    assert sanitize_all(["a  b", "c", "C"]) == {"a  b": "a b", "c": "c", "C": "C_2"}


def test_sanitizer_takes_a_custom_duplicate_format():
    sanitizer = ColumnNameSanitizer(
        duplicate_format="{0}-copy{1}", duplicate_start_index=1
    )
    assert [sanitizer.sanitize_name(i, n) for i, n in enumerate(["a", "a"])] == [
        "a",
        "a-copy1",
    ]


# ----------------------------------------------------------------------------------------------
# TableColumn and TableColumnCollection
# ----------------------------------------------------------------------------------------------


def test_a_column_built_by_hand_has_the_serializer_member_order():
    column = TableColumn("price", "DOUBLE")
    assert list(column) == ["__type", "Name", "Type"]
    assert (
        column.type_name == COLUMN_TYPE
        and column.Name == "price"
        and column.Type == "DOUBLE"
    )


def test_a_decoded_column_is_a_table_column():
    column = codec.decode(
        json.dumps({"__type": COLUMN_TYPE, "Name": "a", "Type": "INTEGER"})
    )
    assert type(column) is TableColumn and column.Name == "a"


def test_the_collection_looks_columns_up_by_position_or_by_name_ignoring_case():
    columns = TableColumnCollection(
        [TableColumn("Price", "DOUBLE"), TableColumn("id", "INTEGER")]
    )
    assert columns[0].Name == "Price" and columns[-1].Name == "id"
    assert columns["price"].Type == "DOUBLE" and columns["ID"].Type == "INTEGER"
    assert columns.Indexes.Keys == ["Price", "id"]
    with pytest.raises(KeyError):
        columns["missing"]
    columns.Add(TableColumn("z", "VARCHAR"))
    assert columns.Indexes.Keys == ["Price", "id", "z"]


def test_a_decoded_tables_columns_are_a_collection_that_can_be_looked_up_by_name():
    table = codec.decode(
        json.dumps(
            {
                "__type": "Table:#CompAnalytics.Contracts.Tables",
                "Columns": [{"__type": COLUMN_TYPE, "Name": "Total", "Type": "DOUBLE"}],
                "Headers": ["Total"],
                "RootExecutionHandle": HANDLE,
                "SqlQuery": "",
                "TableName": "t",
            }
        )
    )
    assert type(table.Columns) is TableColumnCollection
    assert table.Columns["TOTAL"].Type == "DOUBLE"


# ----------------------------------------------------------------------------------------------
# to_table
# ----------------------------------------------------------------------------------------------


def test_to_table_sends_the_handle_then_columns_then_rows(service):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    handle = codec.decode(json.dumps(HANDLE))
    result = to_table(df, handle)

    body = sent(service)
    assert [key for key, _ in body] == [
        "ExecutionHandle",
        "Columns",
        "Rows",
    ]  # the server stops reading at Rows
    members = as_dicts(body)
    assert as_dicts(members["ExecutionHandle"]) == HANDLE
    assert [as_dicts(column) for column in members["Columns"]] == [
        {"__type": COLUMN_TYPE, "Name": "a", "Type": "BIGINT"},
        {"__type": COLUMN_TYPE, "Name": "b", "Type": "VARCHAR"},
    ]
    assert members["Rows"] == [[1, "x"], [2, "y"]]
    assert type(result) is Table  # what CreateTable answers with


def test_to_table_writes_the_members_of_a_column_in_serializer_order(service):
    to_table(pd.DataFrame({"a": [1]}), codec.decode(json.dumps(HANDLE)))
    columns = as_dicts(sent(service))["Columns"]
    assert [key for key, _ in columns[0]] == ["__type", "Name", "Type"]


def test_to_table_puts_the_external_input_handles_before_the_rest(service):
    handles = {"ModuleHandle": "module1", "ModuleInputHandle": "input3"}
    to_table(
        pd.DataFrame({"a": [1]}),
        codec.decode(json.dumps(HANDLE)),
        external_input_handles=handles,
    )
    body = sent(service)
    assert [key for key, _ in body] == [
        "ModuleHandle",
        "ModuleInputHandle",
        "ExecutionHandle",
        "Columns",
        "Rows",
    ]
    assert as_dicts(body)["ModuleHandle"] == "module1"


def test_to_table_sanitizes_the_column_names(service):
    df = pd.DataFrame([[1, 2, 3]], columns=["a  b", "c", "C"])
    to_table(df, codec.decode(json.dumps(HANDLE)))
    names = [as_dicts(column)["Name"] for column in as_dicts(sent(service))["Columns"]]
    assert names == ["a b", "c", "C_2"]


def test_to_table_turns_a_non_default_index_into_a_column(service):
    df = pd.DataFrame({"a": [1, 2]}, index=[10, 20])
    to_table(df, codec.decode(json.dumps(HANDLE)))
    members = as_dicts(sent(service))
    assert [as_dicts(c)["Name"] for c in members["Columns"]] == ["index", "a"]
    assert members["Rows"] == [[10, 1], [20, 2]]


def test_to_table_flattens_multi_index_column_labels(service):
    df = pd.DataFrame(
        [[1, 2]], columns=pd.MultiIndex.from_tuples([("x", "a"), ("x", "b")])
    )
    to_table(df, codec.decode(json.dumps(HANDLE)))
    assert [as_dicts(c)["Name"] for c in as_dicts(sent(service))["Columns"]] == [
        "x_a",
        "x_b",
    ]


def test_to_table_writes_dates_as_iso_strings_with_a_datetimeoffset_column(service):
    df = pd.DataFrame({"d": pd.to_datetime(["2025-08-03"])})
    to_table(df, codec.decode(json.dumps(HANDLE)))
    members = as_dicts(sent(service))
    assert as_dicts(members["Columns"][0])["Type"] == "DATETIMEOFFSET"
    assert members["Rows"][0][0].startswith("2025-08-03T00:00:00")


def test_to_table_keeps_non_ascii_text(service):
    to_table(pd.DataFrame({"name": ["café 中"]}), codec.decode(json.dumps(HANDLE)))
    assert as_dicts(sent(service))["Rows"] == [["café 中"]]


def test_to_table_rejects_a_frame_with_no_columns(service):
    with pytest.raises(ValueError, match="at least one column"):
        to_table(pd.DataFrame(), codec.decode(json.dumps(HANDLE)))
    assert service.bodies == []  # refused before anything was sent


def test_to_table_rejects_duplicate_column_names(service):
    df = pd.DataFrame([[1, 2]], columns=["a", "a"])
    with pytest.raises(ValueError, match="duplicate column name"):
        to_table(df, codec.decode(json.dumps(HANDLE)))
    assert service.bodies == []


def test_to_table_rejects_an_unsupported_dtype(service):
    df = pd.DataFrame({"c": pd.Series(["a", "b"], dtype="category")})
    with pytest.raises(NotImplementedError, match="not supported yet"):
        to_table(df, codec.decode(json.dumps(HANDLE)))
    assert service.bodies == []


# ----------------------------------------------------------------------------------------------
# to_table: the index, the column labels, and the cells that are missing
# ----------------------------------------------------------------------------------------------


def send(service, df):
    """Runs to_table on df and returns the (column names, column types, rows) it sent."""
    to_table(df, codec.decode(json.dumps(HANDLE)))
    members = as_dicts(sent(service))
    columns = [as_dicts(column) for column in members["Columns"]]
    return [c["Name"] for c in columns], [c["Type"] for c in columns], members["Rows"]


def test_to_table_names_an_index_level_as_pandas_does_when_a_column_is_called_index(
    service,
):
    # reset_index finds "index" taken and calls the level "level_0"
    df = pd.DataFrame({"index": [1, 2], "a": [3, 4]}, index=[10, 20])
    names, _, rows = send(service, df)
    assert names == ["level_0", "index", "a"]
    assert rows == [[10, 1, 3], [20, 2, 4]]


def test_to_table_uses_the_name_of_a_named_index_for_its_column(service):
    df = pd.DataFrame({"a": [3, 4]}, index=pd.Index([10, 20], name="id"))
    names, types, rows = send(service, df)
    assert names == ["id", "a"] and types == ["BIGINT", "BIGINT"]
    assert rows == [[10, 3], [20, 4]]


def test_pinned_an_index_named_like_a_column_fails_with_the_pandas_error(service):
    # Needs a decision: nothing here checks for the clash, so the user sees pandas' own message from reset_index.
    df = pd.DataFrame({"a": [3, 4]}, index=pd.Index([10, 20], name="a"))
    with pytest.raises(ValueError, match="already exists"):
        to_table(df, codec.decode(json.dumps(HANDLE)))
    assert service.bodies == []


@pytest.mark.parametrize(
    "columns",
    [
        pd.MultiIndex.from_tuples([(1, 2), (1, 3)]),
        pd.MultiIndex.from_tuples([("x", 2), ("x", 3)]),
    ],
    ids=["all integers", "text and integers"],
)
def test_to_table_flattens_multi_index_column_labels_that_are_not_text(
    service, columns
):
    names, _, _ = send(service, pd.DataFrame([[1, 2]], columns=columns))
    assert names == [
        "_".join(str(part) for part in label) for label in columns
    ]  # 1_2 and 1_3, or x_2 and x_3


def test_to_table_with_integer_column_labels_sends_them_as_text(service):
    names, _, rows = send(service, pd.DataFrame([[1, 2]], columns=[1, 2]))
    assert names == ["1", "2"] and rows == [[1, 2]]


def test_pinned_a_multi_index_frame_with_a_row_index_names_the_index_column_with_a_trailing_underscore(
    service,
):
    # Needs a decision: reset_index gives the index column the label ("index", ""), and the join leaves "index_".
    df = pd.DataFrame(
        [[1, 2], [3, 4]],
        index=[5, 6],
        columns=pd.MultiIndex.from_tuples([("x", "a"), ("x", "b")]),
    )
    names, _, rows = send(service, df)
    assert names == ["index_", "x_a", "x_b"] and rows == [[5, 1, 2], [6, 3, 4]]


@pytest.mark.parametrize(
    "index, expected",
    [
        (pd.RangeIndex(5, 7), [5, 6]),
        (pd.RangeIndex(0, 4, 2), [0, 2]),
        (pd.RangeIndex(1, 3), [1, 2]),
    ],
    ids=["starts at 5", "steps by 2", "starts at 1"],
)
def test_to_table_turns_a_range_index_that_is_not_0_to_n_into_a_column(
    service, index, expected
):
    names, types, rows = send(service, pd.DataFrame({"a": [7, 8]}, index=index))
    assert names == ["index", "a"] and types == ["BIGINT", "BIGINT"]
    assert rows == [[value, other] for value, other in zip(expected, [7, 8])]


def test_to_table_keeps_the_old_row_numbers_of_a_filtered_frame_as_a_column(service):
    df = pd.DataFrame({"a": [1, 2, 3]})
    names, _, rows = send(service, df[df["a"] > 1])
    assert names == ["index", "a"] and rows == [[1, 2], [2, 3]]


def test_to_table_turns_a_string_index_into_a_text_column(service):
    names, types, rows = send(service, pd.DataFrame({"a": [1]}, index=["r1"]))
    assert names == ["index", "a"] and types == ["VARCHAR", "BIGINT"]
    assert rows == [["r1", 1]]


def test_to_table_turns_each_level_of_a_row_multi_index_into_a_column(service):
    index = pd.MultiIndex.from_tuples([(1, 2), (3, 4)])
    names, _, rows = send(service, pd.DataFrame({"a": [5, 6]}, index=index))
    assert names == ["level_0", "level_1", "a"]
    assert rows == [[1, 2, 5], [3, 4, 6]]


def test_to_table_sends_missing_cells_as_null(service):
    df = pd.DataFrame(
        {
            "f": [1.0, np.nan],
            "s": ["x", None],
            "i": pd.array([1, None], dtype="Int64"),
            "b": pd.array([True, None], dtype="boolean"),
            "t": pd.array(["x", None], dtype="string"),
            "d": pd.to_datetime(["2025-01-01", None]),
        }
    )
    names, types, rows = send(service, df)
    assert names == ["f", "s", "i", "b", "t", "d"]
    assert types == [
        "DOUBLE",
        "VARCHAR",
        "BIGINT",
        "BOOLEAN",
        "VARCHAR",
        "DATETIMEOFFSET",
    ]
    assert rows[1] == [None] * 6
    assert rows[0][:5] == [1.0, "x", 1, True, "x"]


def test_an_infinite_float_is_sent_as_an_infinity_and_nan_stays_null(service):
    # to_json writes null for an infinity, so to_table puts each one back; the codec writes it as Infinity or -Infinity
    df = pd.DataFrame(
        {
            "f": [float("inf"), 1.0, float("-inf"), np.nan],
            "g": np.array([1.5, float("inf"), 2.5, 3.5], dtype="float32"),
            "h": pd.array([float("-inf"), None, 1.0, 2.0], dtype="Float64"),
            "i": [1, 2, 3, 4],
        }
    )
    _, types, rows = send(service, df)
    assert types == ["DOUBLE", "FLOAT", "DOUBLE", "BIGINT"]
    assert rows == [
        [float("inf"), 1.5, float("-inf"), 1],
        [1.0, float("inf"), None, 2],
        [float("-inf"), 2.5, 1.0, 3],
        [None, 3.5, 2.0, 4],
    ]
    assert '"Infinity"' not in service.bodies[0]  # a number token, not a string
    assert "[Infinity" in service.bodies[0] and "-Infinity" in service.bodies[0]


def test_to_table_rejects_names_that_only_match_after_conversion_to_text(service):
    df = pd.DataFrame([[1, 2]], columns=[1, "1"])  # two labels, one name
    with pytest.raises(ValueError, match="duplicate column name.*'1'"):
        to_table(df, codec.decode(json.dumps(HANDLE)))
    assert service.bodies == []


def test_to_table_renames_names_that_differ_only_in_case_instead_of_refusing_them(
    service,
):
    names, _, _ = send(service, pd.DataFrame([[1, 2]], columns=["a", "A"]))
    assert names == ["a", "A_2"]


def test_to_table_gives_blank_column_names_a_numbered_name(service):
    names, _, _ = send(service, pd.DataFrame([[1, 2, 3]], columns=["", " ", "x"]))
    assert names == ["col0", "col1", "x"]


def test_to_table_sends_the_columns_of_a_frame_with_no_rows(service):
    df = pd.DataFrame(
        {"a": pd.Series([], dtype="int64"), "b": pd.Series([], dtype="object")}
    )
    names, types, rows = send(service, df)
    assert names == ["a", "b"] and types == ["BIGINT", "VARCHAR"] and rows == []


def test_to_table_sends_a_frame_built_only_from_column_names_as_text_columns(service):
    # no rows, so pandas gives every column the object dtype (reset_index: pandas 1.x gives such a frame an object index)
    names, types, rows = send(
        service, pd.DataFrame(columns=["a", "b"]).reset_index(drop=True)
    )
    assert names == ["a", "b"] and types == ["VARCHAR", "VARCHAR"] and rows == []


def test_to_table_rejects_a_frame_that_has_rows_but_no_columns(service):
    with pytest.raises(ValueError, match="at least one column"):
        to_table(pd.DataFrame(index=[1, 2]), codec.decode(json.dumps(HANDLE)))
    assert service.bodies == []
