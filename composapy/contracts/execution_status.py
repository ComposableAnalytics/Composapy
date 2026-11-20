from enum import IntEnum


class ExecutionStatus(IntEnum):
    Created = 0
    Running = 1
    Canceling = 2
    Success = 3
    Error = 4
    Canceled = 5
    Abandoned = 6
    CompletedWithError = 7
