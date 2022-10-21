import json

from CompAnalytics.Contracts import ExecutionHandle
from CompAnalytics.Core import ContractSerializer

import json_fix  # used to patch json with fake magic method __json__


# patching json package using json-fix
# json-fix : https://pypi.org/project/json-fix/
def _json(self):
    return json.loads(ContractSerializer.Serialize(self))


ExecutionHandle.__json__ = _json


# patching copy.deepycopy
# python docs : https://docs.python.org/3/library/copy.html#copy.deepcopy
def deep_copy(self, memo):
    """Only use for things which don't actually need to be copied."""
    return self


ExecutionHandle.__deepcopy__ = deep_copy


# monkey patching ExecutionHandle for pickling
# python docs : https://docs.python.org/3/library/pickle.html#object.__reduce_ex__
# composable docs : https://dev.composable.ai/api/CompAnalytics.Contracts.ExecutionHandle.html
def reduce_ex(self, protocol):
    """Called when using pickle.dumps(execution_handle_to_pickle)."""
    return (self.__class__, (ContractSerializer.Serialize(self),))


ExecutionHandle.__reduce_ex__ = reduce_ex


class ExecutionHandlePickleBehavior(ExecutionHandle):
    """This is used for changing the behavior of pickling/depickling for ExecutionHandle."""

    def __new__(self, *args, **kwargs):
        """Called when using pickle.loads(picked_table)."""
        return ContractSerializer.Deserialize[ExecutionHandle](args[0])
