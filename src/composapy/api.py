from .session import Session


class ComposableApi:
    """Superclass that all api classes must inherit from."""

    session = None

    def __init__(self, session: Session):
        self.session = session
