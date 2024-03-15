from typing import Dict, Any
import pandas as pd

from composapy.decorators import session_required
from composapy.session import get_session
from composapy.key.models import KeyObject, get_key_object
from composapy.patch.table import MAP_CS_TYPES_TO_PANDAS_TYPES
from composapy.queryview.const import QV_BOOLEAN_VALUE_MAP

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

    def __init__(
        self, contract: Contracts.QueryView, timeout=None, validate_query=False
    ):
        self.contract = contract
        self._key = get_key_object(raise_exception=False)
        if self._key:
            self.contract.DbConnectionId = self._key.id

        if timeout is None:
            timeout = 10
        self.set_driver_timeout(timeout)

        QueryViewObject._validate_vq_value(validate_query)
        self.validate_query = validate_query

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

    @staticmethod
    def _validate_timeout_value(value):
        if not isinstance(value, int):
            raise TypeError(
                f"Timeout value must be of type integer, not '{type(value)}'"
            )
        if value < 0:
            raise ValueError("Timeout value must be non-negative.")

    @staticmethod
    def _validate_vq_value(value):
        if not isinstance(value, bool):
            raise TypeError(
                f"Validate Query parameter must be of type bool, not '{type(value)}'"
            )

    def get_driver_timeout(self):
        """Get the current QueryTimeout value for the query driver (in seconds)."""
        return self.contract.QueryTimeout

    def set_driver_timeout(self, timeout: int):
        """Set the QueryTimeout value for the query driver (in seconds)."""
        QueryViewObject._validate_timeout_value(timeout)
        self.contract.QueryTimeout = timeout

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
    def run(
        self, query: str, timeout: int = None, validate_query: bool = None
    ) -> pd.DataFrame:
        """Run a query on the connected database, returning a Pandas DataFrame of the results.

        .. highlight:: python
        .. code-block:: python

            df = driver.run("select column_name_1, column_name_2 from my_table")

        :param query: The query string
        :param timeout: If specified, this integer timeout (in seconds) will be used as the QueryTimeout value, overriding the default timeout and the timeout specified when the driver was created.
        :param validate_query: If specified, this boolean indicates whether to apply a pre-compilation step to validate SQL queries run with the driver, overriding the validation setting specified when the driver was created. This often provides more informative error output but can be disabled for maximal query performance.
        """
        if not self._key:
            raise KeyRequiredException(
                "Must first attach key by using method: connect(key_object)."
            )

        queryview_service = get_session().queryview_service
        self.contract.QueryString = query

        # query validation setting specified at runtime takes priority over driver-level setting
        if validate_query is not None:
            QueryViewObject._validate_vq_value(validate_query)
        else:
            validate_query = self.validate_query

        # optionally pre-compile query to provide better error output
        if validate_query:
            opts = Contracts.QueryView.ValidationOptions()
            result = queryview_service.CompileQuery(self.contract, opts)
            error_msgs = [
                f"{e.Message} ({e.Start.LineNumber}, {e.Start.ColumnNumber})"
                for e in result.Errors
                if not e.IsWarning
            ]
            if len(error_msgs) > 0:
                raise QueryException("\n".join(error_msgs))

        try:
            # if a timeout is supplied at runtime, override the timeout set when the driver was created
            old_timeout = self.get_driver_timeout()
            if timeout is not None:
                self.set_driver_timeout(timeout)

            qv_result = queryview_service.RunQueryDynamic(self.contract)
        finally:
            # restore the timeout to the previously set value after query execution or if the new value is malformed
            self.set_driver_timeout(old_timeout)

        if qv_result.Error is not None:
            raise QueryException(qv_result.Error)

        return QueryViewObject._qv_result_to_df(qv_result)

    @staticmethod
    def _qv_result_to_df(qv_result):
        columns_definitions = qv_result.ColumnDefinitions
        column_names = []
        column_dtypes = {}
        for column_definition in columns_definitions:
            if not column_definition.Exclude:
                column_names.append(column_definition.Name)
                column_dtypes[column_definition.Name] = MAP_CS_TYPES_TO_PANDAS_TYPES[
                    column_definition.Type
                ]
        df = pd.DataFrame(qv_result.Data, columns=column_names)

        # The queryview result can have "True" or "False" values in boolean columns
        # df.astype() will map both of these values to Python's True because they are "truthy" (non-empty strings)
        # To avoid data loss, we manually map these values to Python bools before calling df.astype()
        bool_columns = [col for col in column_dtypes if column_dtypes[col] == "boolean"]
        for col in bool_columns:
            df[col] = df[col].map(lambda x: pd.NA if not x else QV_BOOLEAN_VALUE_MAP[x])

        return df.astype(column_dtypes)


class QueryException(Exception):
    pass


class QueryInputException(Exception):
    pass


class KeyRequiredException(Exception):
    pass
