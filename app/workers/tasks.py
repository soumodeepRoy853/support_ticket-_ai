import json
import logging
import uuid

from google.genai import errors as google_errors
from sqlalchemy import create_engine
from sqlalchemy import func, case
from sqlalchemy.orm import sessionmaker
from tenacity import RetryError

from app import models  # Ensure all SQLAlchemy models are registered in metadata.
from app.core.config import settings
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.user import User, UserRole
from app.services.ai_service import categorize_ticket, generate_embedding
from app.workers.celery_app import celery_app
import redis as sync_redis

logger = logging.getLogger(__name__)
redis_client = sync_redis.from_url(settings.redis_url)
EMBEDDING_DIMENSION = 768

# Celery tasks run in a separate process from FastAPI, so we use a SYNC engine here.
sync_database_url = settings.database_url.replace("+asyncpg", "+psycopg").replace("ssl=require", "sslmode=require")
sync_engine = create_engine(sync_database_url, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=sync_engine)


def _unwrap_retry_error(exc: Exception) -> Exception:
    if isinstance(exc, RetryError):
        last_exc = exc.last_attempt.exception() if exc.last_attempt else None
        return last_exc or exc
    return exc


def _is_permanent_ai_error(exc: Exception) -> bool:
    if not isinstance(exc, google_errors.ClientError):
        return False
    message = str(exc).upper()
    return any(code in message for code in ["401", "403", "404", "429", "UNAUTHENTICATED", "PERMISSION_DENIED", "NOT_FOUND", "INVALID_ARGUMENT", "RESOURCE_EXHAUSTED"])


def _pick_least_loaded_agent(db, organization_id):
    """Pick agent/admin with smallest active (open/pending) ticket count in the org."""
    try:
        active_count_expr = func.sum(
            case(
                (Ticket.status.in_([TicketStatus.OPEN, TicketStatus.PENDING]), 1),
                else_=0,
            )
        )
        rows = (
            db.query(
                User.id.label("agent_id"),
                active_count_expr.label("active_count"),
            )
            .outerjoin(Ticket, Ticket.assigned_agent_id == User.id)
            .filter(
                User.organization_id == organization_id,
                User.role.in_([UserRole.AGENT, UserRole.ADMIN]),
            )
            .group_by(User.id)
            .order_by(active_count_expr.asc(), User.created_at.asc())
            .all()
        )
        return rows[0].agent_id if rows else None
    except Exception:
        return None

@celery_app.task(bind=True, name="app.workers.tasks.process_ticket_ai", max_retries=3, default_retry_delay=10)
def process_ticket_ai(self, ticket_id: str):
    db = SyncSessionLocal()
    try:
        try:
            ticket_uuid = uuid.UUID(str(ticket_id))
        except (TypeError, ValueError):
            logger.warning(f"Invalid ticket_id {ticket_id!r}, skipping AI processing")
            return

        ticket = db.query(Ticket).filter(Ticket.id == ticket_uuid).first()
        if not ticket:
            logger.warning(f"Ticket {ticket_id} not found, skipping AI processing")
            return

        logger.info(f"Processing AI for ticket {ticket_id}")
        result = categorize_ticket(ticket.subject, ticket.description)

        ticket.ai_category = result.get("category")
        ticket.ai_priority = TicketPriority(result.get("priority", "medium"))
        ticket.ai_summary = result.get("summary")
        ticket.ai_suggested_reply = result.get("suggested_reply")

        # If nobody is assigned yet, auto-assign on first AI handling.
        if ticket.assigned_agent_id is None:
            ticket.assigned_agent_id = _pick_least_loaded_agent(db, ticket.organization_id)

        # Persist assignment and AI text first so embedding failures do not roll back these updates.
        db.commit()

        combined_text = f"{ticket.subject}\n{ticket.description}"
        try:
            embedding = generate_embedding(combined_text)
            if isinstance(embedding, list) and len(embedding) == EMBEDDING_DIMENSION:
                ticket.embedding = embedding
                db.commit()
            else:
                logger.warning(
                    f"Skipping embedding for ticket {ticket_id}: expected {EMBEDDING_DIMENSION} dimensions, got {len(embedding) if isinstance(embedding, list) else 'invalid'}"
                )
        except Exception as embedding_exc:
            db.rollback()
            logger.warning(
                f"Embedding generation failed for ticket {ticket_id}, continuing without embedding: {embedding_exc}"
            )

        logger.info(f"Ticket {ticket_id} AI-processed successfully")

        publish_ticket_event(str(ticket.organization_id), {
        "event": "ticket_ai_processed",
        "ticket_id": str(ticket.id),
        "ai_category": ticket.ai_category,
        "ai_priority": ticket.ai_priority.value if ticket.ai_priority else None,
        "ai_summary": ticket.ai_summary,
        "ai_suggested_reply": ticket.ai_suggested_reply,
        })

    except Exception as exc:
        root_exc = _unwrap_retry_error(exc)
        logger.error(f"AI processing failed for ticket {ticket_id}: {root_exc}")
        db.rollback()

        # Avoid infinite retries on permanent provider/config errors.
        if _is_permanent_ai_error(root_exc):
            logger.error(f"Permanent AI provider error for ticket {ticket_id}; skipping retry")
            return

        if self.request.retries >= self.max_retries:
            logger.error(f"Max retries reached for ticket {ticket_id}; stopping retries")
            return

        # Celery exceptions should be pickle-safe.
        raise self.retry(exc=RuntimeError(str(root_exc)))
    finally:
        db.close()


def publish_ticket_event(organization_id: str, event: dict):
    redis_client.publish("ticket_events", json.dumps({
        "organization_id": organization_id,
        "payload": event,
    }))