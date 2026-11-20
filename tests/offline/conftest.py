import pytest

from composapy.key.models import KeyObject
from composapy.session import Session


@pytest.fixture(autouse=True)
def _no_registrations_carried_over():
    """The registered session and key are process-wide. pytest 6.2.5, which the 3.8 and 3.11 environments pin, runs the
    integration test files before this folder, and they leave a session and a key registered, so every offline test
    starts and ends with none."""
    Session.clear_registration()
    KeyObject.clear_registration()
    yield
    Session.clear_registration()
    KeyObject.clear_registration()
