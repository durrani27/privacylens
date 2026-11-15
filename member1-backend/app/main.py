"""
FastAPI application.

Run:  uvicorn app.main:create_app --factory --reload --port 8000
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .acquisition.play_store import PACKAGE_RE, resolve_query
from .jobs.queue import enqueue_scan
from .services import Services, get_services


class ScanRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300, description="App name, package id or Play link")
    force: bool = Field(False, description="Bypass the result cache")


def _scan_view(svc: Services, scan: dict) -> dict:
    app_row = svc.repo.get_app(scan["package"]) or {}
    view = {
        "scan_id": scan["id"],
        "package": scan["package"],
        "title": app_row.get("title"),
        "developer": app_row.get("developer"),
        "status": scan["status"],
        "stage": scan.get("stage"),
        "progress": scan.get("progress", 0),
        "error": scan.get("error"),
        "app_version": scan.get("app_version"),
        "source_status": scan.get("source_status") or {},
        "created_at": scan["created_at"],
        "findings": [],
    }
    if scan["status"] == "done":
        view["findings"] = svc.repo.list_findings(scan["id"])
    return view


def create_app(services: Optional[Services] = None) -> FastAPI:
    svc = services or get_services()
    app = FastAPI(title="PrivacyLens+ API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=list(svc.settings.cors_origins),
        allow_methods=["*"], allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "queue": svc.settings.queue_backend}

    @app.post("/api/scans", status_code=202)
    def create_scan(req: ScanRequest) -> dict:
        try:
            package = resolve_query(req.query, svc.play)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception:  # noqa: BLE001 - scraper/network problems
            raise HTTPException(status_code=502, detail="Play Store lookup failed")
        if not req.force:  # Step 3 of the workflow: cache check
            cached = svc.repo.find_cached_scan(package, svc.settings.cache_ttl_hours)
            if cached:
                return {"scan_id": cached["id"], "package": package,
                        "status": cached["status"], "cached": True}
        scan = svc.repo.create_scan(package)
        enqueue_scan(scan["id"], svc)
        return {"scan_id": scan["id"], "package": package, "status": "queued", "cached": False}

    @app.get("/api/scans/{scan_id}")
    def get_scan(scan_id: str) -> dict:
        scan = svc.repo.get_scan(scan_id)
        if scan is None:
            raise HTTPException(status_code=404, detail="Scan not found")
        return _scan_view(svc, scan)

    @app.get("/api/scans/{scan_id}/evidence")
    def get_evidence(scan_id: str) -> list[dict]:
        if svc.repo.get_scan(scan_id) is None:
            raise HTTPException(status_code=404, detail="Scan not found")
        return svc.repo.list_evidence(scan_id)

    @app.get("/api/apps/{package}/scans")
    def app_history(package: str) -> list[dict]:
        return svc.repo.list_scans(package)

    @app.put("/api/uploads/{package}", status_code=201)
    async def upload_apk(package: str, request: Request) -> dict:
        """Raw-body APK upload (Content-Type: application/octet-stream)."""
        if not PACKAGE_RE.match(package) or re.search(r"[\\/]", package):
            raise HTTPException(status_code=422, detail="Invalid package id")
        limit = svc.settings.max_apk_bytes
        declared = request.headers.get("content-length")
        if declared and int(declared) > limit:
            raise HTTPException(status_code=413, detail="APK too large")
        body = await request.body()
        if len(body) > limit:
            raise HTTPException(status_code=413, detail="APK too large")
        if body[:2] != b"PK":  # APKs are ZIP archives
            raise HTTPException(status_code=422, detail="File is not an APK/ZIP archive")
        target_dir = svc.settings.data_dir / "uploads"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / f"{package}.apk").write_bytes(body)
        return {"package": package, "stored_bytes": len(body)}

    return app
