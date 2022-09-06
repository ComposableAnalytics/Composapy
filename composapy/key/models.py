from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import json

from composapy import config

if TYPE_CHECKING:
    from CompAnalytics import Contracts


class KeyObject:
    """KeyObject is a wrapper with a custom load strategy for the Composable Property contract.
    The key attributes are dynamically constructed based on key type retrieved.

    .. highlight:: python
    .. code-block:: python

            from composapy.key.api import Key

            key_object = Key.get(123456)
            print(key_object)
            # Key(name='us3r db connection key', type='SqlConnectionSettings')
            print(key_object.__dict__)
            # {'contract': <CompAnalytics.Contracts.Property object at 0x000001CE10E18A40>,
            #  'Password': 'pa55w0rd',
            #  'ConnectionParameters': [],
            #  'Database': 'TestDb',
            #  'Host': '.',
            #  'Port': None,
            #  'UseMultipleActiveResultSets': None,
            #  'Username': 'us3r'}

            key_object = Key.get(654321)
            print(key_object)
            # Key(name='us3r login credentials', type='Credential')
            print(key_object.__dict__)
            # {'contract': <CompAnalytics.Contracts.Property object at 0x000001CE65B37300>,
            #  'Password': 'pa55w0rd',
            #  'UserName': 'Us3rNam3'}

    """

    contract: Contracts.Property

    @property
    def name(self) -> str:
        """Returns the contract member, Name."""
        return self.contract.Name

    @property
    def type(self) -> str:
        """Returns the contract member, DisplayType."""
        return self.contract.DisplayType

    @property
    def id(self) -> int:
        """Returns the contract member, Id."""
        return self.contract.Id

    def __init__(self, contract):
        self.contract = contract

        if self.contract.Value:
            for key, value in json.loads(self.contract.Value).items():
                setattr(self, key, value)

    def __repr__(self):
        return f"KeyObject(name='{self.contract.Name}', type='{self.contract.DisplayType}')"

    @classmethod
    def clear_registration(cls) -> None:
        """Used to unregister the currently registered KeyObject.

        .. highlight:: python
        .. code-block:: python

            KeyObject.clear_registration()
        """
        singleton = _KeyObjectSingleton()
        singleton.key_object = None

    def register(self, save=False) -> None:
        """Used to register a class instance of KeyObject that is used implicitly across the
        kernel. Only one KeyObject can registered at a time.

        .. highlight:: python
        .. code-block:: python

            key_object = KeyObject(123456)
            key_object.register(save=True)

        :param save: If true, saves configuration in local composapy.ini file. Default is false.
        """
        singleton = _KeyObjectSingleton()
        singleton.key_object = self

        if save:
            config.write_config_key(self)


def get_key_object(raise_exception=True) -> Optional[KeyObject]:
    """Used to get the current registered KeyObject.

    .. highlight:: python
    .. code-block:: python

        from composapy.key.api import get_key_object
        KeyObject(123456).register()
        key_object = get_key_object()  # can use this anywhere on running kernel

    :return: the currently registered key object
    """
    singleton = _KeyObjectSingleton()
    if singleton.key_object is None:
        if raise_exception:
            raise KeyObjectRegistrationException("No key object currently registered.")
        return None
    return singleton.key_object


class _KeyObjectSingleton:
    key_object = None

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance


class KeyObjectException(Exception):
    pass


class KeyObjectRegistrationException(KeyObjectException):
    pass
