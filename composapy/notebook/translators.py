import papermill

from composapy.contracts.file_reference import FileReference
from composapy.contracts.table import Table
from composapy.contracts.execution_handle import ExecutionHandle
from composapy._wire import codec


# patching for papermill translators - defining custom parameter rendering logic for FileReference
# github docs : https://github.com/nteract/papermill/blob/main/papermill/translators.py
@classmethod
def translate_file_ref(cls, val):
    return cls.translate_raw_str(
        f"ContractSerializer.Deserialize[FileReference]({val!r})"
    )


papermill.translators.PythonTranslator.translate_file_ref = translate_file_ref


# patching for papermill translators - defining custom parameter rendering logic for Table
# github docs : https://github.com/nteract/papermill/blob/main/papermill/translators.py
@classmethod
def translate_table(cls, val):
    return cls.translate_raw_str(f"ContractSerializer.Deserialize[Table]({val!r})")


papermill.translators.PythonTranslator.translate_table = translate_table


# patching for papermill translators - defining custom parameter rendering logic for ExecutionHandle
# github docs : https://github.com/nteract/papermill/blob/main/papermill/translators.py
@classmethod
def translate_execution_handle(cls, val):
    return cls.translate_raw_str(
        f"ContractSerializer.Deserialize[ExecutionHandle]({val!r})\n"
        f"import os\n"
        f"os.environ['_execution_handle'] = {val!r}"
    )


papermill.translators.PythonTranslator.translate_execution_handle = (
    translate_execution_handle
)


@classmethod
def translate(cls, val):
    """Translate each of the standard json/yaml types to appropriate objects."""

    if val is None:
        return cls.translate_none(val)
    elif isinstance(val, FileReference):
        return cls.translate_file_ref(codec.encode(val))
    elif isinstance(val, Table):
        return cls.translate_table(codec.encode(val))
    elif isinstance(val, ExecutionHandle):
        return cls.translate_execution_handle(codec.encode(val))
    elif isinstance(val, str):
        return cls.translate_str(val)
    # Needs to be before integer checks
    elif isinstance(val, bool):
        return cls.translate_bool(val)
    elif isinstance(val, int):
        return cls.translate_int(val)
    elif isinstance(val, float):
        return cls.translate_float(val)
    elif isinstance(val, dict):
        return cls.translate_dict(val)
    elif isinstance(val, list):
        return cls.translate_list(val)
    # Use this generic translation as a last resort
    return cls.translate_escaped_str(val)


papermill.translators.Translator.translate = translate
