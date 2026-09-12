import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://red-cluster:6379/0")

celery_app = Celery(
    "niyogdisha",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "periodic-source-check": {
            "task": "app.services.tasks.run_scheduled_source_checks",
            "schedule": 7200.0,  # Every 2 hours
        },
        "periodic-job-expiry": {
            "task": "app.services.tasks.run_job_expiry",
            "schedule": 86400.0,  # Every 24 hours
        },
    },
)
