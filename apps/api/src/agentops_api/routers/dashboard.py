from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from agentops_api.auth import AuthContext, get_auth_context
from agentops_api.db import get_db
from agentops_api.schemas.dashboard import DashboardOverviewResponse
from agentops_api.services.dashboard_service import get_overview


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    db: DBSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return get_overview(db, auth)
