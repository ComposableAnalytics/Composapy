import importlib.util
import requests
import re
import site
import sys
from pathlib import Path
from composapy._wire.codec import decode, encode, unwrap, parse_fault
from composapy.exceptions import (
    AuthenticationError,
    ServiceFault,
    InvalidAuthModeAction,
    CONNECTION_ERROR_MESSAGE,
)
from composapy.auth import AuthMode
from composapy import bindings


class ServiceClient:
    def __init__(self, uri, auth_mode, credentials):
        self.session = requests.Session()
        self.uri = uri
        self._login_failed = False

        if auth_mode == AuthMode.TOKEN:
            self.session.headers["Authorization"] = credentials
        elif auth_mode == AuthMode.FORM:
            self._form_login(*credentials)
        elif auth_mode == AuthMode.WINDOWS:
            self._windows_login()

    def send_request(
        self, service, operation, args, *, _content_type=None, _query=None
    ):
        if self._login_failed:
            raise AuthenticationError(
                "Login failed: the login page did not issue an .ASPXAUTH cookie. Check account credentials."
            )

        names = operation["params"]
        path = operation["uri"] or "/" + operation["name"]
        url = f"{self.uri}Services/{service}.svc{path}"

        r = None
        if operation["request"] == "raw":
            if len(args) != 1:
                raise TypeError(f"{operation['name']} takes one raw body")
            body = next(iter(args.values()))
            if isinstance(body, str):
                body = body.encode("utf-8")
            headers = {"Content-Type": _content_type or "application/octet-stream"}
            r = self._request(
                operation["verb"],
                url,
                data=body,
                headers=headers,
                params=_query,
                timeout=_timeout(service),
            )
        elif operation["verb"] == "POST":
            body = encode(args)
            r = self._request(
                "POST",
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                timeout=_timeout(service),
            )
        elif operation["verb"] == "GET":
            get_query = {name: encode(value) for name, value in args.items()}
            r = self._request("GET", url, params=get_query, timeout=_timeout(service))
        else:
            raise ValueError(
                f"The operation {operation['verb']} is not supported for {operation['name']}"
            )

        if operation["response"] == "raw" and r.status_code < 400:
            return r.content
        text = r.content.decode("utf-8-sig")
        return self._handle_response(r.status_code, text)

    def _request(self, method, url, **kwargs):
        try:
            return self.session.request(method, url, **kwargs)
        except requests.ConnectionError:
            raise ConnectionError(CONNECTION_ERROR_MESSAGE) from None

    def _handle_response(self, status_code, text):
        try:
            value = decode(text)
        except ValueError:
            raise ServiceFault(
                f"HTTP {status_code}: {text[:200]}", status_code=status_code
            ) from None
        if status_code == 401:
            raise AuthenticationError(parse_fault(value)["Message"])
        elif status_code >= 400:
            fault = parse_fault(value)
            raise ServiceFault(
                fault["Message"],
                fault["ExceptionType"],
                fault["StackTrace"],
                status_code,
            )
        return unwrap(value)

    def _login(self, page, fields):
        url = f"{self.uri}Account/{page}"
        for attempt in range(5):
            try:
                response = self.session.get(url, timeout=(60, 60))
                break
            except requests.ConnectionError:
                if attempt == 4:
                    raise ConnectionError(CONNECTION_ERROR_MESSAGE) from None
        form = {
            "__VIEWSTATE": _hidden(response.text, "__VIEWSTATE"),
            "__EVENTVALIDATION": _hidden(response.text, "__EVENTVALIDATION"),
            **fields,
        }
        self.session.post(url, data=form, allow_redirects=False, timeout=(60, 60))
        self._login_failed = ".ASPXAUTH" not in self.session.cookies

    def _form_login(self, username, password):
        self._login(
            "FormLogin.aspx",
            {
                "ctl00$MainContent$LoginUser$UserName": username,
                "ctl00$MainContent$LoginUser$Password": password,
                "ctl00$MainContent$LoginUser$LoginButton": "Login Button",
            },
        )

    def _windows_login(self):
        if sys.platform != "win32":
            raise InvalidAuthModeAction("Windows authentication requires Windows.")
        self.session.auth = _negotiate_auth()()
        self._login("WinLogin.aspx", {"ctl00$MainContent$LoginButton": "Log In"})

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def _negotiate_auth():
    """HttpNegotiateAuth from requests-negotiate-sspi, which needs pywin32."""
    try:
        from requests_negotiate_sspi import HttpNegotiateAuth
    except ImportError as error:
        if not _apply_pywin32_pth():
            raise _negotiate_import_error(error) from error
        try:
            from requests_negotiate_sspi import HttpNegotiateAuth
        except ImportError as retry_error:
            raise _negotiate_import_error(retry_error) from retry_error
    return HttpNegotiateAuth


def _negotiate_import_error(error):
    return InvalidAuthModeAction(
        "Windows authentication requires the requests-negotiate-sspi package, "
        f"which could not be imported: {error}"
    )


def _apply_pywin32_pth():
    # Reads it from the folder that holds requests_negotiate_sspi. Returns whether there was a file to read.
    spec = importlib.util.find_spec("requests_negotiate_sspi")
    if spec is None or not spec.origin:
        return False
    site_packages = Path(spec.origin).resolve().parent.parent
    if not (site_packages / "pywin32.pth").is_file():
        return False
    site.addpackage(str(site_packages), "pywin32.pth", None)
    return True


def _hidden(html, name):
    tag = re.search(r'<input[^>]*name="%s"[^>]*>' % re.escape(name), html)
    value = re.search(r'value="([^"]*)"', tag.group(0)) if tag else None
    if not value:
        raise AuthenticationError(f"Could not read {name} from the login page.")
    return value.group(1)


def _timeout(service):
    # Read on every request, so a change made to composapy.bindings after the session was made still applies
    return bindings._service_binding_configs.get(service, bindings.DEFAULT_TIMEOUT)
