"""Register a Key for the process, then save it to composapy.ini and read the saved configuration back."""

from composapy.key.api import Key
from composapy.key.models import get_key_object

key = Key.get(name=fixtures["key_name"])
attempt("before_registering", lambda: get_key_object(raise_exception=False))
record("register_returns", key.register())
record("registered_name", get_key_object().name)
record("registered_repr", repr(get_key_object()))
record("registered_is_the_same_id", get_key_object().id == key.id)

attempt("register_with_save", lambda: key.register(save=True))


def saved_key_options():
    from composapy.config import read_config

    _, config = read_config()
    return {
        section: sorted(config[section])
        for section in config.sections()
        if "key" in section.lower()
    }


attempt("saved_key_sections_and_option_names", saved_key_options)
attempt(
    "clear_registration",
    lambda: (key.clear_registration(), get_key_object(raise_exception=False))[1],
)
attempt("registered_after_clearing", lambda: get_key_object())
