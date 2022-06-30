from composapy.session import (
    Session,
    get_session,
)


class ComposableApi:
    """Superclass that all api classes must inherit from."""

    @property
    def session(self) -> Session:
        return get_session()
