"""
Celery application configuration for ScholarGuard.

Uses Redis as both broker and result backend.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "scholarguard",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task behaviour
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Result expiry (24 hours)
    result_expires=86400,
)

# Auto-discover tasks in the app.tasks package
celery_app.autodiscover_tasks(["app.tasks"])
