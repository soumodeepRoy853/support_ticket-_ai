from fastapi import APIRouter, Depends
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.schemas.analytics import DashboardSummary
from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard_summary(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.AGENT)),
):
    return await analytics_service.get_dashboard_summary(current_user.organization_id)