from composapy._wire.objects import ContractObject


def ExecutionContextOptions(**overrides):
    members = {
        "AvoidSavingRuns": False,
        "ClientHubId": None,
        "Debug": False,
        "DepthFirstExecution": False,
        "DirectoryOrgType": None,
        "EnvironmentId": None,
        "PreviousRunId": None,
        "ResumeApp": False,
    }
    members.update(overrides)
    return ContractObject(
        [("__type", "ExecutionContextOptions:#CompAnalytics.Contracts")]
        + sorted(members.items())
    )
