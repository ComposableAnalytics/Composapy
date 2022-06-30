from typing import Dict

import System
from System import Object
from System.Collections.Generic import List, KeyValuePair
from CompAnalytics.Core import ContractSerializer
from CompAnalytics.Contracts import FileReference


class TypeNotSupportedError(Exception):
    pass


SUPPORTED_TYPES = (
    str,
    int,
    FileReference,
)


def is_string(python_object):
    return System.String(python_object)


def is_int(python_object):
    return System.Int32(python_object)


def is_none(python_object):
    return None


def is_file_ref(python_object):
    return python_object


marshall_actions = {
    str: is_string,
    int: is_int,
    None: is_none,
    FileReference: is_file_ref,
}


def serialize_return_values(return_values: Dict[str, any], output_path: str) -> None:
    clr_return_values = List[KeyValuePair[str, Object]]()
    for n, (k, v) in enumerate(return_values.items()):
        if v is not None and type(v) not in SUPPORTED_TYPES:
            raise TypeNotSupportedError(f"{{type(v)}} is not currently supported.")

        type_value = v if v is None else type(v)
        clr_value = marshall_actions[type_value](v)
        clr_return_values.Add(KeyValuePair[str, Object](k, clr_value))

    ContractSerializer.SerializeToFile(clr_return_values, output_path)
