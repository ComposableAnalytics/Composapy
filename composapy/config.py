from __future__ import annotations
from typing import Tuple, TYPE_CHECKING
import configparser
from dataclasses import dataclass
from pathlib import Path

from composapy.utils import get_config_path
from composapy.auth import AuthMode

if TYPE_CHECKING:
    from composapy.key.models import KeyObject
    from composapy.session import Session


class ConfigSession:
    uri: str
    auth_mode: AuthMode


@dataclass
class FormSession(ConfigSession):
    username: str
    password: str
    uri: str
    auth_mode: AuthMode = AuthMode.FORM


@dataclass
class TokenSession(ConfigSession):
    token: str
    uri: str
    auth_mode: AuthMode = AuthMode.TOKEN


@dataclass
class WindowsSession(ConfigSession):
    uri: str
    auth_mode: AuthMode = AuthMode.WINDOWS


def read_config_session() -> ConfigSession:
    """Returns the session saved in the config."""
    config_path, config = _read_config()

    if "session" not in config:
        raise SessionConfigDoesNotExist(
            "No saved configuration for session exists in composapy.ini."
        )

    if config["session"]["auth_mode"] == AuthMode.FORM.value:
        return FormSession(
            uri=config["session"]["uri"],
            username=config["session"]["username"],
            password=config["session"]["password"],
        )

    elif config["session"]["auth_mode"] == AuthMode.TOKEN.value:
        return TokenSession(
            uri=config["session"]["uri"], token=config["session"]["token"]
        )

    elif config["session"]["auth_mode"] == AuthMode.WINDOWS.value:
        return WindowsSession(uri=config["session"]["uri"])


def write_config_session(session: Session) -> None:
    """Updates configuration file with session."""
    config_path, config = _read_config()

    config["session"] = {
        "uri": session.uri,
        "auth_mode": session.auth_mode.value,
        "token": session._credentials if session.auth_mode == AuthMode.TOKEN else "",
        "username": session._credentials[0]
        if session.auth_mode == AuthMode.FORM
        else "",
        "password": session._credentials[1]
        if session.auth_mode == AuthMode.FORM
        else "",
    }

    _write_config(config_path, config)


def read_config_key_id() -> int:
    """Returns the key id saved in the config."""
    config_path, config = _read_config()

    if "key" not in config:
        raise KeyConfigDoesNotExist(
            "No saved configuration for session exists in composapy.ini."
        )

    return config["key"].getint("id")


def write_config_key(key_object: KeyObject) -> None:
    """Updates configuration file with key."""
    config_path, config = _read_config()

    config["key"] = {"id": key_object.id}

    _write_config(config_path, config)


def _read_config() -> Tuple[Path, configparser.ConfigParser]:
    config_path = get_config_path()
    config = configparser.ConfigParser()
    config.read(config_path)
    return config_path, config


def _write_config(config_path: Path, config: configparser.ConfigParser) -> None:
    with open(config_path, "w") as configfile:
        config.write(configfile)


class ConfigException(Exception):
    pass


class SessionConfigDoesNotExist(ConfigException):
    pass


class KeyConfigDoesNotExist(ConfigException):
    pass
