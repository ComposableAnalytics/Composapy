"""Session: the registered one, its services, and constructing and registering sessions with wrong or missing settings."""

import contextlib
import io
import os

from composapy.auth import AuthMode
from composapy.session import Session, get_session

current = get_session()
record("uri", current.uri)
record("auth_mode", str(current.auth_mode))
record("auth_mode_value", current.auth_mode.value)
record("auth_mode_members", sorted(m.name for m in AuthMode))
attempt("services_are_the_41", lambda: sorted(current.services))
attempt("service_count", lambda: len(current.services))
for name in (
    "app_service",
    "file_upload_service",
    "property_service",
    "queryview_service",
    "table_service",
    "resource_manager",
):
    attempt(f"has.{name}", lambda n=name: getattr(current, n) is not None)
attempt(
    "resource_manager.AvailableServices",
    lambda: sorted(current.resource_manager.AvailableServices()),
)
attempt(
    "service_call_through_the_property", lambda: current.property_service.GetProperty(0)
)
attempt(
    "service_call_through_services",
    lambda: current.services["PropertyService"].GetProperty(0),
)
attempt("get_session_returns_the_same", lambda: get_session() is current)

captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    attempt("register_again", lambda: current.register())
record("register_message", captured.getvalue().strip())
attempt("close", lambda: current.close())
attempt("call_after_close", lambda: current.property_service.GetProperty(0))

token = os.environ["PARITY_TOKEN"]
attempt(
    "token_session_properties",
    lambda: (lambda s: [s.uri, str(s.auth_mode)])(
        Session(auth_mode=AuthMode.TOKEN, credentials=token)
    ),
)
attempt("token_without_credentials", lambda: Session(auth_mode=AuthMode.TOKEN))
attempt(
    "token_credentials_not_text",
    lambda: Session(auth_mode=AuthMode.TOKEN, credentials=5),
)
attempt("form_without_credentials", lambda: Session(auth_mode=AuthMode.FORM))
attempt(
    "form_credentials_not_a_pair",
    lambda: Session(auth_mode=AuthMode.FORM, credentials="user"),
)
attempt(
    "form_credentials_three_items",
    lambda: Session(auth_mode=AuthMode.FORM, credentials=("a", "b", "c")),
)
attempt(
    "windows_with_credentials",
    lambda: Session(auth_mode=AuthMode.WINDOWS, credentials="x"),
)
attempt("auth_mode_not_an_enum", lambda: Session(auth_mode="Token", credentials=token))
attempt(
    "explicit_uri_without_a_slash",
    lambda: Session(
        uri="http://localhost/CompApp", auth_mode=AuthMode.TOKEN, credentials=token
    ).uri,
)
attempt(
    "uri_not_text", lambda: Session(uri=5, auth_mode=AuthMode.TOKEN, credentials=token)
)


def without_application_uri():
    saved = os.environ.pop("APPLICATION_URI")
    try:
        return Session(auth_mode=AuthMode.TOKEN, credentials=token)
    finally:
        os.environ["APPLICATION_URI"] = saved


attempt("no_uri_configured", without_application_uri)

Session.clear_registration()
attempt("get_session_when_none", lambda: get_session())
attempt("get_session_when_none_quietly", lambda: get_session(raise_exception=False))
bad = Session(auth_mode=AuthMode.TOKEN, credentials="not a real token")
bad.register()
attempt("invalid_token_first_call", lambda: bad.property_service.GetProperty(0))
attempt(
    "invalid_token_through_the_api",
    lambda: __import__("composapy.dataflow.api", fromlist=["DataFlow"]).DataFlow.get(0),
)
Session.clear_registration()
wrong = Session(auth_mode=AuthMode.FORM, credentials=("nobody", "not the password"))
attempt("form_wrong_password_registers", lambda: wrong.register())
attempt("form_wrong_password_first_call", lambda: wrong.property_service.GetProperty(0))
