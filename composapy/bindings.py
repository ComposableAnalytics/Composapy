"""Kept so a notebook written for 0.13 that changes how long a service may take still runs.

0.13 had a WCF binding for each service, and a notebook could replace one service's binding with another's
(`bindings._service_binding_configs['TableService'] = bindings._service_binding_configs['ApplicationService']`) to lift its
time limit. A request now has two timeouts, in seconds: how long to wait to connect and how long to wait for the reply.
This dictionary holds them as a (connect, read) pair for each service, where None means no limit. A service that is not in
it gets DEFAULT_TIMEOUT. It is a private name, as it always was, and nothing else of the old module is kept.
"""

DEFAULT_TIMEOUT = (60, 600)

_service_binding_configs = {
    "ApplicationService": (60, None),
    "QueryViewService": (60, None),
}
