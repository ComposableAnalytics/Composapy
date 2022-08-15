import pytest

from composapy.queryview.models import QueryException, KeyRequiredException
from composapy.queryview.api import QueryView


def test_query_health_db(queryview_driver):
    df = queryview_driver.run("select top 100 * from syndromic_events")

    assert len(df) == 100


def test_query_error_response(queryview_driver):
    with pytest.raises(QueryException):
        queryview_driver.run("select column_does_not_exist from syndromic_events")


@pytest.mark.parametrize("session", ["Form"], indirect=True)
def test_query_no_key_connected(session):
    driver = QueryView.driver()
    with pytest.raises(KeyRequiredException):
        driver.run("select top 100 from syndromic_events")
