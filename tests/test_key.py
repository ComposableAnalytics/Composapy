from __future__ import annotations
from typing import TYPE_CHECKING
import json

from composapy.key.api import Key
from composapy.key.models import get_key_object

from composapy.utils import get_config_path
from composapy.config import read_config_key_id

if TYPE_CHECKING:
    from CompAnalytics import Contracts
    from composapy.key.models import KeyObject


def test_get_key_with_name(property: Contracts.Property):
    key_object = Key.get(name=property.Name)

    assert key_object.name == property.Name
    assert key_object.id == property.Id

    property_json = json.loads(property.Value)
    assert getattr(key_object, "Host") == property_json["Host"]
    assert getattr(key_object, "Port") == property_json["Port"]
    assert getattr(key_object, "Username") == property_json["Username"]
    assert getattr(key_object, "Password") == property_json["Password"]


def test_get_key_with_id(property: Contracts.Property):
    key_object = Key.get(key_id=property.Id)

    assert key_object.name == property.Name
    assert key_object.id == property.Id

    property_json = json.loads(property.Value)
    assert getattr(key_object, "Host") == property_json["Host"]
    assert getattr(key_object, "Port") == property_json["Port"]
    assert getattr(key_object, "Username") == property_json["Username"]
    assert getattr(key_object, "Password") == property_json["Password"]


def test_search_key(property: Contracts.Property):
    key_objects = Key.search(property.Name)

    assert len(key_objects) == 1
    key_object = key_objects[0]

    assert key_object.name == property.Name
    assert key_object.id == property.Id

    property_json = json.loads(property.Value)
    assert getattr(key_object, "Host") == property_json["Host"]
    assert getattr(key_object, "Port") == property_json["Port"]
    assert getattr(key_object, "Username") == property_json["Username"]
    assert getattr(key_object, "Password") == property_json["Password"]


def test_register_key(default_health_key_object: KeyObject):
    default_health_key_object.register()

    assert default_health_key_object == get_key_object()


def test_register_key_save_true(default_health_key_object: KeyObject):
    config_path = get_config_path()
    config_path.unlink(missing_ok=True)  # ensure no file exists before test

    default_health_key_object.register(save=True)
    config_key_id = read_config_key_id()

    assert default_health_key_object.id == config_key_id
