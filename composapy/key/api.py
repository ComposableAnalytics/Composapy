from typing import List

from composapy.decorators import session_required
from composapy.session import get_session
from composapy.key.models import KeyObject


class Key:
    """Key static wrapper for the PropertyService contract. It is used to
    service user-level operations on a service-level library.

    .. highlight:: python
    .. code-block:: python

        from composapy.key.api import Key

    """

    @staticmethod
    @session_required
    def get(key_id: int = None, name: str = None) -> KeyObject:
        """Used to retrieve a key available to the currently registered session;
        takes either a key_id or name, but not both.

        .. highlight:: python
        .. code-block:: python

            key_object = Key.get(key_id=123456)
            key_object = Key.get(name="fuzzy pandas database connection key")

        :param key_id: Composable key id
        :param name: Name of the key. Raises an error if no results or more than one result are
            found.
        """
        if key_id and name:
            raise InvalidArgumentsError(
                "Either id (key_id) or name is required, not both."
            )

        if not key_id and not name:
            raise InvalidArgumentsError("An id (key_id) or name is required.")

        property_service = get_session().property_service

        if key_id:
            return KeyObject(property_service.GetProperty(key_id))

        if name:
            results = property_service.SearchProperties(name, 0, 2).Results
            if len(results) > 1:
                raise FoundMultipleError()
            if len(results) == 0:
                raise NoneFoundError()

            return KeyObject(property_service.GetProperty(results[0].Id))

    @staticmethod
    @session_required
    def search(
        name: str, index_start: int = 0, number_results: int = 10
    ) -> List[KeyObject]:
        """Used to retrieve keys available to the user from the currently registered session.
        Each key result must be decoded, which is an expensive process. Limiting the number of
        results and skipping through paged results can reduce the search time. As an example, if
        there are 30 results, index_start is set to 9 and number_results set to 10, this will
        return results index 9 through 19.

        .. highlight:: python
        .. code-block:: python

            key_object = Key.search("common key name")
            key_object = Key.search("common key name", 10, 15)

        :param name: Name of the key.
        :param index_start: Starting index of the results to return.
        :param number_results: Number of results to return.
        """
        property_service = get_session().property_service

        results = property_service.SearchProperties(
            name, index_start, number_results
        ).Results
        return [
            KeyObject(property_service.GetProperty(result.Id)) for result in results
        ]


class KeyException(Exception):
    pass


class InvalidArgumentsError(KeyException):
    pass


class NoneFoundError(KeyException):
    pass


class FoundMultipleError(KeyException):
    pass
