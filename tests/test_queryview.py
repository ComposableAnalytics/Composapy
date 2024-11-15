from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
import re
from typing import TYPE_CHECKING

from composapy.interactive.itable import ITableResult
from composapy.queryview.models import (
    QueryException,
    QueryInputException,
    KeyRequiredException,
)
from composapy.queryview.api import QueryView

if TYPE_CHECKING:
    from composapy.session import Session


def test_query_health_db(queryview_driver):
    df = queryview_driver.run("select top 100 * from syndromic_events")

    assert len(df) == 100


@pytest.mark.parametrize(
    "data",
    [
        ("tinyint", pd.UInt8Dtype(), [0, 255]),
        ("smallint", pd.Int16Dtype(), [-32768, 32767]),
        ("int", pd.Int32Dtype(), [-2147483648, 2147483647]),
        ("bigint", pd.Int64Dtype(), [-9223372036854775808, 9223372036854775807]),
        ("real", np.float32, [-3.402e38, 3.402e38]),
        ("float", np.float64, [-1.797e308, 1.797e308]),
    ],
    indirect=False,
)
def test_query_health_db_nullable_int_float(queryview_driver, data):
    df = queryview_driver.run(
        f"""
        select
	        cast(r.x as {data[0]}) as x
        from (
            select {data[2][0]} as x
            union all
            select {data[2][1]} as x
            union all
            select null as x
        ) as r
    """
    )

    assert len(df) == 3
    assert df["x"].dtype == data[1]
    assert np.allclose(list(df["x"])[0:2], data[2])
    assert df["x"].isna().sum() == 1


@pytest.mark.parametrize(
    "data",
    [("text", "object", ["yes", "no"]), ("varchar", "object", ["yes", "no"])],
    indirect=False,
)
def test_query_health_db_nullable_str(queryview_driver, data):
    df = queryview_driver.run(
        f"""
        select
	        cast(r.x as {data[0]}) as x
        from (
            select '{data[2][0]}' as x
            union all
            select '{data[2][1]}' as x
            union all
            select null as x
        ) as r
    """
    )

    assert len(df) == 3
    assert str(df["x"].dtype) == data[1]
    assert list(df["x"])[0:2] == data[2]
    assert df["x"].isna().sum() == 1


def test_query_health_db_nullable_bool(queryview_driver):
    df = queryview_driver.run(
        f"""
        select
	        cast(r.x as bit) as x
        from (
            select 'true' as x
            union all
            select 'false' as x
            union all
            select null as x
        ) as r
    """
    )

    assert len(df) == 3
    assert df["x"].dtype == pd.BooleanDtype()
    assert list(df["x"])[0:2] == [True, False]
    assert df["x"].isna().sum() == 1


def test_query_health_db_nullable_datetime(queryview_driver):
    df = queryview_driver.run(
        f"""
        select cast(getdate() as datetime) as today
        union
        select null as today
    """
    )

    assert len(df) == 2
    assert str(df["today"].dtype) == "datetime64[ns]"
    assert df["today"].isna().sum() == 1


def test_query_error_response_default(queryview_driver):
    with pytest.raises(QueryException) as e:
        queryview_driver.run("select column_does_not_exist from syndromic_events")
    # there should be no (line, col) pairs because query validation is disabled by default
    assert len(re.compile("\(\d+, \d+\)").findall(str(e.value))) == 0
    assert "Invalid column name" in str(e)


def test_query_error_response_with_query_validation(queryview_driver):
    with pytest.raises(QueryException) as e:
        queryview_driver.run(
            "select top 5 * from syndromic_events where", validate_query=True
        )
    # there should be 3 errors and thus 3 (line, col) pairs
    assert len(re.compile("\(\d+, \d+\)").findall(str(e.value))) == 3


def test_query_error_response_no_query_validation(queryview_driver):
    with pytest.raises(QueryException) as e:
        queryview_driver.run(
            "select top 5 * from syndromic_events where", validate_query=False
        )
    # there should be no (line, col) pairs because validation is disabled
    assert len(re.compile("\(\d+, \d+\)").findall(str(e.value))) == 0


def test_query_validation_ignores_warnings(queryview_driver):
    df = queryview_driver.run(
        """
        select top 5 * into #test from syndromic_events;
        select * from #test
    """,
        validate_query=True,
    )
    assert len(df) == 5


def test_query_invalid_validation_arg(queryview_driver):
    with pytest.raises(TypeError) as e:
        queryview_driver.run(
            "select top 5 * from syndromic_events where", validate_query="not a bool"
        )
    assert "Validate Query parameter must be of type bool" in str(e)


def test_query_timeout_response(queryview_driver):
    with pytest.raises(QueryException) as e:
        queryview_driver.run(
            """
            waitfor delay '00:00:07'
            select top 100 * from syndromic_events
        """,
            timeout=5,
        )
    assert "Query timeout expired" in str(e)


def test_query_invalid_timeout(queryview_driver):
    with pytest.raises(ValueError) as e:
        queryview_driver.run(
            """
            waitfor delay '00:00:07'
            select top 100 * from syndromic_events
        """,
            timeout=-7,
        )
    assert "Timeout value must be non-negative" in str(e)


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_query_no_key_connected(session):
    driver = QueryView.driver()
    driver.contract.DbConnectionId = None
    driver._key = None

    with pytest.raises(KeyRequiredException):
        driver.run("select top 100 from syndromic_events")


def test_empty_result(queryview_driver):
    df = queryview_driver.run(
        """
    select top 100 * 
    from syndromic_events 
    where zip_code = -2
    """
    )

    assert df.empty
    assert not df.columns.empty
    assert not df.dtypes.empty


def test_queryview_driver_uses_registered_key(default_health_key_object):
    default_health_key_object.register()
    driver = QueryView.driver()

    df = driver.run("select top 100 * from syndromic_events")
    assert len(df) == 100


def test_queryview_driver_with_timeout(default_health_key_object):
    default_health_key_object.register()
    driver = QueryView.driver(timeout=5)

    with pytest.raises(QueryException) as e:
        driver.run(
            """
            waitfor delay '00:00:07'
            select top 100 * from syndromic_events
        """
        )
    assert "Query timeout expired" in str(e)


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_queryview_run_with_id(
    session: Session, queryview_driver, default_health_key_object
):
    qv_contract = queryview_driver.contract  # driver sets up contract in conftest.py
    qv_contract.DbConnectionId = default_health_key_object.id
    qv_contract.QueryString = "select top 100 * from syndromic_events"
    qv_id = 0

    try:
        qv_id = session.queryview_service.Save(qv_contract).Id
        df = QueryView.run(qv_id)
        assert len(df) == 100
    finally:
        if qv_id != 0:
            session.queryview_service.Delete(qv_id)


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_queryview_run_with_id_and_inputs(
    session: Session, queryview_input_driver, default_health_key_object
):
    qv_contract = (
        queryview_input_driver.contract
    )  # driver sets up contract with inputs in conftest.py
    qv_contract.DbConnectionId = default_health_key_object.id
    qv_contract.QueryString = """
        select 
            top 50 * 
        from 
            syndromic_events 
        where 
            1=1 {{ageSearchInput}} {{genderSearchInput}} and race = {{raceLiteralInput}} 
            and red = {{redLiteralInput}} {{dateSearchInput}}
    """
    qv_id = 0

    try:
        qv_id = session.queryview_service.Save(qv_contract).Id
        qv_inputs = {
            "ageSearchInput": 60,
            "raceLiteralInput": "Asian",
            "genderSearchInput": ("M", "!="),
            "redLiteralInput": False,
            "dateSearchInput": ("2010-05-17", "="),
        }
        df = QueryView.run(qv_id, inputs=qv_inputs)
        assert len(df) <= 50
        assert all(df["race"] == "Asian")
        assert all(df["age"] > 60)
        assert all(df["gender"] == "F")
        assert not all(df["red"])
        assert all(df["visit_date"] == "2010-05-17")
    finally:
        if qv_id != 0:
            session.queryview_service.Delete(qv_id)


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_queryview_run_with_id_and_multichoice_inputs(
    session: Session, queryview_input_driver, default_health_key_object
):
    qv_contract = (
        queryview_input_driver.contract
    )  # driver sets up contract with inputs in conftest.py
    qv_contract.DbConnectionId = default_health_key_object.id
    qv_contract.QueryString = """
        select 
            top 50 * 
        from 
            syndromic_events 
        where 
            gender IN {{genderLiteralInput}} AND age IN {{ageLiteralInput}}
    """
    qv_id = 0

    try:
        qv_id = session.queryview_service.Save(qv_contract).Id
        qv_inputs = {
            "genderLiteralInput": [{"M", "U"}],
            "ageLiteralInput": [{33, 34, 45}],
        }
        df = QueryView.run(qv_id, inputs=qv_inputs)
        assert len(df) <= 50
        assert all(df["gender"].isin(["M", "U"]))
        assert all(df["age"].isin([33, 34, 45]))
    finally:
        if qv_id != 0:
            session.queryview_service.Delete(qv_id)


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_queryview_run_with_id_and_invalid_inputs_arg(
    session: Session, queryview_input_driver, default_health_key_object
):
    qv_contract = (
        queryview_input_driver.contract
    )  # driver sets up contract in conftest.py
    qv_contract.DbConnectionId = default_health_key_object.id
    qv_contract.QueryString = (
        "select top 50 * from syndromic_events where 1=1 {{genderSearchInput}}"
    )
    qv_id = 0

    try:
        qv_id = session.queryview_service.Save(qv_contract).Id
        with pytest.raises(QueryInputException):
            QueryView.run(
                qv_id, inputs=[("genderSearchInput", "M", "!=")]
            )  # only dicts should be allowed for now
    finally:
        if qv_id != 0:
            session.queryview_service.Delete(qv_id)


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_queryview_run_with_id_and_inputs_invalid_operator_error(
    session: Session, queryview_input_driver, default_health_key_object
):
    qv_contract = (
        queryview_input_driver.contract
    )  # driver sets up contract in conftest.py
    qv_contract.DbConnectionId = default_health_key_object.id
    qv_contract.QueryString = (
        "select top 50 * from syndromic_events where 1=1 {{genderSearchInput}}"
    )
    qv_id = 0

    try:
        qv_id = session.queryview_service.Save(qv_contract).Id
        with pytest.raises(QueryInputException):
            QueryView.run(qv_id, inputs={"genderSearchInput": ("M", ">>")})
    finally:
        if qv_id != 0:
            session.queryview_service.Delete(qv_id)


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_queryview_run_with_id_and_inputs_operator_disallowed(
    session: Session, queryview_input_driver, default_health_key_object
):
    qv_contract = (
        queryview_input_driver.contract
    )  # driver sets up contract in conftest.py
    qv_contract.DbConnectionId = default_health_key_object.id
    qv_contract.QueryString = (
        "select top 50 * from syndromic_events where 1=1 {{ageSearchInput}}"
    )
    qv_id = 0

    try:
        qv_id = session.queryview_service.Save(qv_contract).Id
        with pytest.raises(QueryInputException):
            QueryView.run(qv_id, inputs={"ageSearchInput": (100, "<=")})
    finally:
        if qv_id != 0:
            session.queryview_service.Delete(qv_id)


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_queryview_run_with_id_and_nonexistent_input(
    session: Session, queryview_input_driver, default_health_key_object
):
    qv_contract = (
        queryview_input_driver.contract
    )  # driver sets up contract in conftest.py
    qv_contract.DbConnectionId = default_health_key_object.id
    qv_contract.QueryString = (
        "select top 50 * from syndromic_events where 1=1 {{genderSearchInput}}"
    )
    qv_id = 0

    try:
        qv_id = session.queryview_service.Save(qv_contract).Id
        with pytest.raises(QueryInputException):
            QueryView.run(qv_id, inputs={"nonexistentInput": ("M", "<=")})
    finally:
        if qv_id != 0:
            session.queryview_service.Delete(qv_id)


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_queryview_run_with_id_and_invalid_input_value(
    session: Session, queryview_input_driver, default_health_key_object
):
    qv_contract = (
        queryview_input_driver.contract
    )  # driver sets up contract in conftest.py
    qv_contract.DbConnectionId = default_health_key_object.id
    qv_contract.QueryString = (
        "select top 50 * from syndromic_events where 1=1 {{genderSearchInput}}"
    )
    qv_id = 0

    try:
        qv_id = session.queryview_service.Save(qv_contract).Id
        with pytest.raises(QueryInputException):
            QueryView.run(
                qv_id, inputs={"genderSearchInput": ({"M": True}, "<=")}
            )  # something like a dict would be an invalid input value
    finally:
        if qv_id != 0:
            session.queryview_service.Delete(qv_id)


def test_queryview_driver_interactive(queryview_driver_interactive):
    result = queryview_driver_interactive.run(
        "select * from syndromic_events where age > 100"
    )

    assert isinstance(result, ITableResult)
    assert "<!-- DataTables -->" in result._repr_html_()


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_saved_queryview_interactive(
    session: Session, queryview_driver, default_health_key_object
):
    qv_contract = queryview_driver.contract  # driver sets up contract in conftest.py
    qv_contract.DbConnectionId = default_health_key_object.id
    qv_contract.QueryString = "select top 100 * from syndromic_events"
    qv_id = 0

    try:
        qv_id = session.queryview_service.Save(qv_contract).Id
        result = QueryView.run(qv_id, interactive=True)
        assert isinstance(result, ITableResult)
        assert "<!-- DataTables -->" in result._repr_html_()
    finally:
        if qv_id != 0:
            session.queryview_service.Delete(qv_id)


def test_queryview_driver_interactive_qv_error(queryview_driver_interactive):
    with pytest.raises(QueryException) as e:
        queryview_driver_interactive.run(
            "select!!!! * from syndromic_events where age > 100"
        )
    assert "Incorrect syntax" in str(e)


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_saved_queryview_interactive_qv_error(
    session: Session, queryview_driver, default_health_key_object
):
    qv_contract = queryview_driver.contract  # driver sets up contract in conftest.py
    qv_contract.DbConnectionId = default_health_key_object.id
    qv_contract.QueryString = "select top 100 *, FAKE_COL from syndromic_events"
    qv_id = 0

    try:
        qv_id = session.queryview_service.Save(qv_contract).Id
        with pytest.raises(QueryException) as e:
            QueryView.run(qv_id, interactive=True)
        assert "Invalid column name 'FAKE_COL'" in str(e)
    finally:
        if qv_id != 0:
            session.queryview_service.Delete(qv_id)
