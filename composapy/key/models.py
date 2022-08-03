import json

import CompAnalytics.Contracts


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

    contract: CompAnalytics.Contracts.Property

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
        return f"Key(name='{self.contract.Name}', type='{self.contract.DisplayType}')"
