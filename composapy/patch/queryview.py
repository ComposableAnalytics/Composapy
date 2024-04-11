import json

from CompAnalytics.Contracts.QueryView import QueryView
from CompAnalytics.Core import ContractSerializer

import json_fix  # used to patch json with fake magic method __json__


# patching json package using json-fix
# json-fix : https://pypi.org/project/json-fix/
def _json(self):
    return json.loads(ContractSerializer.Serialize(self))


QueryView.__json__ = _json
