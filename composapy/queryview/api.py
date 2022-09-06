from composapy.key.models import KeyObject
from composapy.queryview.models import QueryViewObject

from CompAnalytics.Contracts.QueryView import QueryView as QueryView_


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
