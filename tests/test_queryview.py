from __future__ import annotations
import pytest
from typing import TYPE_CHECKING

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


def test_query_error_response(queryview_driver):
    with pytest.raises(QueryException):
        queryview_driver.run("select column_does_not_exist from syndromic_events")


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
            QueryView.run(qv_id, inputs={"genderSearchInput": ({"M"}, "<=")})
    finally:
        if qv_id != 0:
            session.queryview_service.Delete(qv_id)
