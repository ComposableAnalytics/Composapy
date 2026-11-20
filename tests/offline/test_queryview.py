"""Offline tests for the QueryView contract factories and the QueryView driver, wrapper, and api.

A fake QueryViewService (and PropertyService, for saved QueryViews) stand in for the real ones.
"""

import json

import pandas as pd
import pytest

from composapy._wire import codec
from composapy.auth import AuthMode
from composapy.contracts.queryview import (
    PagingOptions,
    QueryView as new_query_view,
    ValidationOptions,
)
from composapy.decorators import SessionRequiredError
from composapy.interactive.itable import IDataSource, ITableResult
from composapy.key.models import KeyObject
from composapy.queryview.api import QueryView
from composapy.queryview.models import (
    KeyRequiredException,
    QueryException,
    QueryInputException,
    QueryViewObject,
    QueryViewPagedObject,
)
from composapy.session import Session

URI = "http://example.test/CompApp/"
QUERY_VIEW_TYPE = "QueryView:#CompAnalytics.Contracts.QueryView"


def make_key(key_id=7, name="my key"):
    return KeyObject(
        codec.decode(
            json.dumps(
                {
                    "__type": "Property:#CompAnalytics.Contracts",
                    "Id": key_id,
                    "Name": name,
                    "DisplayType": "SqlConnectionSettings",
                    "Value": None,
                }
            )
        )
    )


def result(columns, rows, error=None):
    """A QueryViewData reply: columns are (name, .NET type) pairs."""
    return codec.decode(
        json.dumps(
            {
                "Error": error,
                "ColumnDefinitions": [
                    {"Name": n, "Type": t, "Exclude": False} for n, t in columns
                ],
                "Data": rows,
            }
        )
    )


class FakeQueryViewService:
    def __init__(self, reply=None, saved=None, compile_errors=None):
        self.reply = (
            reply
            if reply is not None
            else result([("n", "System.Int64")], [["1"], ["2"]])
        )
        self.saved, self.compile_errors = saved, compile_errors or []
        self.calls = []

    def Get(self, query_view_id):
        self.calls.append(("Get", query_view_id))
        return self.saved

    def CompileQuery(self, query_view, options):
        self.calls.append(("CompileQuery", dict(options)))
        return codec.decode(json.dumps({"Errors": self.compile_errors}))

    def RunQueryDynamic(self, query_view):
        # record what the driver sent, as plain values: the same contract object is changed again afterwards
        self.calls.append(
            (
                "RunQueryDynamic",
                query_view.QueryString,
                query_view.QueryTimeout,
                query_view.DbConnectionId,
                query_view.PagingOptions.PageLimit,
            )
        )
        return self.reply


class FakePropertyService:
    def __init__(self):
        self.calls = []

    def GetProperty(self, property_id):
        self.calls.append(property_id)
        return make_key(property_id, "saved key").contract


@pytest.fixture
def session():
    session = Session(uri=URI, auth_mode=AuthMode.TOKEN, credentials="token-for-tests")
    session.register()
    yield session
    Session.clear_registration()
    KeyObject.clear_registration()


@pytest.fixture
def service(session):
    fake = FakeQueryViewService()
    session.services["QueryViewService"] = fake
    return fake


# ----------------------------------------------------------------------------------------------
# The factories
# ----------------------------------------------------------------------------------------------


def test_a_new_query_view_has_the_defaults_the_dotnet_constructor_set():
    contract = new_query_view()
    assert contract.type_name == QUERY_VIEW_TYPE
    assert contract.AutoRun is True and contract.OutputType == "grid"
    for name in (
        "LiteralInputs",
        "SearchInputs",
        "OrderClause",
        "ColumnDefinitions",
        "QueryViewActions",
        "QueryViewLinks",
        "ChildQueryViewConnections",
    ):
        assert contract[name] == [], name
    assert (
        contract.QueryString is None
        and contract.QueryTimeout is None
        and contract.DbConnectionId is None
    )


def test_a_new_query_view_has_its_own_paging_options():
    first, second = new_query_view(), new_query_view()
    assert first.PagingOptions == PagingOptions()
    assert (
        first.PagingOptions is not second.PagingOptions
    )  # not shared between query views
    assert first.LiteralInputs is not second.LiteralInputs


def test_paging_options_and_validation_options_have_all_their_members():
    assert dict(PagingOptions()) == {
        "__type": "PagingOptions:#CompAnalytics.Contracts.QueryView",
        "AutoPaging": False,
        "DefaultOrderClause": None,
        "FullPaging": False,
        "LimitPaging": False,
        "PageLimit": 0,
        "PageNum": 0,
    }
    assert dict(ValidationOptions()) == {
        "__type": "ValidationOptions:#CompAnalytics.Contracts.QueryView",
        "IsCountQuery": False,
        "IsTemplateQuery": False,
    }


def test_overrides_replace_defaults_and_keep_the_member_order():
    contract = new_query_view(Name="sales", QueryTimeout=30)
    assert contract.Name == "sales" and contract.QueryTimeout == 30
    assert list(contract)[0] == "__type"
    assert list(contract) == list(new_query_view())


def test_a_new_query_view_writes_and_reads_back_unchanged():
    text = codec.encode(new_query_view(Name="sales"))
    assert json.loads(codec.encode(codec.decode(text))) == json.loads(text)
    assert list(json.loads(text))[0] == "__type"


# ----------------------------------------------------------------------------------------------
# The driver
# ----------------------------------------------------------------------------------------------


def test_driver_defaults(session):
    driver = QueryView.driver()
    assert type(driver) is QueryViewObject
    assert driver.get_driver_timeout() == 10 and driver.validate_query is False
    assert driver.key is None
    assert repr(driver) == "QueryViewObject(name='None', key='None')"


def test_the_driver_exposes_the_contract_members_as_attributes(session):
    driver = QueryView.driver()
    assert (
        driver.OutputType == "grid" and driver.AutoRun is True and driver.Name is None
    )
    assert not hasattr(driver, "__type") and not hasattr(driver, "Inputs")


def test_driver_with_a_key_connects_it(session):
    key = make_key(42, "warehouse")
    driver = QueryView.driver(key)
    assert driver.key is key and driver.contract.DbConnectionId == 42
    assert repr(driver) == "QueryViewObject(name='None', key='warehouse')"


def test_a_registered_key_is_used_without_being_passed(session):
    make_key(99).register()
    assert QueryView.driver().contract.DbConnectionId == 99


def test_connect_changes_the_key(session):
    driver = QueryView.driver(make_key(1))
    driver.connect(make_key(2))
    assert driver.contract.DbConnectionId == 2


def test_the_interactive_driver_is_the_paged_one(session):
    assert type(QueryView.driver(interactive=True)) is QueryViewPagedObject


@pytest.mark.parametrize(
    "timeout, error", [("5", TypeError), (1.5, TypeError), (-1, ValueError)]
)
def test_a_bad_timeout_is_rejected(session, timeout, error):
    with pytest.raises(error):
        QueryView.driver(timeout=timeout)


def test_a_custom_timeout_is_kept(session):
    assert QueryView.driver(timeout=3).get_driver_timeout() == 3


def test_validate_query_must_be_a_bool(session):
    with pytest.raises(TypeError):
        QueryView.driver(validate_query="yes")


# ----------------------------------------------------------------------------------------------
# Running a query
# ----------------------------------------------------------------------------------------------


def test_running_without_a_key_is_refused(service):
    with pytest.raises(KeyRequiredException):
        QueryView.driver().run("select 1")
    assert service.calls == []


def test_run_sends_the_query_with_the_timeout_and_key(service):
    driver = QueryView.driver(make_key(7), timeout=20)
    df = driver.run("select n from t")
    assert service.calls == [("RunQueryDynamic", "select n from t", 20, 7, 0)]
    assert list(df["n"]) == [1, 2] and str(df["n"].dtype) == "Int64"


def test_a_timeout_given_to_run_applies_once_and_is_then_restored(service):
    driver = QueryView.driver(make_key(), timeout=20)
    driver.run("select 1", timeout=5)
    driver.run("select 2")
    assert [call[2] for call in service.calls] == [5, 20]
    assert driver.get_driver_timeout() == 20


def test_the_timeout_is_restored_even_when_the_query_fails(session):
    class Failing(FakeQueryViewService):
        def RunQueryDynamic(self, query_view):
            raise RuntimeError("boom")

    session.services["QueryViewService"] = Failing()
    driver = QueryView.driver(make_key(), timeout=20)
    with pytest.raises(RuntimeError):
        driver.run("select 1", timeout=5)
    assert driver.get_driver_timeout() == 20


def test_a_query_error_from_the_server_becomes_a_query_exception(session):
    session.services["QueryViewService"] = FakeQueryViewService(
        reply=result([], [], error="Invalid object name 't'.")
    )
    with pytest.raises(QueryException, match="Invalid object name 't'."):
        QueryView.driver(make_key()).run("select * from t")


def test_validation_compiles_first_and_runs_when_there_are_no_errors(service):
    QueryView.driver(make_key(), validate_query=True).run("select 1")
    assert [call[0] for call in service.calls] == ["CompileQuery", "RunQueryDynamic"]
    assert service.calls[0][1] == {
        "__type": "ValidationOptions:#CompAnalytics.Contracts.QueryView",
        "IsCountQuery": False,
        "IsTemplateQuery": False,
    }


def test_validation_errors_stop_the_query_and_warnings_do_not(session):
    errors = [
        {
            "Message": "Incorrect syntax near 'x'",
            "IsWarning": False,
            "Start": {"LineNumber": 3, "ColumnNumber": 8},
        },
        {
            "Message": "Just a warning",
            "IsWarning": True,
            "Start": {"LineNumber": 1, "ColumnNumber": 1},
        },
    ]
    fake = FakeQueryViewService(compile_errors=errors)
    session.services["QueryViewService"] = fake
    with pytest.raises(QueryException) as raised:
        QueryView.driver(make_key(), validate_query=True).run("select x")
    assert (
        str(raised.value) == "Incorrect syntax near 'x' (3, 8)"
    )  # the warning is left out
    assert [call[0] for call in fake.calls] == ["CompileQuery"]  # and nothing was run


def test_validation_can_be_turned_on_or_off_for_one_run(service):
    driver = QueryView.driver(make_key(), validate_query=True)
    driver.run("select 1", validate_query=False)
    assert [call[0] for call in service.calls] == ["RunQueryDynamic"]
    service.calls.clear()
    QueryView.driver(make_key()).run("select 1", validate_query=True)
    assert [call[0] for call in service.calls] == ["CompileQuery", "RunQueryDynamic"]


def test_run_rejects_a_validate_query_that_is_not_a_bool(service):
    with pytest.raises(TypeError):
        QueryView.driver(make_key()).run("select 1", validate_query="yes")


# ----------------------------------------------------------------------------------------------
# Turning a result into a DataFrame
# ----------------------------------------------------------------------------------------------


def test_column_types_map_to_pandas_dtypes():
    reply = result(
        [
            ("s", "System.String"),
            ("i64", "System.Int64"),
            ("i32", "System.Int32"),
            ("i16", "System.Int16"),
            ("b", "System.Byte"),
            ("d", "System.Double"),
            ("m", "System.Decimal"),
            ("f", "System.Single"),
            ("g", "System.Guid"),
        ],
        [
            [
                "x",
                "1",
                "2",
                "3",
                "4",
                "1.5",
                "2.5",
                "3.5",
                "be733cc6-df15-4cd6-8f37-73d1c8def3f7",
            ]
        ],
    )
    df = QueryViewObject._qv_result_to_df(reply)
    assert {name: str(dtype) for name, dtype in df.dtypes.items()} == {
        "s": "object",
        "i64": "Int64",
        "i32": "Int32",
        "i16": "Int16",
        "b": "UInt8",
        "d": "float64",
        "m": "float64",
        "f": "float32",
        "g": "object",
    }
    assert df.loc[0, "d"] == 1.5 and df.loc[0, "i64"] == 1


def test_datetime_columns_become_datetimes():
    df = QueryViewObject._qv_result_to_df(
        result([("t", "System.DateTime")], [["2025-08-03 10:30:00"]])
    )
    assert str(df["t"].dtype) == "datetime64[ns]" and df["t"][0] == pd.Timestamp(
        "2025-08-03 10:30:00"
    )


def test_boolean_text_is_mapped_by_value_not_by_truthiness():
    # df.astype("boolean") would make the text "False" True, because it is a non-empty string
    df = QueryViewObject._qv_result_to_df(
        result([("b", "System.Boolean")], [["True"], ["False"], [""], [None]])
    )
    assert str(df["b"].dtype) == "boolean"
    assert df["b"].tolist()[:2] == [True, False] and df["b"].isna().tolist() == [
        False,
        False,
        True,
        True,
    ]


def test_excluded_columns_are_left_out():
    reply = codec.decode(
        json.dumps(
            {
                "Error": None,
                "ColumnDefinitions": [
                    {"Name": "keep", "Type": "System.Int64", "Exclude": False},
                    {"Name": "hide", "Type": "System.Int64", "Exclude": True},
                ],
                "Data": [["1", "2"]],
            }
        )
    )
    # the data rows carry only the visible columns, as the server sends them
    reply["Data"] = [["1"]]
    assert list(QueryViewObject._qv_result_to_df(reply).columns) == ["keep"]


# ----------------------------------------------------------------------------------------------
# The paged (interactive) driver
# ----------------------------------------------------------------------------------------------


def test_the_paged_driver_defaults_to_autopaging_and_reads_one_row_first(session):
    driver = QueryViewPagedObject(new_query_view())
    paging = driver.contract.PagingOptions
    assert (paging.AutoPaging, paging.PageNum, paging.DefaultOrderClause) == (
        True,
        1,
        "1",
    )
    assert paging.PageLimit == 1  # just enough to learn the column names
    assert driver._original_page_limit == 10


def test_the_paged_driver_wraps_the_query_and_returns_an_interactive_result(service):
    driver = QueryViewPagedObject(new_query_view(), timeout=20)
    driver.connect(make_key(7))
    interactive = driver.run("select n from t")

    assert service.calls[0][1] == "select * from (select n from t) r"
    assert service.calls[0][4] == 1  # the first run asks for one row
    assert (
        driver.contract.PagingOptions.PageLimit == 10
    )  # and the real page size is put back afterwards
    assert type(interactive) is ITableResult
    assert (
        interactive.columns == ["n"]
        and interactive.src is IDataSource.QUERYVIEW
        and interactive.contract is driver.contract
    )


def test_a_saved_query_view_keeps_its_own_paging_and_connects_its_saved_key(session):
    properties = FakePropertyService()
    session.services["PropertyService"] = properties
    saved = new_query_view(DbConnectionId=55)
    saved.PagingOptions.LimitPaging = True
    saved.PagingOptions.PageLimit = 25

    driver = QueryViewPagedObject(saved, saved=True)
    assert (
        properties.calls == [55]
        and driver.key.name == "saved key"
        and driver.contract.DbConnectionId == 55
    )
    assert driver._qv_has_saved_paging is True
    assert (
        driver.contract.PagingOptions.AutoPaging is False
    )  # the saved settings were not overwritten
    assert driver._original_page_limit == 25


def test_a_registered_key_does_not_replace_the_saved_querys_key(session):
    session.services["PropertyService"] = FakePropertyService()
    make_key(1, "global key").register()
    driver = QueryViewPagedObject(new_query_view(DbConnectionId=55), saved=True)
    assert driver.contract.DbConnectionId == 55 and driver.key.name == "saved key"


# ----------------------------------------------------------------------------------------------
# Running a saved QueryView with inputs
# ----------------------------------------------------------------------------------------------


def saved_query_view():
    contract = new_query_view(
        Id=123, Name="saved", QueryString="select 1\nfrom t", DbConnectionId=55
    )
    contract.LiteralInputs = [
        {
            "__type": "LiteralInput:#CompAnalytics.Contracts.QueryView",
            "DisplayName": "Region",
            "Value": "all",
            "IsMultiChoice": False,
        },
    ]
    contract.SearchInputs = [
        {
            "__type": "SearchInput:#CompAnalytics.Contracts.QueryView",
            "DisplayName": "Total",
            "Value": None,
            "DefaultOperator": "=",
            "OperatorOptional": True,
            "IsMultiChoice": False,
        },
        {
            "__type": "SearchInput:#CompAnalytics.Contracts.QueryView",
            "DisplayName": "Fixed",
            "Value": None,
            "DefaultOperator": "=",
            "OperatorOptional": False,
            "IsMultiChoice": False,
        },
    ]
    # make them contract objects, as a decoded reply would hold them
    contract.LiteralInputs = [
        codec.decode(codec.encode(item)) for item in contract.LiteralInputs
    ]
    contract.SearchInputs = [
        codec.decode(codec.encode(item)) for item in contract.SearchInputs
    ]
    return contract


@pytest.fixture
def saved(session):
    contract = saved_query_view()
    fake = FakeQueryViewService(saved=contract)
    session.services["QueryViewService"] = fake
    return contract, fake


def test_running_a_saved_query_view_returns_a_dataframe(saved):
    contract, fake = saved
    df = QueryView.run(123)
    assert fake.calls[0] == ("Get", 123) and list(df["n"]) == [1, 2]


def test_a_literal_input_is_set_by_display_name(saved):
    contract, _ = saved
    QueryView.run(123, inputs={"Region": "north"})
    assert contract.LiteralInputs[0].Value == "north"


def test_a_search_input_takes_a_value_and_an_allowed_operator(saved):
    contract, _ = saved
    QueryView.run(123, inputs={"Total": (100, ">=")})
    assert (
        contract.SearchInputs[0].Value == "100"
        and contract.SearchInputs[0].DefaultOperator == ">="
    )


def test_a_non_default_operator_is_refused_when_the_input_does_not_allow_changes(saved):
    with pytest.raises(QueryInputException):
        QueryView.run(123, inputs={"Fixed": (1, ">")})
    QueryView.run(123, inputs={"Fixed": (1, "=")})  # the default operator is fine


def test_a_list_of_values_makes_a_multichoice_input(saved):
    contract, _ = saved
    QueryView.run(123, inputs={"Region": [("north", "south")]})
    # The server reads the list from the JSON array text that run() writes as the input's value
    assert contract.LiteralInputs[0].Value == '["north","south"]'


@pytest.mark.parametrize(
    "inputs",
    [
        ["not", "a", "dict"],  # inputs must be a dict
        {"Region": ("a", "=", "extra")},  # more than a value and an operator
        {"Region": ("a", "~~")},  # an operator that is not allowed
        {"No such input": "x"},  # no input has that display name
    ],
    ids=["not-a-dict", "three-items", "bad-operator", "unknown-name"],
)
def test_bad_inputs_are_refused(saved, inputs):
    with pytest.raises(QueryInputException):
        QueryView.run(123, inputs=inputs)


def test_a_saved_query_view_error_becomes_a_query_exception(session):
    session.services["QueryViewService"] = FakeQueryViewService(
        saved=saved_query_view(),
        reply=result([], [], error="Timeout expired"),
    )
    with pytest.raises(QueryException, match="Timeout expired"):
        QueryView.run(123)


def test_the_interactive_saved_run_flattens_the_query_text_and_wraps_it_for_autopaging(
    session,
):
    fake = FakeQueryViewService(saved=saved_query_view())  # no paging saved with it
    session.services["QueryViewService"] = fake
    session.services["PropertyService"] = FakePropertyService()
    interactive = QueryView.run(123, interactive=True)
    assert type(interactive) is ITableResult
    assert (
        fake.calls[1][1] == "select * from (select 1 from t) r"
    )  # the newline became a space, then autopaging wraps it


def test_the_interactive_saved_run_leaves_the_query_alone_when_paging_was_saved(
    session,
):
    contract = saved_query_view()
    contract.PagingOptions.FullPaging = True
    fake = FakeQueryViewService(saved=contract)
    session.services["QueryViewService"] = fake
    session.services["PropertyService"] = FakePropertyService()
    QueryView.run(123, interactive=True)
    assert fake.calls[1][1] == "select 1 from t"  # flattened, but not wrapped


@pytest.mark.parametrize(
    "value, expected",
    [(5, "5"), (2.5, "2.5"), ("text", "text"), (True, "true"), (False, "false")],
)
def test_single_values_are_written_as_text(value, expected):
    assert QueryView._format_qv_value(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (["a", "b"], '["a","b"]'),
        (("a", "b"), '["a","b"]'),
        ([1, 2], "[1,2]"),
        ([True, False], "[true,false]"),
    ],
)
def test_several_values_are_written_as_a_json_style_list(value, expected):
    assert QueryView._format_qv_value(value) == expected


def test_a_value_that_is_not_a_primitive_or_a_list_is_refused():
    with pytest.raises(QueryInputException):
        QueryView._format_qv_value({"a": 1})
    with pytest.raises(QueryInputException):
        QueryView._format_qv_value([object()])


def test_a_query_that_is_not_text_is_a_type_error_as_the_dotnet_string_property_made_it(
    session,
):
    driver = QueryView.driver(make_key(1, "k"))
    for value in (5, 5.5, ["select 1"], b"select 1", {"q": 1}):
        with pytest.raises(TypeError, match="must be a str"):
            driver.run(value)


def test_no_query_at_all_is_not_refused_by_the_type_check(service):
    driver = QueryView.driver(make_key(1, "k"))
    driver.run(None)  # what an empty query means is for the server to say
    assert service.calls[0][:2] == ("RunQueryDynamic", None)


def test_a_bool_timeout_is_stored_as_the_int_dotnet_stored(session):
    driver = QueryView.driver(make_key(1, "k"))
    driver.set_driver_timeout(True)
    assert driver.get_driver_timeout() == 1 and type(driver.get_driver_timeout()) is int
    driver.set_driver_timeout(30)
    assert type(driver.get_driver_timeout()) is int


@pytest.mark.parametrize(
    "items",
    [
        ['a"b', "c"],
        ['say "hi"', "it's"],
        ["back\\slash", "tab\there"],
        ["a]b", "[c", "d[e]f"],
        ["", " "],
        ["é", "日本"],
    ],
)
def test_the_text_of_a_multichoice_value_is_a_json_array_the_server_can_read(items):
    text = QueryView._format_qv_value(items)

    assert json.loads(text) == items
    # The server reads the text as an array only when its first "[" and its first "]" are the ends of it
    assert text.startswith("[") and text.endswith("]")
    assert text.count("[") == 1 and text.index("]") == len(text) - 1


def test_a_multichoice_value_of_mixed_kinds_keeps_numbers_and_booleans_bare():
    assert (
        QueryView._format_qv_value(["a", 1, 2.5, True, False])
        == '["a",1,2.5,true,false]'
    )


# ----------------------------------------------------------------------------------------------
# More ways of passing inputs to a saved QueryView
# ----------------------------------------------------------------------------------------------


def test_pinned_an_operator_given_for_a_literal_input_is_checked_and_then_ignored(
    saved,
):
    # Pinned, needs a decision: a literal input has no operator, so ">" is accepted without a word about it
    contract, _ = saved
    QueryView.run(123, inputs={"Region": ("north", ">")})
    literal = contract.LiteralInputs[0]
    assert literal.Value == "north"
    assert "DefaultOperator" not in literal


def test_an_operator_given_for_a_literal_input_must_still_be_an_acceptable_one(saved):
    with pytest.raises(QueryInputException, match="Operator '~~'"):
        QueryView.run(123, inputs={"Region": ("north", "~~")})


@pytest.mark.parametrize("operator", ["like", "Like", "", " ="])
def test_pinned_an_operator_is_matched_exactly_so_lowercase_like_is_refused(
    saved, operator
):
    # Pinned, needs a decision: the list is ("=", "!=", ">=", "<=", ">", "<", "LIKE") and the match is case-sensitive
    with pytest.raises(QueryInputException, match="not an acceptable option"):
        QueryView.run(123, inputs={"Total": (1, operator)})


@pytest.mark.parametrize("value", [(), []], ids=["tuple", "list"])
def test_an_empty_pair_is_refused_with_a_message_that_says_what_is_accepted(
    saved, value
):
    with pytest.raises(QueryInputException) as error:
        QueryView.run(123, inputs={"Region": value})
    message = str(error.value)
    assert "Input 'Region' takes a value, or a (value, operator) pair" in message
    assert "length 0" in message and "length 2" not in message


def test_a_pair_of_three_is_refused_with_the_same_message(saved):
    with pytest.raises(QueryInputException, match="Input 'Total' takes a value, or a"):
        QueryView.run(123, inputs={"Total": (1, "=", 3)})


@pytest.mark.parametrize("value", [("north",), ["north"]], ids=["tuple", "list"])
def test_a_pair_of_one_is_a_value_with_no_operator(saved, value):
    contract, _ = saved
    QueryView.run(123, inputs={"Total": value})
    search = contract.SearchInputs[0]
    assert search.Value == "north" and search.DefaultOperator == "="


def test_a_search_input_with_a_list_of_values_and_an_operator(saved):
    contract, _ = saved
    QueryView.run(123, inputs={"Total": ([1, 2], ">=")})
    search = contract.SearchInputs[0]
    assert search.Value == "[1,2]" and search.DefaultOperator == ">="


def test_a_search_input_with_a_list_of_values_and_no_operator(saved):
    contract, _ = saved
    QueryView.run(123, inputs={"Total": [(1, 2)]})
    search = contract.SearchInputs[0]
    assert search.Value == "[1,2]" and search.DefaultOperator == "="


def test_a_search_input_that_does_not_allow_operator_changes_takes_a_list_with_its_own_operator(
    saved,
):
    contract, _ = saved
    QueryView.run(123, inputs={"Fixed": (["a", "b"], "=")})
    assert contract.SearchInputs[1].Value == '["a","b"]'
    with pytest.raises(
        QueryInputException, match="non-default operator for search input 'Fixed'"
    ):
        QueryView.run(123, inputs={"Fixed": (["a", "b"], "<")})


def test_a_plain_list_of_two_values_is_read_as_a_value_and_an_operator(saved):
    # the documented way to pass several values is a list inside a list
    with pytest.raises(QueryInputException, match="Operator 'south'"):
        QueryView.run(123, inputs={"Total": ["north", "south"]})


def test_a_set_of_values_is_a_list_of_values(saved):
    contract, _ = saved
    QueryView.run(123, inputs={"Region": {"north"}})
    assert contract.LiteralInputs[0].Value == '["north"]'


@pytest.mark.parametrize("value", [None, (None,), (None, "=")], ids=["bare", "1", "2"])
def test_none_as_a_value_is_refused_with_a_message_that_a_value_is_needed(saved, value):
    # None is not a way to clear an input
    with pytest.raises(
        QueryInputException, match="A value is needed for input 'Region'"
    ) as error:
        QueryView.run(123, inputs={"Region": value})
    assert "Iterable" not in str(error.value)


def test_no_inputs_and_empty_inputs_change_nothing(saved):
    contract, fake = saved
    before = codec.encode(contract)
    QueryView.run(123)
    QueryView.run(123, inputs={})
    assert codec.encode(contract) == before
    assert [call[0] for call in fake.calls] == ["Get", "RunQueryDynamic"] * 2


def test_an_input_is_matched_by_its_exact_display_name(saved):
    with pytest.raises(
        QueryInputException, match="No input found matching the display name 'region'"
    ):
        QueryView.run(123, inputs={"region": "north"})


def test_pinned_a_name_that_a_literal_and_a_search_input_share_sets_only_the_literal(
    saved,
):
    # Pinned, needs a decision: the literal inputs are searched first and the search stops at the first match
    contract, _ = saved
    contract.SearchInputs[0].DisplayName = "Region"
    QueryView.run(123, inputs={"Region": "north"})
    assert contract.LiteralInputs[0].Value == "north"
    assert contract.SearchInputs[0].Value is None


def test_pinned_inputs_given_before_a_bad_one_have_already_been_set_when_it_is_refused(
    saved,
):
    # Pinned, needs a decision: the inputs are applied one at a time, so nothing is rolled back; the contract is the
    # server's copy, so this only shows when the same object is looked at again
    contract, fake = saved
    with pytest.raises(QueryInputException, match="No input found"):
        QueryView.run(123, inputs={"Region": "north", "Missing": "x"})
    assert contract.LiteralInputs[0].Value == "north"
    assert [call[0] for call in fake.calls] == ["Get"]  # and nothing was run


def test_an_interactive_run_sends_the_inputs_it_was_given(session):
    contract = saved_query_view()
    session.services["QueryViewService"] = FakeQueryViewService(saved=contract)
    session.services["PropertyService"] = FakePropertyService()
    interactive = QueryView.run(
        123, inputs={"Region": "north", "Total": (5, ">=")}, interactive=True
    )
    assert type(interactive) is ITableResult and interactive.contract is contract
    assert contract.LiteralInputs[0].Value == "north"
    assert contract.SearchInputs[0].Value == "5"
    assert contract.SearchInputs[0].DefaultOperator == ">="


def test_an_interactive_run_with_a_bad_input_is_refused_before_the_query_is_run(
    session,
):
    fake = FakeQueryViewService(saved=saved_query_view())
    session.services["QueryViewService"] = fake
    with pytest.raises(QueryInputException):
        QueryView.run(123, inputs={"Nope": 1}, interactive=True)
    assert [call[0] for call in fake.calls] == ["Get"]


def test_an_interactive_run_of_a_saved_view_with_no_key_says_the_view_has_no_key(
    session,
):
    # KeyRequiredException is what the driver already raises when it is run without a key
    contract = saved_query_view()
    contract.DbConnectionId = None
    session.services["QueryViewService"] = FakeQueryViewService(saved=contract)
    session.services["PropertyService"] = FakePropertyService()
    with pytest.raises(
        KeyRequiredException, match="saved query view 'saved' has no database key"
    ) as error:
        QueryView.run(123, interactive=True)
    assert "Save the query view with a key" in str(error.value)


def test_the_paged_driver_made_from_a_saved_view_with_no_key_says_the_view_has_no_key(
    session,
):
    session.services["PropertyService"] = FakePropertyService()
    with pytest.raises(
        KeyRequiredException, match="saved query view 'named' has no database key"
    ):
        QueryViewPagedObject(new_query_view(Name="named"), saved=True)


# ----------------------------------------------------------------------------------------------
# Without a session, and a timeout that is refused
# ----------------------------------------------------------------------------------------------


def test_running_a_saved_query_view_needs_a_registered_session():
    with pytest.raises(SessionRequiredError):
        QueryView.run(123)


def test_running_a_query_on_a_driver_needs_a_registered_session():
    driver = QueryView.driver(make_key())  # a driver can be made without one
    with pytest.raises(SessionRequiredError):
        driver.run("select 1")


def test_the_paged_driver_needs_a_registered_session_to_run():
    driver = QueryViewPagedObject(new_query_view())
    with pytest.raises(SessionRequiredError):
        driver.run("select 1")


@pytest.mark.parametrize(
    "timeout, error", [("x", TypeError), (1.5, TypeError), (-1, ValueError)]
)
def test_a_timeout_that_is_refused_by_run_leaves_the_drivers_timeout_and_runs_nothing(
    service, timeout, error
):
    driver = QueryView.driver(make_key(), timeout=20)
    with pytest.raises(error):
        driver.run("select 1", timeout=timeout)
    assert driver.get_driver_timeout() == 20 and service.calls == []
    driver.run("select 2")
    assert [call[2] for call in service.calls] == [20]


def test_a_timeout_of_zero_is_sent_as_zero_and_then_the_old_one_is_back(service):
    driver = QueryView.driver(make_key(), timeout=20)
    driver.run("select 1", timeout=0)
    assert [call[2] for call in service.calls] == [0]
    assert driver.get_driver_timeout() == 20


def test_a_validation_error_leaves_the_timeout_alone_because_no_change_was_made_yet(
    session,
):
    errors = [
        {
            "Message": "Incorrect syntax",
            "IsWarning": False,
            "Start": {"LineNumber": 1, "ColumnNumber": 1},
        }
    ]
    session.services["QueryViewService"] = FakeQueryViewService(compile_errors=errors)
    driver = QueryView.driver(make_key(), timeout=20, validate_query=True)
    with pytest.raises(QueryException):
        driver.run("select x", timeout=5)
    assert driver.get_driver_timeout() == 20
