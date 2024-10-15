import functools

from composapy.session import (
    SessionRegistrationException,
    get_session,
    handle_connection_exception,
)


def session_required(function):
    @functools.wraps(function)
    def inner(*args, **kwargs):
        try:
            get_session()
            result = function(*args, **kwargs)
        except SessionRegistrationException:
            raise SessionRequiredError(
                f"{function.__name__} requires an active, registered session to be called. "
                f"Please register a session by creating a session object and calling it's "
                f"register() method."
            )
        except Exception as e:
            handle_connection_exception(e)
            raise
        return result

    return inner


class SessionRequiredError(SessionRegistrationException):
    pass
