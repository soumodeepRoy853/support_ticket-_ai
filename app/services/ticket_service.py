from typing import Optional
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.ticket import Ticket, TicketStatus
from app.models.user import User, UserRole
from app.schemas.ticket import TicketCreate, TicketUpdate
from uuid import UUID
from fastapi import HTTPException

VALID_TRANSITIONS = {
    TicketStatus.OPEN: {TicketStatus.PENDING, TicketStatus.RESOLVED, TicketStatus.CLOSED},
    TicketStatus.PENDING: {TicketStatus.OPEN, TicketStatus.RESOLVED, TicketStatus.CLOSED},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.OPEN},
    TicketStatus.CLOSED: set(),  # closed is terminal
}

async def create_ticket(db: AsyncSession, customer: User, payload: TicketCreate) -> Ticket:
    ticket = Ticket(
        organization_id=customer.organization_id,
        customer_id=customer.id,
        subject=payload.subject,
        description=payload.description,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def get_ticket_or_404(db: AsyncSession, ticket_id: UUID, org_id: UUID) -> Ticket:
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.organization_id == org_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


async def list_tickets(
    db: AsyncSession,
    org_id: UUID,
    status: Optional[TicketStatus],
    page: int,
    page_size: int,
) -> tuple[list[Ticket], int]:
    query = select(Ticket).where(Ticket.organization_id == org_id)
    count_query = select(func.count()).select_from(Ticket).where(Ticket.organization_id == org_id)

    if status:
        query = query.where(Ticket.status == status)
        count_query = count_query.where(Ticket.status == status)

    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return items, total



async def update_ticket(db: AsyncSession, ticket: Ticket, payload: TicketUpdate, actor: User) -> Ticket:
    if actor.role not in (UserRole.ADMIN, UserRole.AGENT):
        raise HTTPException(status_code=403, detail="Only agents/admins can update tickets")

    if ticket.status is None:
        ticket.status = TicketStatus.OPEN

    if payload.status and payload.status != ticket.status:
        if payload.status not in VALID_TRANSITIONS[ticket.status]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from {ticket.status.value} to {payload.status.value}",
            )
        ticket.status = payload.status

    if payload.priority:
        ticket.priority = payload.priority

    if payload.assigned_agent_id is not None:
        ticket.assigned_agent_id = payload.assigned_agent_id
    elif ticket.assigned_agent_id is None:
        ticket.assigned_agent_id = actor.id

    await db.commit()
    await db.refresh(ticket)
    return ticket


async def find_similar_tickets(db: AsyncSession, ticket: Ticket, limit: int = 5) -> list[Ticket]:
    if ticket.embedding is None:
        return []  # AI processing hasn't completed yet

    result = await db.execute(
        select(Ticket)
        .where(
            Ticket.organization_id == ticket.organization_id,
            Ticket.id != ticket.id,
            Ticket.embedding.isnot(None),
        )
        .order_by(Ticket.embedding.cosine_distance(ticket.embedding))
        .limit(limit)
    )
    return result.scalars().all()