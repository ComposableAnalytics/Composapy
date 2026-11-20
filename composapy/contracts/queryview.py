from composapy._wire.objects import ContractObject, NetList


def PagingOptions():
    return ContractObject(
        [
            ("__type", "PagingOptions:#CompAnalytics.Contracts.QueryView"),
            ("AutoPaging", False),
            ("DefaultOrderClause", None),
            ("FullPaging", False),
            ("LimitPaging", False),
            ("PageLimit", 0),
            ("PageNum", 0),
        ]
    )


def ValidationOptions():
    return ContractObject(
        [
            ("__type", "ValidationOptions:#CompAnalytics.Contracts.QueryView"),
            ("IsCountQuery", False),
            ("IsTemplateQuery", False),
        ]
    )


def QueryView(**overrides):
    members = {  # base-class members first (QueryViewCore), then QueryView's own, each alphabetical
        "ColumnDefinitions": [],
        "ExportHyperLinks": False,
        "Id": None,
        "LiteralInputs": [],
        "Name": None,
        "OrderClause": [],
        "PagingOptions": PagingOptions(),
        "SearchInputs": [],
        "TimeZoneOffset": None,
        "AllowMultiExpansion": False,
        "AutoRun": True,
        "AutoRunOnInputChange": False,
        "CacheSrcAppResults": None,
        "CheckForSaveConflict": False,
        "ChildQueryViewConnections": [],
        "CountQueryString": None,
        "DbConnectionId": None,
        "DbConnectionName": None,
        "Description": None,
        "InfiniteScroll": False,
        "IsOwner": False,
        "LastHistoryId": None,
        "OutputType": "grid",
        "Permissions": None,
        "QueryString": None,
        "QueryTimeout": None,
        "QueryViewActions": [],
        "QueryViewLinks": [],
        "RunReuseTimeoutMS": None,
        "ShowNullAsWhitespace": False,
        "SrcAppId": None,
        "SrcAppName": None,
    }
    members.update(overrides)
    return _contract("QueryView", members)


def _contract(type_name, members):
    # A list is a NetList whether the server sent it or composapy built it, so a
    # script can Add to and Clear a driver's contract as it could under pythonnet
    return ContractObject(
        [("__type", f"{type_name}:#CompAnalytics.Contracts.QueryView")]
        + [
            (name, NetList(value) if isinstance(value, list) else value)
            for name, value in members.items()
        ]
    )


def _dynamic_input_members():
    return {
        "AcceptParentOverride": False,
        "ChoiceQuery": None,
        "DataType": None,
        "Default": "",
        "DisplayName": None,
        "Id": None,
        "IsHidden": False,
        "IsVertical": False,
        "IsVisibleAsChild": False,
        "Order": 0,
        "TemplateName": None,
        "Value": "",
    }


def LiteralInput(**overrides):
    members = _dynamic_input_members()
    members["IsMultiChoice"] = False
    members.update(overrides)
    return _contract("LiteralInput", members)


def SearchInput(**overrides):
    members = _dynamic_input_members()
    members.update(
        {  # SearchInput's own members, alphabetical
            "Column": None,
            "Custom": None,
            "DefaultOperator": None,
            "IsMultiChoice": False,
            "OperatorOptional": False,
        }
    )
    members.update(overrides)
    return _contract("SearchInput", members)
