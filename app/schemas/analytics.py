from pydantic import BaseModel
from datetime import date

class StatusBreakdown(BaseModel):
    status: str
    count: int

class CategoryBreakdown(BaseModel):
    category: str
    count: int

class DailyVolume(BaseModel):
    date: date
    count: int

class AgentWorkload(BaseModel):
    agent_id: str
    agent_name: str
    open_tickets: int

class DashboardSummary(BaseModel):
    total_tickets: int
    status_breakdown: list[StatusBreakdown]
    category_breakdown: list[CategoryBreakdown]
    avg_resolution_hours: float | None
    daily_volume: list[DailyVolume]
    agent_workload: list[AgentWorkload]