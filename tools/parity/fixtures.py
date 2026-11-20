"""Create, and afterwards remove, the instance-side objects the corpus scripts read: a SQL Key and saved QueryViews.

Run by run_parity.py under the candidate environment, once before either variant runs, so both variants see the same
objects. create() returns a dict of names and ids, which the runner hands to scripts as `fixtures`. The Key is the local
health database the integration tests use (a self-signed certificate, hence TrustServerCertificate).
"""

import json

from composapy._wire.objects import ContractObject
from composapy.key.api import Key
from composapy.queryview.api import QueryView

SQL_TYPE = (
    "CompAnalytics.Extension.Sql.SqlConnectionSettings, CompAnalytics.Extension.Sql, Version=1.0.0.0, "
    "Culture=neutral, PublicKeyToken=792cfbd70dcd13a9"
)
KEY_NAME = "ParityHealthKey"  # no hyphen and no "not": the Key search syntax treats both as operators


def _sql_key_property(name):
    settings = {
        "Password": "c0mpanalytics!",
        "ConnectionParameters": [{"Key": "TrustServerCertificate", "Value": "yes"}],
        "Database": "Health",
        "Host": ".",
        "Port": None,
        "Username": "CompAnalyticsPublicUser",
        "UseMultipleActiveResultSets": None,
    }
    return ContractObject(
        [
            ("__type", "Property:#CompAnalytics.Contracts"),
            ("AssemblyQualifiedType", SQL_TYPE),
            ("DisplayType", "SqlConnectionSettings"),
            ("DisplayTypeName", "Database Connection Settings"),
            ("Name", name),
            ("Value", json.dumps(settings)),
            ("EnvironmentValues", []),
        ]
    )


def _input(kind, **members):
    base = {
        "AcceptParentOverride": False,
        "ChoiceQuery": None,
        "DataType": None,
        "Default": "",
        "DisplayName": None,
        "Id": None,
        "IsHidden": False,
        "IsMultiChoice": False,
        "IsVertical": False,
        "IsVisibleAsChild": False,
        "Order": 0,
        "TemplateName": None,
        "Value": "",
    }
    if kind == "SearchInput":
        base.update(
            {
                "Column": None,
                "Custom": None,
                "DefaultOperator": None,
                "OperatorOptional": False,
            }
        )
    base.update(members)
    return ContractObject(
        [("__type", f"{kind}:#CompAnalytics.Contracts.QueryView")]
        + sorted(base.items())
    )


def _add_inputs(contract):
    literals = [
        _input(
            "LiteralInput",
            DisplayName="raceLiteralInput",
            TemplateName="raceLiteralInput",
            DataType="String",
            Default="White",
        ),
        _input(
            "LiteralInput",
            DisplayName="redLiteralInput",
            TemplateName="redLiteralInput",
            DataType="Boolean",
            Default="true",
        ),
        _input(
            "LiteralInput",
            DisplayName="genderLiteralInput",
            TemplateName="genderLiteralInput",
            DataType="String",
            IsMultiChoice=True,
            ChoiceQuery="SELECT DISTINCT gender FROM syndromic_events",
        ),
        _input(
            "LiteralInput",
            DisplayName="ageLiteralInput",
            TemplateName="ageLiteralInput",
            DataType="Number",
            IsMultiChoice=True,
            ChoiceQuery="SELECT DISTINCT age FROM syndromic_events",
        ),
    ]
    searches = [
        _input(
            "SearchInput",
            DisplayName="ageSearchInput",
            TemplateName="ageSearchInput",
            DataType="Number",
            Column="age",
            Default="50",
            DefaultOperator=">",
        ),
        _input(
            "SearchInput",
            DisplayName="genderSearchInput",
            TemplateName="genderSearchInput",
            DataType="String",
            Column="gender",
            Default="M",
            DefaultOperator="=",
            OperatorOptional=True,
        ),
        _input(
            "SearchInput",
            DisplayName="dateSearchInput",
            TemplateName="dateSearchInput",
            DataType="Date",
            Column="visit_date",
            DefaultOperator="<",
            OperatorOptional=True,
        ),
    ]
    contract.LiteralInputs.extend(literals)
    contract.SearchInputs.extend(searches)


QUERY_VIEWS = {
    "qv_simple": ("select top 100 * from syndromic_events", False),
    "qv_error": ("select top 100 *, FAKE_COL from syndromic_events", False),
    "qv_inputs": (
        """select top 50 * from syndromic_events where 1=1 {{ageSearchInput}} {{genderSearchInput}} and race = {{raceLiteralInput}}
                  and red = {{redLiteralInput}} {{dateSearchInput}}""",
        True,
    ),
    "qv_multichoice": (
        "select top 50 * from syndromic_events where gender IN {{genderLiteralInput}} AND age IN {{ageLiteralInput}}",
        True,
    ),
    "qv_gender": (
        "select top 50 * from syndromic_events where 1=1 {{genderSearchInput}}",
        True,
    ),
    "qv_age": (
        "select top 50 * from syndromic_events where 1=1 {{ageSearchInput}}",
        True,
    ),
}


def create(session):
    properties = session.property_service
    saved = properties.SaveProperty(_sql_key_property(KEY_NAME))
    key = Key.get(saved.Id)
    fixtures = {"key_name": KEY_NAME, "key_id": saved.Id, "queryview_ids": {}}
    for name, (query, with_inputs) in QUERY_VIEWS.items():
        driver = QueryView.driver(key)
        contract = driver.contract
        contract.DbConnectionId = key.id
        contract.QueryString = query
        if with_inputs:
            _add_inputs(contract)
        fixtures["queryview_ids"][name] = session.queryview_service.Save(contract).Id
    return fixtures


def delete(session, fixtures):
    for qv_id in fixtures.get("queryview_ids", {}).values():
        try:
            session.queryview_service.Delete(qv_id)
        except Exception as error:  # best effort: report and keep cleaning up
            print(f"could not delete QueryView {qv_id}: {error}")
    if fixtures.get("key_id"):
        try:
            session.property_service.DeleteProperty(fixtures["key_id"])
        except Exception as error:
            print(f"could not delete Key {fixtures['key_id']}: {error}")
