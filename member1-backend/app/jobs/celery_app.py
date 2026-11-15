"""Celery worker entry point:  celery -A app.jobs.celery_app.celery_app worker -l info"""
from celery import Celery

from ..config import Settings
from ..services import get_services
from .pipeline import run_scan

_settings = Settings.from_env()
celery_app = Celery("privacylens", broker=_settings.redis_url, backend=_settings.redis_url)
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1  # scans are long; do not hoard jobs


@celery_app.task(name="privacylens.run_scan")
def run_scan_task(scan_id: str) -> None:
    run_scan(scan_id, get_services())
