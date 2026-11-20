"""Switches IIS Windows Authentication for the application under test, the change WinAuthUtils makes."""

import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

SITE = "Default Web Site"
APPCMD = (
    Path(os.environ.get("windir", r"C:\Windows"))
    / "System32"
    / "inetsrv"
    / "appcmd.exe"
)
AUTHENTICATION = "/section:system.web/authentication"
WINDOWS_AUTHENTICATION = "/section:windowsAuthentication"
# Installed by the IIS Windows Authentication feature. Without it IIS accepts the setting and never asks for credentials.
WINDOWS_AUTH_MODULE = APPCMD.parent / "authsspi.dll"


class IisError(RuntimeError):
    pass


def virtual_path(application_uri):
    return urlparse(application_uri).path.rstrip("/")


def _appcmd(run, *args):
    try:
        result = run([str(APPCMD), *args], capture_output=True, text=True)
    except FileNotFoundError as error:
        raise IisError(
            f"appcmd.exe was not found at {APPCMD}; IIS and its management tools must be installed"
        ) from error
    if result.returncode != 0:
        raise IisError(
            f"appcmd {' '.join(args)} failed with exit code {result.returncode}: {(result.stdout + result.stderr).strip()}. "
            "The windows-auth tests change IIS, so run them from an elevated (administrator) terminal."
        )
    return result.stdout.strip()


def _read(run, target):
    mode = _appcmd(run, "list", "config", target, AUTHENTICATION, "/text:mode")
    enabled = _appcmd(
        run, "list", "config", target, WINDOWS_AUTHENTICATION, "/text:enabled"
    ).lower()
    if not re.fullmatch(r"[A-Za-z]+", mode) or enabled not in ("true", "false"):
        raise IisError(
            f"appcmd answered mode={mode!r}, enabled={enabled!r} for {target}; expected a word and true or false"
        )
    return mode, enabled


def _apply(run, target, mode, enabled):
    _appcmd(run, "set", "config", target, AUTHENTICATION, f"/mode:{mode}")
    _appcmd(
        run,
        "set",
        "config",
        target,
        WINDOWS_AUTHENTICATION,
        f"/enabled:{enabled}",
        "/commit:apphost",
    )


def _restore(run, target, mode, enabled):
    """Puts both settings back. If the mode cannot be restored the enabled setting is still tried, so a failure here never
    leaves Windows authentication switched on; the first failure is the one raised."""
    first_error = None
    try:
        _appcmd(run, "set", "config", target, AUTHENTICATION, f"/mode:{mode}")
    except Exception as error:
        first_error = error
    try:
        _appcmd(
            run,
            "set",
            "config",
            target,
            WINDOWS_AUTHENTICATION,
            f"/enabled:{enabled}",
            "/commit:apphost",
        )
    except Exception as error:
        first_error = first_error or error
    if first_error is not None:
        raise first_error


@contextmanager
def windows_auth_enabled(application_uri, environ=None, run=subprocess.run):
    environ = os.environ if environ is None else environ
    if environ.get(
        "JUPYTER_ENVIRONMENT_FLAG"
    ):  # the C# DataLab suites manage this setting
        yield
        return
    if not WINDOWS_AUTH_MODULE.exists():
        raise IisError(
            f"IIS Windows Authentication is not installed: {WINDOWS_AUTH_MODULE.name} is missing from "
            f"{WINDOWS_AUTH_MODULE.parent}. IIS accepts the setting without it but never asks for credentials, so every "
            "Windows login would fail. Install it from an elevated terminal with "
            "`Enable-WindowsOptionalFeature -Online -FeatureName IIS-WindowsAuthentication -All`."
        )
    target = SITE + virtual_path(application_uri)
    original = _read(run, target)
    try:
        _apply(run, target, "Windows", "true")
        yield
    finally:
        _restore(run, target, *original)
