CONNECTION_ERROR_MESSAGE = (
    "Unable to connect to URI. Common issues include incorrect URI scheme "
    "(http or https) or a typo in your URI. Please verify that you are using "
    "the correct scheme for your server."
)


class SessionException(Exception):
    pass


class AuthenticationError(Exception):
    pass


class ServiceFault(Exception):
    def __init__(
        self, message, exception_type=None, stack_trace=None, status_code=None
    ):
        super().__init__(message)
        self.ExceptionType = exception_type
        self.StackTrace = stack_trace
        self.status_code = status_code


class UriNotConfiguredError(SessionException):
    pass


class InvalidTokenConfigError(SessionException):
    pass


class InvalidFormConfigError(SessionException):
    pass


class InvalidWindowsConfigError(SessionException):
    pass


class SessionRegistrationException(SessionException):
    pass


class InvalidAuthModeAction(SessionException):
    pass
