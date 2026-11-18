from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExecutionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    session_id: UUID
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: int | None
    created_at: datetime


class AgentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    environment_id: UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class ExecutionTrendPoint(BaseModel):
    date: date
    count: int


class DashboardOverviewResponse(BaseModel):
    total_executions: int
    running_executions: int
    completed_executions: int
    failed_executions: int
    queued_executions: int
    cancelled_executions: int

    # None when there is no completed/failed execution yet to compute a rate
    # from - distinct from an actual 0% success rate.
    success_rate: float | None

    total_agents: int

    # None when no telemetry event in scope has ever reported model_usage -
    # distinct from a genuine total of 0 tokens.
    total_tokens_used: int | None

    recent_executions: list[ExecutionSummary]
    recent_agents: list[AgentSummary]

    # Daily execution counts for the trailing window; always present (an
    # empty/zero-filled list is a real "no executions that day", not
    # "unavailable"), per the M7 "clearly distinguish unavailable metrics
    # from zero values" requirement applied to this particular metric.
    execution_trend: list[ExecutionTrendPoint]
