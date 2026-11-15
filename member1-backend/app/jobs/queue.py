"""Hand a scan to a worker. `celery` in docker-compose, threads for local dev, `sync` for tests."""
from __future__ import annotations

import threading

from .pipeline import run_scan


def enqueue_scan(scan_id: str, services) -> None:
    backend = services.settings.queue_backend
    if backend == "celery":
        from .celery_app import run_scan_task  # lazy: Celery is only needed in this mode

        run_scan_task.delay(scan_id)
    elif backend == "sync":
        run_scan(scan_id, services)
    else:  # "inline": background thread, no Redis required
        threading.Thread(target=run_scan, args=(scan_id, services), daemon=True).start()
