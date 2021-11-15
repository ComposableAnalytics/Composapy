from ComposaPy.session import Session


class ComposableApi:
    session = None

    def __init__(self, session: Session):
        self.session = session
