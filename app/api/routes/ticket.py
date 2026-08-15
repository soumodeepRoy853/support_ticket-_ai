from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.ticket import TicketStatus
from app.schemas.ticket import TicketCreate, TicketUpdate, TicketOut, TicketListOut
from app.services import ticket_service
from app.workers.tasks import process_ticket_ai

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

@router.post("/", response_model=TicketOut, status_code=201)
async def create_ticket(
    payload: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ticket = await ticket_service.create_ticket(db, current_user, payload)
    try:
        process_ticket_ai.delay(str(ticket.id))
    except Exception:
        # Keep ticket creation successful even if the AI queue is unavailable.
        # The ticket is already stored; the AI processing can be retried later.
        pass
    return ticket

@router.get("/", response_model=TicketListOut)
async def list_tickets(
    status: TicketStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await ticket_service.list_tickets(
        db, current_user.organization_id, status, page, page_size
    )
    return TicketListOut(total=total, page=page, page_size=page_size, items=items)

@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ticket_service.get_ticket_or_404(db, ticket_id, current_user.organization_id)

@router.patch("/{ticket_id}", response_model=TicketOut)
async def update_ticket(
    ticket_id: str,
    payload: TicketUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.AGENT)),
    db: AsyncSession = Depends(get_db),
):
    ticket = await ticket_service.get_ticket_or_404(db, ticket_id, current_user.organization_id)
    return await ticket_service.update_ticket(db, ticket, payload, current_user)