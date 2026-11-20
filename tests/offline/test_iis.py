"""Offline tests for tests/iis.py: switching IIS Windows Authentication around the windows-auth tox environment.

A fake appcmd.exe holds the two settings and records every call, so these tests change nothing in IIS. The real
commands need an elevated terminal; the fake only checks that the right ones are issued and that IIS is put back.
"""

from types import SimpleNamespace

import pytest

from tests import iis

URI = "http://localhost/CompApp/"
TARGET = "Default Web Site/CompApp"


@pytest.fixture(autouse=True)
def _windows_authentication_is_installed(tmp_path, monkeypatch):
    """The real check looks for IIS's authsspi.dll, which this machine may not have; the tests state it either way."""
    module = tmp_path / "authsspi.dll"
    module.write_bytes(b"")
    monkeypatch.setattr(iis, "WINDOWS_AUTH_MODULE", module)
    return module


class FakeAppcmd:
    """Answers `list config` from its state, applies `set config` to it, and records every call."""

    def __init__(self, mode="Forms", enabled="false", fail_when=None, list_output=None):
        self.state = {"mode": mode, "enabled": enabled}
        self.calls, self.kwargs = [], []
        self.fail_when = fail_when  # a word; any call containing it fails
        self.list_output = list_output or {}

    def __call__(self, args, **kwargs):
        self.calls.append([str(a) for a in args])
        self.kwargs.append(kwargs)
        words = " ".join(str(a) for a in args)
        if self.fail_when and self.fail_when in words:
            return SimpleNamespace(
                returncode=5,
                stdout="",
                stderr="Cannot read configuration file due to insufficient permissions",
            )
        if args[1] == "list":
            attribute = "mode" if "system.web/authentication" in words else "enabled"
            return SimpleNamespace(
                returncode=0,
                stdout=self.list_output.get(attribute, self.state[attribute] + "\r\n"),
                stderr="",
            )
        if args[1] == "set":
            for a in args:
                if str(a).startswith("/mode:"):
                    self.state["mode"] = str(a)[len("/mode:") :]
                if str(a).startswith("/enabled:"):
                    self.state["enabled"] = str(a)[len("/enabled:") :]
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected appcmd call: {args}")

    def commands(self):
        return [call[1:] for call in self.calls]  # without the path of appcmd.exe


# ----------------------------------------------------------------------------------------------
# The virtual path
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("http://localhost/CompApp/", "/CompApp"),
        ("http://localhost/CompApp", "/CompApp"),
        ("https://host.example.test:8443/a/b/", "/a/b"),
        ("http://localhost/", ""),
        ("http://localhost", ""),
    ],
)
def test_the_virtual_path_is_the_applications_path_without_a_trailing_slash(
    uri, expected
):
    assert iis.virtual_path(uri) == expected


# ----------------------------------------------------------------------------------------------
# What is changed, and what is put back
# ----------------------------------------------------------------------------------------------


def test_windows_authentication_is_on_inside_the_block_and_back_as_found_after_it():
    fake = FakeAppcmd(mode="Forms", enabled="false")
    with iis.windows_auth_enabled(URI, environ={}, run=fake):
        assert fake.state == {"mode": "Windows", "enabled": "true"}
    assert fake.state == {"mode": "Forms", "enabled": "false"}


def test_what_was_there_is_restored_even_when_it_was_not_forms_and_false():
    fake = FakeAppcmd(mode="Windows", enabled="true")
    with iis.windows_auth_enabled(URI, environ={}, run=fake):
        pass
    assert fake.state == {"mode": "Windows", "enabled": "true"}
    fake = FakeAppcmd(mode="None", enabled="true")
    with iis.windows_auth_enabled(URI, environ={}, run=fake):
        pass
    assert fake.state == {"mode": "None", "enabled": "true"}


def test_the_exact_commands_are_issued_in_order():
    fake = FakeAppcmd(mode="Forms", enabled="false")
    with iis.windows_auth_enabled(URI, environ={}, run=fake):
        pass
    assert fake.commands() == [
        ["list", "config", TARGET, "/section:system.web/authentication", "/text:mode"],
        ["list", "config", TARGET, "/section:windowsAuthentication", "/text:enabled"],
        [
            "set",
            "config",
            TARGET,
            "/section:system.web/authentication",
            "/mode:Windows",
        ],
        [
            "set",
            "config",
            TARGET,
            "/section:windowsAuthentication",
            "/enabled:true",
            "/commit:apphost",
        ],
        ["set", "config", TARGET, "/section:system.web/authentication", "/mode:Forms"],
        [
            "set",
            "config",
            TARGET,
            "/section:windowsAuthentication",
            "/enabled:false",
            "/commit:apphost",
        ],
    ]


def test_the_site_root_is_used_when_the_application_has_no_path():
    fake = FakeAppcmd()
    with iis.windows_auth_enabled("http://localhost/", environ={}, run=fake):
        pass
    assert all(call[2] == "Default Web Site" for call in fake.commands())


def test_appcmd_is_run_without_a_shell_from_its_own_folder_path():
    fake = FakeAppcmd()
    with iis.windows_auth_enabled(URI, environ={}, run=fake):
        pass
    assert all(
        call[0].lower().endswith("appcmd.exe") and "inetsrv" in call[0].lower()
        for call in fake.calls
    )
    assert not any(kwargs.get("shell") for kwargs in fake.kwargs)
    assert all(
        kwargs.get("capture_output") and kwargs.get("text") for kwargs in fake.kwargs
    )


@pytest.mark.parametrize("text", ["false\r\n", "false", " False \n", "FALSE"])
def test_the_enabled_value_is_read_whatever_its_case_and_spacing(text):
    fake = FakeAppcmd(list_output={"enabled": text})
    with iis.windows_auth_enabled(URI, environ={}, run=fake):
        pass
    assert fake.state["enabled"] == "false"


# ----------------------------------------------------------------------------------------------
# Failures
# ----------------------------------------------------------------------------------------------


def test_iis_is_restored_and_the_error_propagates_when_the_tests_fail():
    fake = FakeAppcmd(mode="Forms", enabled="false")
    with pytest.raises(AssertionError, match="the test failed"):
        with iis.windows_auth_enabled(URI, environ={}, run=fake):
            assert fake.state["enabled"] == "true"
            raise AssertionError("the test failed")
    assert fake.state == {"mode": "Forms", "enabled": "false"}


def test_a_failure_while_enabling_still_restores_what_was_changed():
    fake = FakeAppcmd(mode="Forms", enabled="false", fail_when="/enabled:true")
    with pytest.raises(iis.IisError):
        with iis.windows_auth_enabled(URI, environ={}, run=fake):
            pytest.fail("the block must not run")
    assert fake.state["mode"] == "Forms"  # the first change was undone


def test_nothing_is_changed_when_the_current_settings_cannot_be_read():
    fake = FakeAppcmd(fail_when="list")
    with pytest.raises(iis.IisError) as error:
        with iis.windows_auth_enabled(URI, environ={}, run=fake):
            pytest.fail("the block must not run")
    assert not any(call[1] == "set" for call in fake.calls)
    message = str(error.value)
    assert "insufficient permissions" in message and "administrator" in message.lower()


@pytest.mark.parametrize("output", ["", "maybe", "Forms Windows"])
def test_an_unreadable_answer_is_an_error_and_changes_nothing(output):
    fake = FakeAppcmd(list_output={"enabled": output})
    with pytest.raises(iis.IisError):
        with iis.windows_auth_enabled(URI, environ={}, run=fake):
            pytest.fail("the block must not run")
    assert not any(call[1] == "set" for call in fake.calls)


def test_a_missing_appcmd_says_so():
    def missing(args, **kwargs):
        raise FileNotFoundError(args[0])

    with pytest.raises(iis.IisError, match="appcmd"):
        with iis.windows_auth_enabled(URI, environ={}, run=missing):
            pytest.fail("the block must not run")


# ----------------------------------------------------------------------------------------------
# The C# suites manage this setting themselves
# ----------------------------------------------------------------------------------------------


def test_nothing_is_touched_when_the_csharp_suites_manage_the_setting():
    fake = FakeAppcmd()
    ran = []
    with iis.windows_auth_enabled(
        URI, environ={"JUPYTER_ENVIRONMENT_FLAG": "1"}, run=fake
    ):
        ran.append(True)
    assert ran == [True] and fake.calls == []


def test_an_empty_flag_does_not_count_as_set():
    fake = FakeAppcmd()
    with iis.windows_auth_enabled(
        URI, environ={"JUPYTER_ENVIRONMENT_FLAG": ""}, run=fake
    ):
        pass
    assert fake.calls != []


# ----------------------------------------------------------------------------------------------
# IIS without the Windows Authentication feature
# ----------------------------------------------------------------------------------------------


def test_a_machine_without_the_windows_authentication_feature_is_refused_before_anything_changes(
    _windows_authentication_is_installed,
):
    _windows_authentication_is_installed.unlink()
    fake = FakeAppcmd()
    with pytest.raises(iis.IisError) as error:
        with iis.windows_auth_enabled(URI, environ={}, run=fake):
            pytest.fail("the block must not run")
    assert fake.calls == []  # not even a read
    message = str(error.value)
    assert (
        "authsspi.dll" in message
        and "IIS-WindowsAuthentication" in message
        and "Enable-WindowsOptionalFeature" in message
    )


def test_the_missing_feature_does_not_matter_when_the_csharp_suites_manage_the_setting(
    _windows_authentication_is_installed,
):
    _windows_authentication_is_installed.unlink()
    fake = FakeAppcmd()
    ran = []
    with iis.windows_auth_enabled(
        URI, environ={"JUPYTER_ENVIRONMENT_FLAG": "1"}, run=fake
    ):
        ran.append(True)
    assert ran == [True] and fake.calls == []


def test_the_real_module_path_is_next_to_appcmd():
    import importlib.util

    spec = importlib.util.spec_from_file_location("iis_unpatched", iis.__file__)
    unpatched = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(
        unpatched
    )  # a copy, so the fixture's patch and iis.IisError stay as they are
    assert unpatched.WINDOWS_AUTH_MODULE == unpatched.APPCMD.parent / "authsspi.dll"


# ----------------------------------------------------------------------------------------------
# A restore that fails, and a mode that cannot be read
# ----------------------------------------------------------------------------------------------


def test_pinned_a_failing_restore_replaces_the_error_of_the_tests_and_keeps_it_as_the_context():
    # Pinned, needs a decision: the caller sees the IisError, not the failure of the tests; Python chains the failure as
    # __context__, so the traceback prints both
    fake = FakeAppcmd(mode="Forms", enabled="false", fail_when="/mode:Forms")
    with pytest.raises(iis.IisError, match="administrator") as error:
        with iis.windows_auth_enabled(URI, environ={}, run=fake):
            raise AssertionError("the test failed")
    assert isinstance(error.value.__context__, AssertionError)
    assert "the test failed" in str(error.value.__context__)


def test_a_failing_restore_after_tests_that_passed_is_raised_not_swallowed():
    fake = FakeAppcmd(mode="Forms", enabled="false", fail_when="/mode:Forms")
    with pytest.raises(iis.IisError, match="exit code 5"):
        with iis.windows_auth_enabled(URI, environ={}, run=fake):
            pass


def test_a_failing_mode_restore_does_not_stop_the_enabled_setting_being_restored():
    fake = FakeAppcmd(mode="Forms", enabled="false", fail_when="/mode:Forms")
    with pytest.raises(iis.IisError):
        with iis.windows_auth_enabled(URI, environ={}, run=fake):
            pass
    assert fake.state["enabled"] == "false"


def test_a_failing_enabled_restore_has_restored_the_mode_before_it():
    fake = FakeAppcmd(mode="Forms", enabled="false", fail_when="/enabled:false")
    with pytest.raises(iis.IisError):
        with iis.windows_auth_enabled(URI, environ={}, run=fake):
            pass
    assert fake.state == {"mode": "Forms", "enabled": "true"}


@pytest.mark.parametrize(
    "output",
    [
        "",
        "Forms Windows",
        "mode=Forms",
        "Forms!",
        "Forms2",
        "Forms\r\nWindows",
        "(none)",
    ],
)
def test_an_unreadable_mode_answer_is_an_error_that_shows_both_answers_and_changes_nothing(
    output,
):
    fake = FakeAppcmd(list_output={"mode": output})
    with pytest.raises(iis.IisError, match="appcmd answered mode=") as error:
        with iis.windows_auth_enabled(URI, environ={}, run=fake):
            pytest.fail("the block must not run")
    assert repr(output.strip()) in str(error.value) and TARGET in str(error.value)
    assert not any(call[1] == "set" for call in fake.calls)


@pytest.mark.parametrize("mode", ["Passport", "None", "forms", "WINDOWS"])
def test_any_one_word_mode_is_put_back_as_it_was_read(mode):
    fake = FakeAppcmd(mode=mode, enabled="true")
    with iis.windows_auth_enabled(URI, environ={}, run=fake):
        assert fake.state["mode"] == "Windows"
    assert fake.state == {"mode": mode, "enabled": "true"}


def test_a_mode_answer_with_spaces_around_it_is_read_as_the_word():
    fake = FakeAppcmd(list_output={"mode": "  Forms \r\n\r\n"})
    with iis.windows_auth_enabled(URI, environ={}, run=fake):
        pass
    assert fake.state["mode"] == "Forms"
