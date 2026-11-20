from composapy._wire import codec
from composapy._wire.objects import ContractObject, register

TYPE = "ExecutionHandle:#CompAnalytics.Contracts"


class ExecutionHandle(ContractObject):

    def __init__(self, *args, **members):
        if len(args) == 1 and isinstance(args[0], str):
            super().__init__(
                codec.decode(args[0])
            )  # an old pickle hands us the JSON text
        else:
            super().__init__(
                *args, **members
            )  # the decoder hands us pairs; code hands us keywords
        if "__type" not in self:  # built by hand: put it in serializer order
            ordered = {
                "__type": TYPE,
                "AppId": self.get("AppId"),
                "HandleId": self.get("HandleId"),
                "Id": self.get("Id"),
            }
            self.clear()
            self.update(ordered)

    def __eq__(self, other):
        return isinstance(other, ExecutionHandle) and self.get("HandleId") == other.get(
            "HandleId"
        )

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.get("HandleId"))

    def __deepcopy__(self, memo):
        return self

    def __reduce__(self):
        return (self.__class__, (codec.encode(self),))


class ExecutionHandlePickleBehavior(ExecutionHandle):
    pass


register(TYPE, ExecutionHandle)
