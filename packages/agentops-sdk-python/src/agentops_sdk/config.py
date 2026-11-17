
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agentops_sdk.exceptions import AgentOpsConfigurationError


CaptureMode = Literal["metadata_only", "redacted", "restricted"]


class AgentOpsConfig(BaseModel):
    """Configuration for the AgentOps Python SDK."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    endpoint: str = Field(min_length=1)
    api_key: str = Field(min_length=1, repr=False)
    # Optional: a client may be constructed without a default agent and
    # instead identify one or more agents per-call via AgentOps.agent(...).
    # Kept for backward compatibility with the original single-agent client.
    agent_id: UUID | None = None
    environment: str = Field(default="development", min_length=1)

    # Reported as telemetry's source.service_name - identifies the
    # application sending events, distinct from the agent's own name.
    service_name: str = Field(default="agentops-sdk-python", min_length=1)

    capture_mode: CaptureMode = "metadata_only"

    batch_size: int = Field(default=50, ge=1, le=1000)
    flush_interval: float = Field(default=5.0, gt=0)
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout: float = Field(default=5.0, gt=0)

    @field_validator("endpoint")
    @classmethod
    def normalize_endpoint(cls, value: str) -> str:
        value = value.strip().rstrip("/")

        if not value.startswith(("http://", "https://")):
            raise AgentOpsConfigurationError(
                "Endpoint must start with http:// or https://"
            )

        return value

    @field_validator("api_key", "environment")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise AgentOpsConfigurationError(
                "Configuration value cannot be empty"
            )

        return value

    @model_validator(mode="after")
    def validate_capture_mode(self):
        if self.capture_mode == "restricted":
            # Restricted capture requires a future authorization mechanism.
            # Do not enable it until backend authorization is implemented.
            raise AgentOpsConfigurationError(
                "Restricted capture is not available yet."
            )

        return self
