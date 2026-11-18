"""Tenant-scoped aggregate queries backing the dashboard overview (M7).

Every query here goes through the existing tenant_scope.py helpers, exactly
like every other resource endpoint - an aggregate count must never be
computed from a differently-scoped query than the records a caller can
individually see, or the two would silently disagree for a key restricted to
one project/environment.
"""

from collections import OrderedDict
from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext
from agentops_api.models.core import Agent, Execution, TelemetryEventRecord
from agentops_api.services.tenant_scope import (
    scope_agent_list,
    scope_execution_list,
    scope_telemetry_event_list,
)


EXECUTION_TREND_DAYS = 7


def _execution_status_counts(db: DBSession, auth: AuthContext) -> dict[str, int]:
    statement = scope_execution_list(
        select(Execution.status, func.count(Execution.id)).group_by(Execution.status),
        auth,
    )
    return dict(db.execute(statement).all())


def _total_tokens_used(db: DBSession, auth: AuthContext) -> int | None:
    statement = scope_telemetry_event_list(
        select(
            func.sum(cast(TelemetryEventRecord.model_usage["total_tokens"].astext, Integer))
        ).where(TelemetryEventRecord.model_usage.isnot(None)),
        auth,
    )
    total = db.execute(statement).scalar_one_or_none()
    return int(total) if total is not None else None


def _recent_executions(db: DBSession, auth: AuthContext, limit: int) -> list[Execution]:
    statement = scope_execution_list(
        select(Execution).order_by(Execution.created_at.desc()).limit(limit),
        auth,
    )
    return list(db.execute(statement).scalars().all())


def _recent_agents(db: DBSession, auth: AuthContext, limit: int) -> list[Agent]:
    statement = scope_agent_list(
        select(Agent).order_by(Agent.updated_at.desc()).limit(limit),
        auth,
    )
    return list(db.execute(statement).scalars().all())


def _total_agents(db: DBSession, auth: AuthContext) -> int:
    statement = scope_agent_list(select(func.count(Agent.id)), auth)
    return db.execute(statement).scalar_one()


def _execution_trend(db: DBSession, auth: AuthContext, days: int) -> list[tuple[datetime, int]]:
    window_start = datetime.now(timezone.utc) - timedelta(days=days - 1)

    statement = scope_execution_list(
        select(
            func.date_trunc("day", Execution.created_at).label("day"),
            func.count(Execution.id),
        )
        .where(Execution.created_at >= window_start)
        .group_by("day"),
        auth,
    )
    return list(db.execute(statement).all())


def get_overview(db: DBSession, auth: AuthContext) -> dict:
    status_counts = _execution_status_counts(db, auth)

    completed = status_counts.get("completed", 0)
    failed = status_counts.get("failed", 0)
    denominator = completed + failed
    success_rate = (completed / denominator) if denominator > 0 else None

    today = datetime.now(timezone.utc).date()
    trend_by_day: OrderedDict[object, int] = OrderedDict(
        ((today - timedelta(days=offset)), 0) for offset in range(EXECUTION_TREND_DAYS - 1, -1, -1)
    )

    for day, count in _execution_trend(db, auth, EXECUTION_TREND_DAYS):
        trend_by_day[day.date()] = count

    return {
        "total_executions": sum(status_counts.values()),
        "running_executions": status_counts.get("running", 0),
        "completed_executions": completed,
        "failed_executions": failed,
        "queued_executions": status_counts.get("queued", 0),
        "cancelled_executions": status_counts.get("cancelled", 0),
        "success_rate": success_rate,
        "total_agents": _total_agents(db, auth),
        "total_tokens_used": _total_tokens_used(db, auth),
        "recent_executions": _recent_executions(db, auth, limit=10),
        "recent_agents": _recent_agents(db, auth, limit=5),
        "execution_trend": [
            {"date": day, "count": count} for day, count in trend_by_day.items()
        ],
    }
