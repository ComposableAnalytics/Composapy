"""Importing requests-negotiate-sspi for a Windows login, in a virtual environment that reaches the shared packages through
a plain path entry (a DataLab's does), where Python never reads the shared folder's pywin32.pth.
"""

import sys

import pytest

from composapy._transport.client import _negotiate_auth
from composapy.exceptions import InvalidAuthModeAction

PACKAGE = "requests_negotiate_sspi"
DEPENDENCY = "fake_pywintypes"


@pytest.fixture
def shared_site_packages(tmp_path, monkeypatch):
    """A folder with a requests_negotiate_sspi that needs fake_pywintypes, which sits in a subfolder only a .pth names."""
    folder = tmp_path / "site-packages"
    (folder / PACKAGE).mkdir(parents=True)
    (folder / PACKAGE / "__init__.py").write_text(
        f"import {DEPENDENCY}\nclass HttpNegotiateAuth:\n    pass\n", encoding="utf-8"
    )
    (folder / "win32" / "lib").mkdir(parents=True)
    (folder / "win32" / "lib" / f"{DEPENDENCY}.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(
        str(folder)
    )  # a plain path entry: its .pth files are not read
    for name in (PACKAGE, DEPENDENCY):
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield folder
    for name in (PACKAGE, DEPENDENCY):
        sys.modules.pop(name, None)


def test_pywin32_pth_beside_the_package_is_read_when_the_import_fails(
    shared_site_packages,
):
    (shared_site_packages / "pywin32.pth").write_text(
        "# the pywin32 file\nwin32\nwin32\\lib\n", encoding="utf-8"
    )

    auth = _negotiate_auth()

    assert auth.__name__ == "HttpNegotiateAuth"
    assert str(shared_site_packages / "win32" / "lib") in sys.path


def test_a_failed_import_with_no_pywin32_pth_names_the_cause(shared_site_packages):
    with pytest.raises(InvalidAuthModeAction) as raised:
        _negotiate_auth()

    assert "requests-negotiate-sspi" in str(raised.value)
    assert f"No module named '{DEPENDENCY}'" in str(raised.value)
    assert isinstance(raised.value.__cause__, ImportError)


def test_a_pywin32_pth_that_does_not_help_still_names_the_cause(shared_site_packages):
    (shared_site_packages / "pywin32.pth").write_text("nowhere\n", encoding="utf-8")

    with pytest.raises(InvalidAuthModeAction, match=f"No module named '{DEPENDENCY}'"):
        _negotiate_auth()


def test_a_package_that_is_not_installed_is_reported(monkeypatch):
    for name in (PACKAGE,):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(
        sys.modules, PACKAGE, None
    )  # makes `import` raise ImportError, as a missing package does

    with pytest.raises(InvalidAuthModeAction, match="could not be imported"):
        _negotiate_auth()
