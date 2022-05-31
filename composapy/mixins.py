from typing import Optional
from pathlib import Path
import pandas as pd
import requests

from composapy.session import Session, SessionException
from composapy.utils import urljoin

import System
from CompAnalytics import Contracts
from CompAnalytics.Utils import StandardPaths


class ObjectSetMixinException(Exception):
    pass


class NoneFoundError(ObjectSetMixinException):
    pass


class FoundMultipleError(ObjectSetMixinException):
    pass


class ObjectSetMixin:
    """Used for object model sets which require element navigation tree utilities."""

    _target = None

    def __len__(self):
        return len(self._target)

    def __getitem__(self, index):
        return self._target[index]

    def __iter__(self):
        return iter(self._target)

    def first(self):
        """Returns first module in self._target."""
        return next(iter(self._target))

    def first_with_name(self, name):
        """Matches by first in self._target with given name."""
        return next(item for item in self._target if item.name == name)

    def filter(self, **kwargs):
        """Filters based on a module field value, such as name.
        example: modules.filter(name=module_name)
        """
        return tuple(
            item
            for item in self._target
            if all(getattr(item, key) == val for key, val in kwargs.items())
        )

    def get(self, **kwargs):
        """Searches based on module field value, such as name. Throws exception if there is
        either more than one result or zero results."""
        results = tuple(
            item
            for item in self._target
            if all(getattr(item, key) == val for key, val in kwargs.items())
        )
        if len(results) == 0:
            raise NoneFoundError()
        elif len(results) > 1:
            raise FoundMultipleError()
        return results[0]


class PandasMixin:
    MAP_CS_TYPES_TO_PANDAS_TYPES = {
        "System.String": "object",
        "System.Int64": "Int64",
        "System.Int32": "Int64",
        "System.Int16": "Int64",
        "System.Double": "float64",
        "System.Decimal": "float64",
        "System.Single": "float64",
        "System.Boolean": "bool",
        "System.Guid": "object",
    }
    MAP_STRING_TYPES_TO_PANDAS_TYPES = {
        "CHAR": "object",
        "INTEGER": "int64",
        "INT": "int64",
        "BIGINT": "int64",
        "INT64": "int64",
        "UNSIGNED BIG INT": "int64",
        "VARCHAR": "object",
        "STRING": "object",
        "TEXT": "object",
        "FLOAT": "float64",
        "DOUBLE": "float64",
        "REAL": "float64",
        "BOOLEAN": "bool",
        "DATETIME": "datetime64",
        "DATETIMEOFFSET": "datetime64",
        "BLOB": "object",
        "OBJECT": "object",
        "GUID": "object",
    }

    session: Session
    contract: Contracts

    def to_pandas(self):
        if isinstance(self.contract.ValueObj, Contracts.Tables.Table):
            return self.convert_table_to_dataframe(self.contract.ValueObj)

    def convert_table_to_dataframe(self, table) -> Optional[pd.DataFrame]:
        if not self.session:
            return

        table_results = self.session.table_service.GetResultFromTable(
            table, 0, 0x7FFFFFFF
        )
        headers = table_results.Headers
        results = table_results.Results
        df = pd.DataFrame(results, columns=headers)

        dtypes_dict = self._make_pandas_dtypes_dict(table.Columns)
        for key in dtypes_dict.keys():
            if dtypes_dict[key] == "float64":
                df[key] = df[key].apply(lambda x: System.Decimal.ToDouble(x))

        return df.astype(dtypes_dict)

    def _make_pandas_dtypes_dict(self, table_columns):
        dtypes_dict = dict()
        for key in table_columns.Dictionary.Keys:
            column = table_columns.Dictionary[key]
            dtypes_dict[column.Name] = self.MAP_STRING_TYPES_TO_PANDAS_TYPES[
                column.Type
            ]
        return dtypes_dict

    def _make_pandas_dtypes_from_list_of_column_defs(self, list_of_column_defs):
        dtypes_dict = dict()
        for column_def in list_of_column_defs:
            dtypes_dict[column_def.Name] = self.MAP_CS_TYPES_TO_PANDAS_TYPES[
                column_def.Type
            ]
        return dtypes_dict


class SessionKwargsRequiredError(SessionException, ObjectSetMixinException):
    pass


class SessionObjectMixin:
    """For classes that require a session to function."""

    session: Session

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session")
        if not self.session:
            raise SessionKwargsRequiredError(
                "Must include Session in **kwargs when using the SessionObjectMixin."
            )
        super().__init__(*args, **kwargs)


class FileReferenceException(Exception):
    pass


class SessionPropertyRequiredError(FileReferenceException):
    pass


class ContractPropertyRequiredError(FileReferenceException):
    pass


class InvalidOperationError(FileReferenceException):
    pass


class FileReferenceMixin:
    """For use in managing classes with underlying contract type FileReference."""

    session: Session
    contract: Contracts

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.session:
            raise SessionPropertyRequiredError(
                "Must include session property for FileReferenceMixin."
            )
        if not self.contract:
            raise ContractPropertyRequiredError(
                "Must include contract property for FileReferenceMixin."
            )

    def to_file(self, save_dir: Path, file_name: str = None) -> Contracts.FileReference:
        """Downloads a run file by calling module.result.to_file().

        Parameters:
        (Path) save_dir: the directory to save the downloaded file to
        (str) file_name:
            The name of the newly saved file (default is None). If None is provided,
            uses the original filename from URI.
        """
        if not isinstance(self.contract.ValueObj, Contracts.FileReference):
            raise InvalidOperationError(
                f"{self.contract.Name} is not a file reference."
            )

        file_ref_uri = str(self.contract.ValueObj.Uri)
        file_ref_relative_uri = self._parse_uri(file_ref_uri)

        if not file_name:
            file_name = file_ref_uri[file_ref_uri.rindex("/") :].strip("/")

        url = urljoin(self.session.uri, file_ref_relative_uri)
        response = requests.get(url, headers={"Authorization": self.session.api_token})

        Path.mkdir(save_dir, parents=True, exist_ok=True)
        file_path = save_dir.joinpath(file_name)
        with open(file_path, "w+b") as _local_file:
            _local_file.write(response.content)

        self.contract.ValueObj = Contracts.FileReference.Create[
            self.contract.ValueObj.GetType()
        ](str(file_path), StandardPaths.CreateSiteRelativePath(System.Uri(url)))

        return self.contract.ValueObj

    def _parse_uri(self, file_ref_uri):
        return "/".join(list(filter(None, file_ref_uri.split("/")))[1:])
