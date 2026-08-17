import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, extract
from datetime import datetime, timedelta
from uuid import UUID
from app.models.ticket import Ticket, TicketStatus
from app.models.user import User, UserRole
from app.core.database import AsyncSessionLocal


async def get_status_breakdown(db: AsyncSession, org_id: UUID) -> list[dict]:
    query = (
        select(Ticket.status, func.count(Ticket.id).label("count"))
        .where(Ticket.organization_id == org_id)
        .group_by(Ticket.status)
    )
    result = await db.execute(query)
    return [{"status": row.status.value, "count": row.count} for row in result]




async def get_category_breakdown(db: AsyncSession, org_id: UUID) -> list[dict]:
    query = (
        select(Ticket.ai_category, func.count(Ticket.id).label("count"))
        .where(Ticket.organization_id == org_id, Ticket.ai_category.isnot(None))
        .group_by(Ticket.ai_category)
        .order_by(func.count(Ticket.id).desc())
    )
    result = await db.execute(query)
    return [{"category": row.ai_category, "count": row.count} for row in result]




async def get_avg_resolution_hours(db: AsyncSession, org_id: UUID) -> float | None:
    # resolution time = updated_at - created_at, but ONLY for tickets that reached
    # resolved/closed — an open ticket has no resolution time yet
    query = select(
        func.avg(
            extract("epoch", Ticket.updated_at - Ticket.created_at) / 3600.0
        )
    ).where(
        Ticket.organization_id == org_id,
        Ticket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED]),
    )
    result = await db.execute(query)
    avg_hours = result.scalar_one_or_none()
    return round(avg_hours, 2) if avg_hours is not None else None




async def get_daily_volume(db: AsyncSession, org_id: UUID, days: int = 14) -> list[dict]:
    since = datetime.utcnow() - timedelta(days=days)
    query = (
        select(
            func.date(Ticket.created_at).label("day"),
            func.count(Ticket.id).label("count"),
        )
        .where(Ticket.organization_id == org_id, Ticket.created_at >= since)
        .group_by(func.date(Ticket.created_at))
        .order_by(func.date(Ticket.created_at))
    )
    result = await db.execute(query)
    return [{"date": row.day, "count": row.count} for row in result]




async def get_agent_workload(db: AsyncSession, org_id: UUID) -> list[dict]:
    query = (
        select(
            User.id,
            User.full_name,
            func.sum(
                case(
                    (Ticket.status.in_([TicketStatus.OPEN, TicketStatus.PENDING]), 1),
                    else_=0,
                )
            ).label("open_tickets"),
        )
        .outerjoin(Ticket, Ticket.assigned_agent_id == User.id)
        .where(
            User.organization_id == org_id,
            User.role.in_([UserRole.AGENT, UserRole.ADMIN]),
        )
        .group_by(User.id, User.full_name)
        .having(func.sum(case((Ticket.status.in_([TicketStatus.OPEN, TicketStatus.PENDING]), 1), else_=0)) > 0)
        .order_by(func.sum(case((Ticket.status.in_([TicketStatus.OPEN, TicketStatus.PENDING]), 1), else_=0)).desc())
    )
    result = await db.execute(query)
    return [
        {"agent_id": str(row.id), "agent_name": row.full_name, "open_tickets": row.open_tickets}
        for row in result
    ]



async def get_dashboard_summary(org_id: UUID) -> dict:
    async def run(coro_func):
        async with AsyncSessionLocal() as session:
            return await coro_func(session, org_id)

    total_tickets_query = select(func.count(Ticket.id)).where(Ticket.organization_id == org_id)

    async def get_total():
        async with AsyncSessionLocal() as session:
            result = await session.execute(total_tickets_query)
            return result.scalar_one()

    total, status_breakdown, category_breakdown, avg_resolution, daily_volume, agent_workload = await asyncio.gather(
        get_total(),
        run(get_status_breakdown),
        run(get_category_breakdown),
        run(get_avg_resolution_hours),
        run(get_daily_volume),
        run(get_agent_workload),
    )

    return {
        "total_tickets": total,
        "status_breakdown": status_breakdown,
        "category_breakdown": category_breakdown,
        "avg_resolution_hours": avg_resolution,
        "daily_volume": daily_volume,
        "agent_workload": agent_workload,
    }