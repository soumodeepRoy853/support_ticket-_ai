import logging
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # Ensure all SQLAlchemy models are registered in metadata.
from app.core.config import settings
from app.models.ticket import Ticket, TicketPriority
from app.services.ai_service import categorize_ticket
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Celery tasks run in a separate process from FastAPI, so we use a SYNC engine here.
# Use the PostgreSQL sync dialect explicitly so SQLAlchemy loads the correct driver.
sync_database_url = settings.database_url.replace("+asyncpg", "+psycopg")
sync_engine = create_engine(sync_database_url)
SyncSessionLocal = sessionmaker(bind=sync_engine)

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

        db.commit()
        logger.info(f"Ticket {ticket_id} AI-processed successfully")

    except Exception as exc:
        logger.error(f"AI processing failed for ticket {ticket_id}: {exc}")
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()