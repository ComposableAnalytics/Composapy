"""Offline tests for composapy.bindings, the small piece of the 0.13 module that is kept: a notebook that replaced one
service's binding with another's, to change how long the service may take, still runs and still has that effect.

The HTTP layer is a fake requests.Session, so nothing leaves the process.
"""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest
import requests

from composapy import bindings
from composapy._transport import client as client_module
from composapy.auth import AuthMode
from composapy.session import Session

URI = "http://example.test/CompApp/"

# The line a customer notebook has, as it is written there
NOTEBOOK_LINE = (
    "from composapy import bindings\n"
    "bindings._service_binding_configs['TableService'] = "
    "bindings._service_binding_configs['ApplicationService']\n"
)


class FakeResponse:
    status_code = 200
    content = b'{"d":null}'


class FakeHttp:
    """Stands in for requests.Session and records the keyword arguments of every request."""

    instances = []

    def __init__(self):
        self.headers = {}
        self.requests = []
        FakeHttp.instances.append(self)

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return FakeResponse()

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fake_http_and_a_copy_of_the_dictionary(monkeypatch):
    """Each test gets its own copy of the dictionary, so a notebook line run by one test is gone for the next."""
    monkeypatch.setattr(requests, "Session", FakeHttp)
    monkeypatch.setattr(FakeHttp, "instances", [])
    monkeypatch.setattr(
        bindings, "_service_binding_configs", dict(bindings._service_binding_configs)
    )


def session():
    return Session(auth_mode=AuthMode.TOKEN, credentials="token-for-tests", uri=URI)


def timeout_of_the_last_request():
    ((_, _, kwargs),) = FakeHttp.instances[-1].requests[-1:]
    return kwargs["timeout"]


# ----------------------------------------------------------------------------------------------
# The module and what it holds
# ----------------------------------------------------------------------------------------------


def test_the_module_can_be_imported_the_way_a_notebook_imports_it():
    from composapy import bindings as imported

    assert imported is importlib.import_module("composapy.bindings")


def test_importing_it_in_a_clean_interpreter_needs_nothing_else_of_the_old_module():
    # -I drops the current folder from sys.path, so the folder composapy is in is passed as an argument
    root = str(Path(bindings.__file__).resolve().parents[1])
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); from composapy import bindings; "
        "print(sorted(n for n in vars(bindings) if not n.startswith('__')))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, root], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "['DEFAULT_TIMEOUT', '_service_binding_configs']"


def test_the_default_timeouts_are_the_ones_the_application_and_query_view_services_always_had():
    assert bindings.DEFAULT_TIMEOUT == (60, 600)
    assert bindings._service_binding_configs == {
        "ApplicationService": (60, None),
        "QueryViewService": (60, None),
    }


@pytest.mark.parametrize(
    "service, expected",
    [
        ("ApplicationService", (60, None)),
        ("QueryViewService", (60, None)),
        ("TableService", (60, 600)),
        ("PropertyService", (60, 600)),
        ("NoSuchService", (60, 600)),
    ],
)
def test_each_service_gets_its_own_timeout_and_an_unlisted_one_gets_the_default(
    service, expected
):
    assert client_module._timeout(service) == expected


# ----------------------------------------------------------------------------------------------
# The notebook's line
# ----------------------------------------------------------------------------------------------


def test_the_notebook_line_runs_and_gives_the_table_service_the_application_services_timeout():
    exec(NOTEBOOK_LINE, {})

    assert client_module._timeout("TableService") == (60, None)
    assert bindings._service_binding_configs["TableService"] is (
        bindings._service_binding_configs["ApplicationService"]
    )


def test_the_notebook_line_changes_no_other_service():
    exec(NOTEBOOK_LINE, {})

    assert client_module._timeout("ApplicationService") == (60, None)
    assert client_module._timeout("QueryViewService") == (60, None)
    assert client_module._timeout("PropertyService") == (60, 600)
    assert client_module._timeout("FileUploadService") == (60, 600)


def test_a_request_to_the_table_service_is_sent_with_the_default_timeout_until_the_line_runs():
    session().table_service.GetTable(1, 0, 10)

    assert timeout_of_the_last_request() == (60, 600)


def test_a_request_to_the_table_service_is_sent_without_a_read_timeout_after_the_line_runs():
    exec(NOTEBOOK_LINE, {})

    session().table_service.GetTable(1, 0, 10)

    assert timeout_of_the_last_request() == (60, None)


def test_a_session_made_before_the_line_runs_follows_the_change():
    # A notebook makes its session in a later cell or an earlier one; either way the setting is read when a request is sent
    early = session()
    early.table_service.GetTable(1, 0, 10)
    assert timeout_of_the_last_request() == (60, 600)

    exec(NOTEBOOK_LINE, {})
    early.table_service.GetTable(1, 0, 10)

    assert timeout_of_the_last_request() == (60, None)


def test_a_request_to_another_service_keeps_its_timeout_after_the_line_runs():
    exec(NOTEBOOK_LINE, {})

    session().property_service.GetProperty(1)

    assert timeout_of_the_last_request() == (60, 600)


def test_a_timeout_set_to_a_pair_of_the_notebooks_own_is_used_as_it_is():
    bindings._service_binding_configs["TableService"] = (5, 30)

    session().table_service.GetTable(1, 0, 10)

    assert timeout_of_the_last_request() == (5, 30)


def test_the_application_service_is_still_sent_without_a_read_timeout():
    session().services["ApplicationService"].GetApplication(1)

    assert timeout_of_the_last_request() == (60, None)
