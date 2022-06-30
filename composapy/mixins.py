class ObjectSetMixinException(Exception):
    pass


class NoneFoundError(ObjectSetMixinException):
    pass


class FoundMultipleError(ObjectSetMixinException):
    pass


class ObjectSetMixin:
    """Used for object model sets which require element navigation tree utilities."""

    _target = None

    def __len__(self):
        return len(self._target)

    def __getitem__(self, index):
        return self._target[index]

    def __iter__(self):
        return iter(self._target)

    def first(self):
        """Returns first module in self._target."""

        return next(iter(self._target))

    def first_with_name(self, name):
        """Matches by first in self._target with given name."""

        return next(item for item in self._target if item.name == name)

    def filter(self, **kwargs):
        """Filters based on a module field value, such as name.
        example: modules.filter(name=module_name)
        """

        return tuple(
            item
            for item in self._target
            if all(getattr(item, key) == val for key, val in kwargs.items())
        )

    def get(self, **kwargs):
        """Searches based on module field value, such as name. Throws exception if there is
        either more than one result or zero results."""

        results = tuple(
            item
            for item in self._target
            if all(getattr(item, key) == val for key, val in kwargs.items())
        )
        if len(results) == 0:
            raise NoneFoundError()
        elif len(results) > 1:
            raise FoundMultipleError()
        return results[0]
