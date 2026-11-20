import json
from pathlib import Path

_OPERATIONS = None


def load_operations():
    global _OPERATIONS
    if _OPERATIONS is None:
        path = Path(__file__).resolve().parent.parent / "_wire" / "operations.json"
        _OPERATIONS = json.loads(path.read_text(encoding="utf-8"))
    return _OPERATIONS


class ServiceProxy:

    def __init__(self, client, name):
        self.client = client
        self.name = name
        self._ops = {op["name"]: op for op in load_operations()[name]}

    def __getattr__(self, method):

        def send_request(*args, **kwargs):
            chosen_op = self._ops.get(method)
            if chosen_op is None:
                raise AttributeError(
                    f"The operation {method} is not defined for {self.name}"
                )

            names = chosen_op["params"]
            if len(args) > len(names):
                raise TypeError(
                    f"{method}() takes {len(names)} arguments but {len(args)} were given"
                )
            params = dict(zip(names, args))

            content_type = kwargs.pop("_content_type", None)
            query = kwargs.pop("_query", None)
            for key, value in kwargs.items():
                if key not in names:
                    raise TypeError(f"{method}() got an unexpected argument '{key}'")
                if key in params:
                    raise TypeError(f"{method}() got multiple values for '{key}'")
                params[key] = value
            return self.client.send_request(
                self.name, chosen_op, params, _content_type=content_type, _query=query
            )

        if method.startswith("_"):
            raise AttributeError(method)
        return send_request
