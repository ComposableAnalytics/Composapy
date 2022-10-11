import papermill
from six import string_types, integer_types

from CompAnalytics.Core import ContractSerializer
from CompAnalytics.Contracts.Tables import Table
from CompAnalytics.Contracts import FileReference, ExecutionHandle

# patching for papermill translators - defining custom parameter rendering logic for FileReference
# github docs : https://github.com/nteract/papermill/blob/main/papermill/translators.py
@classmethod
def translate_file_ref(cls, val):
    return cls.translate_raw_str(
        f"ContractSerializer.Deserialize[FileReference]('{val}')"
    )


papermill.translators.PythonTranslator.translate_file_ref = translate_file_ref


# patching for papermill translators - defining custom parameter rendering logic for Table
# github docs : https://github.com/nteract/papermill/blob/main/papermill/translators.py
@classmethod
def translate_table(cls, val):
    return cls.translate_raw_str(f"ContractSerializer.Deserialize[Table]('{val}')")


papermill.translators.PythonTranslator.translate_table = translate_table


# patching for papermill translators - defining custom parameter rendering logic for ExecutionHandle
# github docs : https://github.com/nteract/papermill/blob/main/papermill/translators.py
@classmethod
def translate_execution_handle(cls, val):
    return cls.translate_raw_str(
        f"ContractSerializer.Deserialize[ExecutionHandle]('{val}')"
    )


papermill.translators.PythonTranslator.translate_execution_handle = (
    translate_execution_handle
)


@classmethod
def translate(cls, val):
    """Translate each of the standard json/yaml types to appropriate objects."""

    if val is None:
        return cls.translate_none(val)
    elif isinstance(val, string_types):
        return cls.translate_str(val)
    # Needs to be before integer checks
    elif isinstance(val, bool):
        return cls.translate_bool(val)
    elif isinstance(val, integer_types):
        return cls.translate_int(val)
    elif isinstance(val, float):
        return cls.translate_float(val)
    elif isinstance(val, dict):
        return cls.translate_dict(val)
    elif isinstance(val, list):
        return cls.translate_list(val)
    elif isinstance(val, FileReference):
        return cls.translate_file_ref(ContractSerializer.Serialize(val))
    elif isinstance(val, Table):
        return cls.translate_table(ContractSerializer.Serialize(val))
    elif isinstance(val, ExecutionHandle):
        return cls.translate_execution_handle(ContractSerializer.Serialize(val))
    # Use this generic translation as a last resort
    return cls.translate_escaped_str(val)


papermill.translators.Translator.translate = translate
