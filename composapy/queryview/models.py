from typing import Dict, Any
import pandas as pd

from composapy.decorators import session_required
from composapy.session import get_session
from composapy.key.models import KeyObject, get_key_object
from composapy.patch.table import MAP_CS_TYPES_TO_PANDAS_TYPES

from CompAnalytics import Contracts


class QueryViewObject:
    """Wrapper for the QueryView.QueryView contract.

    .. highlight:: python
    .. code-block:: python

        from composapy.key.api import Key
        from composapy.queryview.api import QueryView

        key = Key.get(123456)  # KeyObject(id=123456)

        # create driver and connect...
        driver = QueryView.driver()  # QueryViewObject(name=some_name, key=None)
        driver.connect(key)

        # ...or use the key as method argument to automatically connect
        driver = QueryView.driver(key)  # QueryViewObject(name=some_name, key=some_key)

    """

    contract: Contracts.QueryView.QueryView

    def __init__(self, contract: Contracts.QueryView):
        self.contract = contract
        self._key = get_key_object(raise_exception=False)
        if self._key:
            self.contract.DbConnectionId = self._key.id

        properties = [
            item
            for item in vars(self.contract.__class__)
            if not item.startswith("_")
            and not item.startswith("get")
            and not item.startswith("set")
            and not item.startswith("Overloads")
            and item != "Inputs"
        ]
        for _property in properties:
            setattr(self, _property, getattr(self.contract, _property))

    @property
    def key(self) -> KeyObject:
        """Returns the connected KeyObject."""
        return self._key

    @property
    def connection_info(self) -> Dict[str, Any]:
        """Returns KeyObject attribute information."""
        return self._key.__dict__

    @property
    def name(self) -> str:
        """Returns the contract name."""
        return self.contract.Name

    def __repr__(self):
        return (
            f"QueryViewObject(name='{self.contract.Name if self.contract.Name else 'None'}', "
            f"key='{self._key.name if self._key else 'None'}')"
        )

    def connect(self, key: KeyObject) -> None:
        """Set new key and update contract DbConnectionId.

        .. highlight:: python
        .. code-block:: python

            from composapy.key.api import Key
            from composapy.queryview.api import QueryView

            key = Key.get(123456)  # KeyObject(id=123456)

            driver = QueryView.driver()  # QueryViewObject(name=some_name, key=None)
            driver.connect(key)
            print(driver)  # QueryViewObject(name=some_name, key=some_name)

        :param key: KeyObject retrieved with the Composable Key api
        """
        self._key = key
        self.contract.DbConnectionId = self._key.id

    @session_required
    def run(self, query: str) -> pd.DataFrame:
        """Run a query on the connected database, returning a Pandas DataFrame of the results.

        .. highlight:: python
        .. code-block:: python

            df = driver.run("select column_name_1, column_name_2 from my_table")

        :param query: The query string
        """
        if not self._key:
            raise KeyRequiredException(
                "Must first attach key by using method: connect(key_object)."
            )

        queryview_service = get_session().services["QueryViewService"]
        self.contract.QueryString = query

        qv_data_result = queryview_service.RunQueryDynamic(self.contract)

        if qv_data_result.Error is not None:
            raise QueryException(qv_data_result.Error)

        columns_definitions = qv_data_result.ColumnDefinitions
        column_names = []
        column_dtypes = {}

        for column_definition in columns_definitions:
            if not column_definition.Exclude:
                column_names.append(column_definition.Name)
                column_dtypes[column_definition.Name] = MAP_CS_TYPES_TO_PANDAS_TYPES[
                    column_definition.Type
                ]

        df = pd.DataFrame(qv_data_result.Data, columns=column_names)
        return df.astype(column_dtypes)


class QueryException(Exception):
    pass


class KeyRequiredException(Exception):
    pass
