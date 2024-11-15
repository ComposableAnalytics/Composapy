from __future__ import annotations
from typing import Dict, TYPE_CHECKING

from composapy import get_session, session_required
from composapy.interactive.itable import ITableResult
from composapy.key.models import KeyObject
from composapy.queryview.const import QV_ACCEPTABLE_OPERATORS, QV_INPUT_PRIMITIVE_TYPES
from composapy.queryview.models import (
    QueryViewObject,
    QueryViewPagedObject,
    QueryException,
    QueryInputException,
)

from CompAnalytics.Contracts.QueryView import QueryView as QueryView_

if TYPE_CHECKING:
    import pandas as pd


class QueryView:
    """A wrapper class for queryview operations."""

    @staticmethod
    def driver(
        key: KeyObject = None,
        timeout: int = None,
        validate_query: bool = False,
        interactive: bool = False,
    ) -> QueryViewObject:
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
        :param validate_query: boolean indicating whether to apply a pre-compilation step to validate SQL queries run with the driver. This often provides more informative error output but can be disabled for maximal query performance.
        :param interactive: when enabled, query results will be rendered as an interactive DataTable with server-side pagination.
        """
        if interactive:
            qv_object = QueryViewPagedObject(QueryView_(), timeout, validate_query)
        else:
            qv_object = QueryViewObject(QueryView_(), timeout, validate_query)

        if key:
            qv_object.connect(key)
        return qv_object

    @staticmethod
    @session_required
    def run(
        qv_id: int, inputs: Dict[str, any] = None, interactive: bool = False
    ) -> pd.DataFrame | ITableResult:
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
        :param interactive: when enabled, query results will be rendered as an interactive DataTable with pagination.
        """
        queryview_service = get_session().queryview_service
        qv_contract = queryview_service.Get(qv_id)

        if inputs is not None:
            if not isinstance(inputs, dict):
                raise QueryInputException(
                    f"Expected inputs argument to be a dictionary but got '{type(inputs)}' instead"
                )

            for name in inputs:
                if isinstance(inputs[name], (list, tuple)):
                    if len(inputs[name]) == 1:
                        value, operator = inputs[name][0], None
                    elif len(inputs[name]) == 2:
                        value, operator = inputs[name][0], inputs[name][1]
                    else:
                        raise QueryInputException(
                            f"Value-operator pair must have length 2 for input '{name}'. If you are trying to pass a multichoice input, please pass it as an iterable within an iterable, \
                            followed by an optional operator. Composapy expects an iterable to contain a value followed by an operator indicating a search input, and new support for multichoice \
                            involves writing the value as a set, list, or tuple within the encompassing iterable to maintain this structure."
                        )
                else:
                    value, operator = inputs[name], None

                value = QueryView._format_qv_value(value)

                if operator is not None and operator not in QV_ACCEPTABLE_OPERATORS:

                    raise QueryInputException(
                        f"Operator '{operator}' is not an acceptable option for input '{name}'. If you are trying to pass a multichoice input, please pass it as an iterable within an iterable, \
                            followed by an optional operator. Composapy expects an iterable to contain a value followed by an operator indicating a search input, and new support for multichoice \
                            involves writing the value as a set, list, or tuple within the encompassing iterable to maintain this structure."
                    )

                # Look for a matching literal input in qv_contract for this name
                match = False
                for lit in qv_contract.LiteralInputs:
                    if lit.DisplayName == name:
                        lit.Value = value
                        if isinstance(value, (set, list, tuple)):
                            lit.IsMultiChoice = True
                        match = True
                        break

                # If no literal input match was found, look for a search input
                if not match:
                    for srch in qv_contract.SearchInputs:
                        if srch.DisplayName == name:
                            srch.Value = value
                            if isinstance(value, (set, list, tuple)):
                                srch.IsMultiChoice = True
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

        if interactive:
            return QueryViewPagedObject(qv_contract, saved=True).run(
                qv_contract.QueryString.replace("\n", " ")
            )

        qv_result = queryview_service.RunQueryDynamic(qv_contract)

        if qv_result.Error is not None:
            raise QueryException(qv_result.Error)

        return QueryViewObject._qv_result_to_df(qv_result)

    @staticmethod
    def _format_qv_value(val: any):
        """Checks that the given QueryView input value is primitive or an iterable of primitives and converts it to a string or a comma-separated string."""
        if type(val) not in QV_INPUT_PRIMITIVE_TYPES:
            if isinstance(val, (list, tuple, set)):  # If it is multichoice
                flat_val = (
                    list(val) if isinstance(val, (list, tuple)) else val
                )  # remove duplicates
                for item in flat_val:
                    if type(item) not in QV_INPUT_PRIMITIVE_TYPES:
                        raise QueryInputException(
                            f"All elements in the input iterable must be of type int, bool, str, or float, not '{type(item)}'."
                        )
                    return (
                        "["
                        + ",".join(
                            (
                                f'"{str(item)}"'
                                if isinstance(item, str)
                                else (
                                    str(item).lower()
                                    if isinstance(item, bool)
                                    else str(item)
                                )
                            )
                            for item in flat_val
                        )
                        + "]"
                    )

            else:
                raise QueryInputException(
                    f"Iterable type must be of type list, tuple, or set, not'{type(val)}'."
                )

        if isinstance(val, bool):
            return str(val).lower()

        return str(val)
