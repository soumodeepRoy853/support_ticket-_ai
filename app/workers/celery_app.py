import ssl
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "support_ticket_ai",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
    task_time_limit=60,        # hard kill after 60s
    task_soft_time_limit=45,   # raise exception at 45s, allow cleanup
    broker_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
    redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
)

celery_app.autodiscover_tasks(["app.workers"])