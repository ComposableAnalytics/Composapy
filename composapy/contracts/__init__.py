# Register the classes
from composapy.contracts.execution_handle import (
    ExecutionHandle,
    ExecutionHandlePickleBehavior,
)
from composapy.contracts.table import (
    Table,
    TablePickleBehavior,
    to_table,
    TableColumn,
    TableColumnCollection,
)
from composapy.contracts.file_reference import (
    FileReference,
    CsvFileReference,
    ImageReference,
    KmlReference,
    KmzReference,
    StlReference,
    Mp3Reference,
    WavReference,
    VideoReference,
    AudioReference,
    FileReferencePickleBehavior,
)
from composapy.contracts.execution_context_options import ExecutionContextOptions
from composapy.contracts.execution_status import ExecutionStatus
from composapy.contracts.queryview import (
    LiteralInput,
    QueryView,
    SearchInput,
    ValidationOptions,
)
from composapy.contracts.serializer import ContractSerializer
