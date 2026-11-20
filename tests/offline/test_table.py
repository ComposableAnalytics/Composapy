"""Offline tests for the typed Table contract (composapy.contracts) and its to_pandas and _repr_html_.

They need no .NET and no server: a fake TableService stands in for the real one. The expected dtypes and
values for the baseline table come from tests/baseline/pickles/manifest.json, written by the 0.13.3 wheel
that DataLabs ran before this project.
"""

import copy
import json
import pickle
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

import composapy.interactive.options as iopts
from composapy._wire import codec
from composapy.auth import AuthMode
from composapy.contracts import Table, TablePickleBehavior
from composapy.contracts.table import parse_datetime_string
from composapy.exceptions import ServiceFault
from composapy.session import Session

TESTS_DIR = Path(__file__).resolve().parent.parent
BASELINE_DIR = TESTS_DIR / "baseline" / "pickles"
MANIFEST = json.loads((BASELINE_DIR / "manifest.json").read_text(encoding="utf-8"))
BASELINE_TABLE = MANIFEST["table.pkl"]

URI = "http://example.test/CompApp/"
TYPE = "Table:#CompAnalytics.Contracts.Tables"


def table_json(columns):
    """The JSON the server sends for a table with the given (name, type) columns."""
    return json.dumps(
        {
            "__type": TYPE,
            "Columns": [
                {
                    "__type": "TableColumn:#CompAnalytics.Contracts.Tables",
                    "Name": name,
                    "Type": type_,
                }
                for name, type_ in columns
            ],
            "Headers": [name for name, _ in columns],
            "RootExecutionHandle": {
                "__type": "ExecutionHandle:#CompAnalytics.Contracts",
                "AppId": None,
                "HandleId": "be733cc6-df15-4cd6-8f37-73d1c8def3f7",
                "Id": 685692,
            },
            "SqlQuery": "SELECT * FROM [t]",
            "TableName": "t",
        }
    )


class FakeTableService:
    """Answers GetResultFromTable with canned headers and rows, decoded as the real reply would be."""

    def __init__(self, headers=None, rows=None, error=None):
        self.headers, self.rows, self.error, self.calls = headers, rows, error, []

    def GetResultFromTable(self, table, skip, take):
        self.calls.append((table, skip, take))
        if self.error is not None:
            raise self.error
        return codec.decode(json.dumps({"Headers": self.headers, "Results": self.rows}))


@pytest.fixture
def session():
    session = Session(uri=URI, auth_mode=AuthMode.TOKEN, credentials="token-for-tests")
    session.register()
    yield session
    Session.clear_registration()


@pytest.fixture
def show_interactive(monkeypatch):
    monkeypatch.setattr(iopts, "SHOW_INTERACTIVE_TABLES", True)


def to_pandas(session, columns, rows):
    session.services["TableService"] = FakeTableService(
        [name for name, _ in columns], rows
    )
    return codec.decode(table_json(columns)).to_pandas()


# ----------------------------------------------------------------------------------------------
# The contract
# ----------------------------------------------------------------------------------------------


def test_decoding_a_table_gives_a_table_with_its_members():
    table = codec.decode(table_json([("a", "VARCHAR"), ("b", "INTEGER")]))
    assert type(table) is Table and table.type_name == TYPE
    assert table.TableName == "t" and table.SqlQuery == "SELECT * FROM [t]"
    assert [c.Name for c in table.Columns] == ["a", "b"]
    assert table.RootExecutionHandle.Id == 685692


def test_encoding_a_table_gives_the_same_json_in_the_same_order():
    text = table_json([("a", "VARCHAR"), ("b", "INTEGER")])
    out = codec.encode(codec.decode(text))
    assert json.loads(out) == json.loads(text)
    assert list(json.loads(out)) == list(
        json.loads(text)
    )  # __type first, then the members as sent


def test_the_baseline_table_json_survives_a_round_trip():
    out = json.loads(codec.encode(codec.decode(json.dumps(BASELINE_TABLE["json"]))))
    assert out == BASELINE_TABLE["json"] and list(out) == list(BASELINE_TABLE["json"])


def test_deepcopy_returns_the_same_object():
    table = codec.decode(table_json([("a", "VARCHAR")]))
    assert copy.deepcopy(table) is table


def test_a_new_pickle_round_trips():
    table = codec.decode(table_json([("a", "VARCHAR")]))
    loaded = pickle.loads(pickle.dumps(table))
    assert type(loaded) is Table and loaded == table
    assert json.loads(codec.encode(loaded)) == json.loads(codec.encode(table))


def test_the_pickle_behavior_class_can_be_assigned_and_pickled():
    table = codec.decode(table_json([("a", "VARCHAR")]))
    table.__class__ = (
        TablePickleBehavior  # what the DataLab wrappers do to the objects they receive
    )
    loaded = pickle.loads(pickle.dumps(table))
    assert isinstance(loaded, Table) and loaded == table


def test_a_pickle_written_by_the_baseline_behavior_class_loads():
    # table_behavior.pkl records composapy.patch.table.TablePickleBehavior; 0.13.3 could not load it back
    loaded = pickle.loads((BASELINE_DIR / "table_behavior.pkl").read_bytes())
    assert isinstance(loaded, Table)
    assert json.loads(codec.encode(loaded)) == BASELINE_TABLE["json"]


def test_a_pickle_written_by_the_baseline_plain_class_loads():
    loaded = pickle.loads((BASELINE_DIR / "table.pkl").read_bytes())
    assert isinstance(loaded, Table)
    assert json.loads(codec.encode(loaded)) == BASELINE_TABLE["json"]


# ----------------------------------------------------------------------------------------------
# to_pandas
# ----------------------------------------------------------------------------------------------


def test_to_pandas_asks_for_the_whole_table(session):
    service = FakeTableService(["a"], [["x"]])
    session.services["TableService"] = service
    table = codec.decode(table_json([("a", "VARCHAR")]))
    table.to_pandas()
    assert [(skip, take) for _, skip, take in service.calls] == [(0, 0x7FFFFFFF)]
    assert service.calls[0][0] is table


def test_to_pandas_matches_the_baseline_dtypes_and_values(session):
    table_columns = [(c["Name"], c["Type"]) for c in BASELINE_TABLE["json"]["Columns"]]
    df = to_pandas(session, table_columns, BASELINE_TABLE["values"]["data"])
    assert {name: str(dtype) for name, dtype in df.dtypes.items()} == BASELINE_TABLE[
        "dtypes"
    ]
    assert (
        json.loads(df.to_json(orient="split", date_format="iso"))
        == BASELINE_TABLE["values"]
    )


COLUMNS = [
    ("i", "INTEGER"),
    ("f", "DOUBLE"),
    ("s", "VARCHAR"),
    ("b", "BOOLEAN"),
    ("d", "DATETIME"),
    ("o", "DATETIMEOFFSET"),
]


def test_to_pandas_dtypes_for_every_column_kind(session):
    rows = [[1, 1.5, "x", True, "/Date(1754179200000)/", "/Date(1754179200000+0200)/"]]
    df = to_pandas(session, COLUMNS, rows)
    assert {name: str(dtype) for name, dtype in df.dtypes.items()} == {
        "i": "Int64",
        "f": "float64",
        "s": "object",
        "b": "boolean",
        "d": "datetime64[ns]",
        "o": "datetime64[ns]",
    }
    assert df["d"][0] == pd.Timestamp("2025-08-03 00:00:00")
    assert df["o"][0] == pd.Timestamp(
        "2025-08-03 02:00:00"
    )  # the offset is added, as the old code did


def test_to_pandas_keeps_nulls_as_missing_values(session):
    df = to_pandas(session, COLUMNS, [[None] * 6])
    assert df["i"].isna()[0] and df["f"].isna()[0] and df["s"].isna()[0]
    assert df["b"].isna()[0] and df["d"].isna()[0] and df["o"].isna()[0]


@pytest.mark.parametrize("kind", ["INTEGER", "DOUBLE", "TEXT", "BOOLEAN", "DATE"])
def test_to_pandas_of_a_table_with_no_rows_keeps_its_columns(session, kind):
    df = to_pandas(session, [("c", kind)], [])
    assert len(df) == 0 and list(df.columns) == ["c"]


@pytest.mark.parametrize("kind", ["DATETIME", "DATETIMEOFFSET"])
def test_to_pandas_of_a_table_with_no_rows_and_a_datetime_column(session, kind):
    df = to_pandas(session, [("c", kind)], [])
    assert len(df) == 0 and str(df["c"].dtype) == "datetime64[ns]"


def test_to_pandas_accepts_a_datetimeoffset_column_with_mixed_offsets(session):
    rows = [
        ["/Date(1754179200000+0200)/"],
        ["/Date(1754179200000+0100)/"],
        ["/Date(1754179200000)/"],
        [None],
    ]
    df = to_pandas(session, [("o", "DATETIMEOFFSET")], rows)
    assert str(df["o"].dtype) == "datetime64[ns]"
    assert [str(v) for v in df["o"]] == [
        "2025-08-03 02:00:00",
        "2025-08-03 01:00:00",
        "2025-08-03 00:00:00",
        "NaT",
    ]


def test_to_pandas_reads_a_date_before_1970(session):
    df = to_pandas(session, [("d", "DATETIME")], [["/Date(-86400000)/"]])
    assert df["d"][0] == pd.Timestamp("1969-12-31 00:00:00")


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2025-08-03", "2025-08-03 00:00:00"),
        ("08/03/2025 10:00:00", "2025-08-03 10:00:00"),
        ("DateTime(1754179200)", "2025-08-03 00:00:00"),
        (1754179200, "2025-08-03 00:00:00"),
    ],
)
def test_to_pandas_still_parses_the_other_date_formats(session, value, expected):
    df = to_pandas(session, [("d", "DATETIME")], [[value]])
    assert df["d"][0] == pd.Timestamp(expected)


def test_to_pandas_turns_an_unparseable_date_into_nat(session, capsys):
    df = to_pandas(session, [("d", "DATETIME")], [["not a date"]])
    assert df["d"].isna()[0]
    assert "Error parsing datetime" in capsys.readouterr().out


def test_a_datetime_fault_becomes_a_value_error(session):
    session.services["TableService"] = FakeTableService(
        error=ServiceFault(
            "String was not recognized as a valid DateTime", status_code=500
        )
    )
    with pytest.raises(ValueError, match="invalid datetime values"):
        codec.decode(table_json([("d", "DATETIME")])).to_pandas()


def test_any_other_fault_passes_through_unchanged(session):
    session.services["TableService"] = FakeTableService(
        error=ServiceFault("something else", status_code=500)
    )
    with pytest.raises(ServiceFault, match="something else"):
        codec.decode(table_json([("a", "VARCHAR")])).to_pandas()


# ----------------------------------------------------------------------------------------------
# to_pandas: cell values and column types the tests above do not reach
# ----------------------------------------------------------------------------------------------


def test_to_pandas_turns_numeric_text_in_a_double_column_into_numbers(session):
    df = to_pandas(session, [("f", "DOUBLE")], [["1.5"], [None], ["2"], [""]])
    assert str(df["f"].dtype) == "float64"
    assert df["f"][0] == 1.5 and df["f"][2] == 2.0
    assert df["f"].isna().tolist() == [False, True, False, True]


def test_pinned_a_non_numeric_string_in_a_double_column_raises_the_pandas_value_error(
    session,
):
    # Pinned, needs a decision: an unparseable date is rewritten into a message about the column's values
    # (test_a_datetime_fault_becomes_a_value_error), but this error is pandas' own and does not name the column.
    with pytest.raises(ValueError, match="abc"):
        to_pandas(session, [("f", "DOUBLE")], [["abc"]])


def test_to_pandas_reads_an_unsigned_big_int_column_up_to_the_largest_value(session):
    df = to_pandas(session, [("u", "UNSIGNED BIG INT")], [[1], [2**64 - 1]])
    assert str(df["u"].dtype) == "UInt64" and df["u"][1] == 2**64 - 1
    df = to_pandas(session, [("u", "UNSIGNED BIG INT")], [[1], [None]])
    assert str(df["u"].dtype) == "UInt64" and df["u"].isna().tolist() == [False, True]


def test_to_pandas_keeps_a_big_int_exact_when_the_column_also_has_a_null(session):
    df = to_pandas(session, [("i", "BIGINT")], [[2**62 + 1], [None]])
    assert df["i"][0] == 2**62 + 1


def test_to_pandas_reads_a_large_unsigned_big_int_when_the_column_also_has_a_null(
    session,
):
    df = to_pandas(session, [("u", "UNSIGNED BIG INT")], [[2**64 - 1], [None]])
    assert df["u"][0] == 2**64 - 1


def test_to_pandas_leaves_an_unknown_column_type_as_object(session):
    df = to_pandas(session, [("w", "WEIRD")], [[1], ["x"], [None]])
    assert str(df["w"].dtype) == "object"
    assert df["w"].tolist() == [1, "x", None]


def test_pinned_a_column_type_in_lower_case_is_not_recognised_and_stays_object(
    session,
):
    # The type names are matched exactly as the server writes them (upper case); "integer" is not "INTEGER"
    df = to_pandas(session, [("i", "integer")], [[7]])
    assert str(df["i"].dtype) == "object"


# ----------------------------------------------------------------------------------------------
# parse_datetime_string: the text formats, the Python types, and what is not a date
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2025-08-03T10:00:00Z", "2025-08-03 10:00:00"),
        ("2025-08-03T10:00:00.123Z", "2025-08-03 10:00:00.123"),
        ("2025-08-03T10:00:00+0200", "2025-08-03 08:00:00"),
        ("2025-08-03T10:00:00+02:00", "2025-08-03 08:00:00"),
        ("2025-08-03T10:00:00-0530", "2025-08-03 15:30:00"),
        ("2025-08-03T10:00:00", "2025-08-03 10:00:00"),
        ("Sun, 03 Aug 2025 10:00:00 GMT", "2025-08-03 10:00:00"),
        ("03-Aug-2025", "2025-08-03 00:00:00"),
        ("03-Aug-2025 10:00:00", "2025-08-03 10:00:00"),
        ("2025-08-03 10:00:00.5", "2025-08-03 10:00:00.5"),
    ],
)
def test_parse_datetime_string_gives_a_utc_timestamp_for_each_text_format(
    text, expected
):
    parsed = parse_datetime_string(text)
    assert parsed == pd.Timestamp(expected, tz="UTC")
    assert parsed.utcoffset() == timedelta(0)  # an offset is converted away, not kept


def test_text_with_an_offset_is_an_instant_and_a_date_offset_is_a_wall_clock_time(
    session,
):
    # Two shapes, two rules, as in 0.13. Text with an offset is a DATETIMEOFFSET value or ISO text: the offset is real,
    # so it names an instant and is converted to UTC. In "/Date(ms+0200)/" the offset is the one the server added to a
    # DateTime, so the wall-clock time (02:00) is the value
    iso = to_pandas(session, [("d", "DATETIME")], [["2025-08-03T02:00:00+0200"]])
    wire = to_pandas(session, [("d", "DATETIME")], [["/Date(1754179200000+0200)/"]])
    assert iso["d"][0] == pd.Timestamp("2025-08-03 00:00:00")
    assert wire["d"][0] == pd.Timestamp("2025-08-03 02:00:00")


def test_to_pandas_gives_utc_for_iso_strings_with_and_without_an_offset(
    session,
):
    rows = [["2025-08-03T10:00:00Z"], ["2025-08-03T10:00:00+0200"], [None]]
    df = to_pandas(session, [("d", "DATETIME")], rows)
    assert str(df["d"].dtype) == "datetime64[ns]"
    assert [str(v) for v in df["d"]] == [
        "2025-08-03 10:00:00",
        "2025-08-03 08:00:00",
        "NaT",
    ]


@pytest.mark.parametrize("missing", [None, float("nan"), pd.NaT, pd.NA])
def test_parse_datetime_string_gives_nat_for_a_missing_value(missing):
    assert parse_datetime_string(missing) is pd.NaT


def test_a_float_nan_in_a_datetime_column_is_nat(session):
    df = to_pandas(session, [("d", "DATETIME")], [[float("nan")], ["2025-08-03"]])
    assert df["d"].isna().tolist() == [True, False]
    assert str(df["d"].dtype) == "datetime64[ns]"


def test_a_naive_datetime_object_is_taken_to_be_utc():
    parsed = parse_datetime_string(datetime(2025, 8, 3, 10, 0))
    assert parsed == pd.Timestamp("2025-08-03 10:00:00", tz="UTC")
    assert parsed.utcoffset() == timedelta(0)


def test_an_aware_datetime_object_keeps_its_wall_clock_time_as_utc():
    # the same as "/Date(ms+0200)/": a DateTime's offset is the server's, so the offset is added to the instant and
    # 10:00 at +02:00 reads as 10:00
    plus_two = datetime(2025, 8, 3, 10, 0, tzinfo=timezone(timedelta(hours=2)))
    assert parse_datetime_string(plus_two) == pd.Timestamp(
        "2025-08-03 10:00:00", tz="UTC"
    )
    utc = datetime(2025, 8, 3, 10, 0, tzinfo=timezone.utc)
    assert parse_datetime_string(utc) == pd.Timestamp("2025-08-03 10:00:00", tz="UTC")


def test_a_pandas_timestamp_is_read_like_a_datetime_object():
    parsed = parse_datetime_string(pd.Timestamp("2025-08-03 10:00:00"))
    assert parsed == pd.Timestamp("2025-08-03 10:00:00", tz="UTC")


@pytest.mark.parametrize(
    "number, expected",
    [
        (0, "1970-01-01 00:00:00"),
        (-1, "1969-12-31 23:59:59"),
        (1754179200, "2025-08-03 00:00:00"),
        (1754179200.5, "2025-08-03 00:00:00.5"),
    ],
)
def test_a_number_is_unix_seconds_in_utc(number, expected):
    assert parse_datetime_string(number) == pd.Timestamp(expected, tz="UTC")


def test_a_number_too_large_to_be_a_date_is_nat():
    assert parse_datetime_string(10**30) is pd.NaT


@pytest.mark.parametrize(
    "value, type_name", [(b"x", "bytes"), ({"a": 1}, "dict"), (("a", "b"), "tuple")]
)
def test_an_unsupported_value_type_prints_a_message_and_is_nat(
    value, type_name, capsys
):
    assert parse_datetime_string(value) is pd.NaT
    assert "Unsupported type: <class '%s'>" % type_name in capsys.readouterr().out


def test_a_list_of_values_is_an_unsupported_type_and_not_a_crash(capsys):
    assert parse_datetime_string([1, 2]) is pd.NaT
    assert "Unsupported type" in capsys.readouterr().out


def test_an_unsupported_cell_in_a_datetime_column_becomes_nat_in_the_frame(
    session, capsys
):
    df = to_pandas(session, [("d", "DATETIME")], [[{"a": 1}], ["2025-08-03"]])
    assert df["d"].isna().tolist() == [True, False]
    assert "Unsupported type" in capsys.readouterr().out


@pytest.mark.parametrize("text", ["   ", "garbage"])
def test_text_that_is_not_a_date_is_nat_with_a_message(text, capsys):
    assert parse_datetime_string(text) is pd.NaT
    assert "Error parsing datetime" in capsys.readouterr().out


@pytest.mark.parametrize(
    "text",
    ["", "NaT", "nan"],
)
def test_text_that_pandas_reads_as_missing_is_nat_without_a_message(text, capsys):
    assert parse_datetime_string(text) is pd.NaT
    assert capsys.readouterr().out == ""


# ----------------------------------------------------------------------------------------------
# _repr_html_
# ----------------------------------------------------------------------------------------------


def test_repr_html_shows_a_pandas_table_by_default(session):
    session.services["TableService"] = FakeTableService(
        ["a", "b"], [["x", 1], ["y", 2]]
    )
    html = codec.decode(table_json([("a", "VARCHAR"), ("b", "INTEGER")]))._repr_html_()
    assert "<table" in html and ">x<" in html and ">y<" in html
    assert "PostUiTableByTable" not in html


def test_repr_html_shows_the_interactive_table_when_asked(session, show_interactive):
    table = codec.decode(table_json([("a", "VARCHAR"), ("b", "INTEGER")]))
    html = table._repr_html_()
    assert URI + "Services/TableService.svc/PostUiTableByTable" in html
    assert URI + "Services/AssetService.svc/GetJavascript" in html
    assert URI + "scripts/vendor/DataTables/media/css/jquery.dataTables.css" in html
    assert '"title": "a"' in html and '"title": "b"' in html  # the column names
    assert "<#=" not in html  # every template marker was filled in
    # the browser posts this back to the service, so it must be the type-tagged wire JSON
    assert '"__type": "Table:#CompAnalytics.Contracts.Tables"' in html
    assert '"TableName": "t"' in html
