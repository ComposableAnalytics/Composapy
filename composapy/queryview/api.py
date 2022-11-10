from __future__ import annotations
from typing import TYPE_CHECKING

from composapy import get_session, session_required
from composapy.key.models import KeyObject
from composapy.queryview.models import QueryViewObject, QueryException

from CompAnalytics.Contracts.QueryView import QueryView as QueryView_

if TYPE_CHECKING:
    import pandas as pd


class QueryView:
    """A wrapper class for queryview operations."""

    @staticmethod
    def driver(key: KeyObject = None) -> QueryViewObject:
        """Retrieve a queryview driver object, key is optional argument, but will need to call
        connect with key as argument to run a query.

        .. highlight:: python
        .. code-block:: python

            from composapy.key.api import Key
            from composapy.queryview.api import QueryView

            key = Key.get(123456)  # KeyObject(id=123456)

            # Create driver and connect...
            driver = QueryView.driver()  # QueryViewObject(name=some_name, key=None)
            driver.connect(key)

            # ... or use the key as method argument to automatically connect.
            driver = QueryView.driver(key)  # QueryViewObject(name=some_name, key=some_key)

            # If you already have a KeyObject registered, there is no need to pass in the key
            # or call connect with it; the driver will be created with a registered key by default.

        :param key: KeyObject retrieved with the Composable Key api
        """
        qv_object = QueryViewObject(QueryView_())
        if key:
            qv_object.connect(key)
        return qv_object

    @staticmethod
    @session_required
    def run(qv_id: int) -> pd.DataFrame:
        """Run a saved QueryView resource, returning the results as a Pandas DataFrame. Will use
        the currently saved QueryView query and connection settings. Note, this will not use your
        currently registered key as the query connection settings.

        .. highlight:: python
        .. code-block:: python

            from composapy.queryview.api import QueryView

            df = QueryView.run(123456)

        :param qv_id: QueryView id, can be found in the url of your QueryView resource.
        """
        queryview_service = get_session().queryview_service
        qv_contract = queryview_service.Get(qv_id)
        qv_result = queryview_service.RunQueryDynamic(qv_contract)

        if qv_result.Error is not None:
            raise QueryException(qv_result.Error)

        return QueryViewObject._qv_result_to_df(qv_result)
