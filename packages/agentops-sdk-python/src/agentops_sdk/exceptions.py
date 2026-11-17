
class AgentOpsError(Exception):
    """Base exception for AgentOps SDK errors."""


class AgentOpsConfigurationError(AgentOpsError):
    """Raised when SDK configuration is invalid."""


class AgentOpsAuthenticationError(AgentOpsError):
    """Raised when AgentOps authentication fails."""


class AgentOpsTransportError(AgentOpsError):
    """Raised when an AgentOps API request fails."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class AgentOpsNotFoundError(AgentOpsTransportError):
    """Raised on HTTP 404 - a referenced agent, session or execution does not
    exist, or is outside the API key's authorized scope. Never retryable."""

    def __init__(self, message: str):
        super().__init__(message, retryable=False)


class AgentOpsConflictError(AgentOpsTransportError):
    """Raised on HTTP 409 - an idempotency or uniqueness conflict reported by
    the server. Never retryable: resubmitting the same request will not help."""

    def __init__(self, message: str):
        super().__init__(message, retryable=False)


class AgentOpsValidationError(AgentOpsTransportError):
    """Raised on HTTP 422 - the server rejected the request as invalid (e.g.
    self-contradictory resource references). Never retryable."""

    def __init__(self, message: str):
        super().__init__(message, retryable=False)


class AgentOpsShutdownError(AgentOpsError):
    """Raised when the SDK is used after shutdown."""
