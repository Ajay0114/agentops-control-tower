
class AgentOpsError(Exception):
    """Base exception for AgentOps SDK errors."""


class AgentOpsConfigurationError(AgentOpsError):
    """Raised when SDK configuration is invalid."""


class AgentOpsAuthenticationError(AgentOpsError):
    """Raised when AgentOps authentication fails."""


class AgentOpsTransportError(AgentOpsError):
    """Raised when telemetry delivery fails."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class AgentOpsShutdownError(AgentOpsError):
    """Raised when the SDK is used after shutdown."""
