from __future__ import annotations
from typing import Dict, TYPE_CHECKING

from composapy import get_session, session_required
from composapy.key.models import KeyObject
from composapy.queryview.const import QV_ACCEPTABLE_OPERATORS, QV_INPUT_PRIMITIVE_TYPES
from composapy.queryview.models import (
    QueryViewObject,
    QueryException,
    QueryInputException,
)

from CompAnalytics.Contracts.QueryView import QueryView as QueryView_

if TYPE_CHECKING:
    import pandas as pd


class QueryView:
    """A wrapper class for queryview operations."""

    @staticmethod
    def driver(key: KeyObject = None, timeout: int = None) -> QueryViewObject:
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
        :param timeout: optional integer timeout value (in seconds) for the query driver. This will apply to all queries executed with this driver unless an alternate timeout value is specified when calling the driver.run() method
        """
        qv_object = QueryViewObject(QueryView_(), timeout)
        if key:
            qv_object.connect(key)
        return qv_object

    @staticmethod
    @session_required
    def run(qv_id: int, inputs: Dict[str, any] = None) -> pd.DataFrame:
        """Run a saved QueryView resource, returning the results as a Pandas DataFrame. Will use
        the currently saved QueryView query and connection settings. Note, this will not use your
        currently registered key as the query connection settings.

        .. highlight:: python
        .. code-block:: python

            from composapy.queryview.api import QueryView

            df = QueryView.run(123456)

            # Or, if the QueryView has inputs, you can pass them in as an optional argument
            # Literal inputs should be a string-string key-value pair: "Display Name": "Value"
            # Filter inputs can be a string-string key-value pair or a string-tuple pair: "Display Name": ("Value", "Operator")
            df = QueryView.run(123456, inputs={"Display Name 1": "Value 1", "Display Name 2": ("Value 2", ">=")})

        :param qv_id: QueryView id, can be found in the url of your QueryView resource.
        :param inputs: Dictionary of filter/literal inputs to use for the query execution.
        """
        queryview_service = get_session().queryview_service
        qv_contract = queryview_service.Get(qv_id)

        if inputs is not None:
            if not isinstance(inputs, dict):
                raise QueryInputException(
                    f"Expected inputs argument to be a dictionary but got '{type(inputs)}' instead"
                )

            for name in inputs:
                # Unpack/validate input value or value-operator pair
                if type(inputs[name]) in (list, tuple):
                    if len(inputs[name]) != 2:
                        raise QueryInputException(
                            f"Value-operator pair must have length 2 for input '{name}'."
                        )
                    value, operator = inputs[name]
                else:
                    value, operator = inputs[name], None

                value = QueryView._format_qv_value(value)

                if operator is not None and operator not in QV_ACCEPTABLE_OPERATORS:
                    raise QueryInputException(
                        f"Operator '{operator}' is not an acceptable option for input '{name}'"
                    )

                # Look for a matching literal input in qv_contract for this name
                match = False
                for lit in qv_contract.LiteralInputs:
                    if lit.DisplayName == name:
                        lit.Value = value
                        match = True
                        break

                # If no literal input match was found, look for a search input
                if not match:
                    for srch in qv_contract.SearchInputs:
                        if srch.DisplayName == name:
                            srch.Value = value
                            if operator:
                                # Only update operator if the "allow operator changes" setting is enabled
                                # If the setting is disabled but the same default operator is passed in, no need to trigger an error
                                if (
                                    not srch.OperatorOptional
                                    and srch.DefaultOperator != operator
                                ):
                                    raise QueryInputException(
                                        f"Cannot use non-default operator for search input '{srch.DisplayName}'. To resolve this error, either omit the operator for this input or enable the 'Allow Operator Changes setting in the QueryView."
                                    )
                                srch.DefaultOperator = operator
                            match = True
                            break

                # If still no match was found, raise an exception
                if not match:
                    raise QueryInputException(
                        "No input found matching the display name '{name}'"
                    )

        qv_result = queryview_service.RunQueryDynamic(qv_contract)

        if qv_result.Error is not None:
            raise QueryException(qv_result.Error)

        return QueryViewObject._qv_result_to_df(qv_result)

    @staticmethod
    def _format_qv_value(val: any):
        """Checks that the given QueryView input value is primitive and converts it to a string."""
        if type(val) not in QV_INPUT_PRIMITIVE_TYPES:
            raise QueryInputException(
                f"Input value must be of type int, bool, str, or float, not '{type(val)}'. Support for multi-choice inputs will be added in a subsequent version of Composapy."
            )

        if isinstance(val, bool):
            return str(val).lower()

        return str(val)
