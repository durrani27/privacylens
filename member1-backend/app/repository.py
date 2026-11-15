"""Data-access functions for apps, scans, evidence, findings and snapshots."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .db import Database

_ACTIVE = ("queued", "running")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex


def _loads(value: Optional[str], default: Any) -> Any:
    return json.loads(value) if value else default


class Repository:
    def __init__(self, db: Database):
        self.db = db

    # -- apps --------------------------------------------------------------
    def upsert_app(self, package: str, **fields: Any) -> None:
        allowed = {"title", "developer", "latest_version", "privacy_policy_url"}
        data = {k: v for k, v in fields.items() if k in allowed and v is not None}
        now = _now()
        if not self.db.query("SELECT package FROM apps WHERE package = :p", {"p": package}):
            self.db.execute(
                "INSERT INTO apps (package, created_at, updated_at) VALUES (:p, :n, :n)",
                {"p": package, "n": now},
            )
        for key, value in data.items():  # keys are whitelisted above
            self.db.execute(
                f"UPDATE apps SET {key} = :v, updated_at = :n WHERE package = :p",
                {"v": value, "n": now, "p": package},
            )

    def get_app(self, package: str) -> Optional[dict]:
        rows = self.db.query("SELECT * FROM apps WHERE package = :p", {"p": package})
        return rows[0] if rows else None

    # -- scans -------------------------------------------------------------
    def create_scan(self, package: str) -> dict:
        self.upsert_app(package)
        scan_id, now = _id(), _now()
        self.db.execute(
            "INSERT INTO scans (id, package, status, stage, progress, created_at, updated_at) "
            "VALUES (:id, :p, 'queued', 'queued', 0, :n, :n)",
            {"id": scan_id, "p": package, "n": now},
        )
        return self.get_scan(scan_id)  # type: ignore[return-value]

    def get_scan(self, scan_id: str) -> Optional[dict]:
        rows = self.db.query("SELECT * FROM scans WHERE id = :id", {"id": scan_id})
        if not rows:
            return None
        scan = rows[0]
        scan["source_status"] = _loads(scan.get("source_status"), {})
        return scan

    def update_scan(self, scan_id: str, **fields: Any) -> None:
        allowed = {"status", "stage", "progress", "error", "app_version", "source_status"}
        sets, params = [], {"id": scan_id, "n": _now()}
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"cannot update scan field {key!r}")
            params[key] = json.dumps(value) if key == "source_status" else value
            sets.append(f"{key} = :{key}")
        if sets:
            self.db.execute(
                f"UPDATE scans SET {', '.join(sets)}, updated_at = :n WHERE id = :id", params
            )

    def list_scans(self, package: str) -> list[dict]:
        rows = self.db.query(
            "SELECT id, status, app_version, created_at FROM scans "
            "WHERE package = :p ORDER BY created_at DESC",
            {"p": package},
        )
        return rows

    def find_cached_scan(self, package: str, ttl_hours: int) -> Optional[dict]:
        """Latest finished scan inside the TTL, or an in-flight scan (last 1 h)."""
        now = datetime.now(timezone.utc)
        done_cutoff = (now - timedelta(hours=ttl_hours)).isoformat()
        active_cutoff = (now - timedelta(hours=1)).isoformat()
        rows = self.db.query(
            "SELECT id FROM scans WHERE package = :p AND ("
            " (status = 'done' AND created_at >= :done) OR"
            " (status IN ('queued', 'running') AND created_at >= :active)"
            ") ORDER BY created_at DESC",
            {"p": package, "done": done_cutoff, "active": active_cutoff},
        )
        return self.get_scan(rows[0]["id"]) if rows else None

    # -- evidence ----------------------------------------------------------
    def add_evidence(self, scan_id: str, rows: list[dict]) -> list[str]:
        ids = []
        for r in rows:
            eid = _id()
            ids.append(eid)
            self.db.execute(
                "INSERT INTO evidence (id, scan_id, source, raw_type, raw_value, category, "
                "polarity, confidence, snippet, meta, created_at) VALUES "
                "(:id, :scan, :source, :raw_type, :raw_value, :category, :polarity, "
                ":confidence, :snippet, :meta, :n)",
                {
                    "id": eid,
                    "scan": scan_id,
                    "source": r["source"],
                    "raw_type": r["raw_type"],
                    "raw_value": r["raw_value"],
                    "category": r.get("category"),
                    "polarity": r.get("polarity", "declares"),
                    "confidence": r.get("confidence"),
                    "snippet": r.get("snippet"),
                    "meta": json.dumps(r.get("meta") or {}),
                    "n": _now(),
                },
            )
        return ids

    def list_evidence(self, scan_id: str) -> list[dict]:
        rows = self.db.query(
            "SELECT * FROM evidence WHERE scan_id = :s ORDER BY created_at, id", {"s": scan_id}
        )
        for r in rows:
            r["meta"] = _loads(r.get("meta"), {})
        return rows

    # -- findings ----------------------------------------------------------
    def add_findings(self, scan_id: str, findings: list[dict]) -> None:
        for f in findings:
            self.db.execute(
                "INSERT INTO findings (id, scan_id, category, verdict, rule_id, explanation, "
                "evidence_ids, created_at) VALUES (:id, :s, :c, :v, :r, :e, :ev, :n)",
                {
                    "id": _id(),
                    "s": scan_id,
                    "c": f["category"],
                    "v": f["verdict"],
                    "r": f.get("rule_id"),
                    "e": f.get("explanation"),
                    "ev": json.dumps(f.get("evidence_ids", [])),
                    "n": _now(),
                },
            )

    def list_findings(self, scan_id: str) -> list[dict]:
        rows = self.db.query(
            "SELECT * FROM findings WHERE scan_id = :s ORDER BY category", {"s": scan_id}
        )
        for r in rows:
            r["evidence_ids"] = _loads(r.get("evidence_ids"), [])
        return rows

    # -- snapshots (consumed by Iteration 6 version drift) -----------------
    def save_snapshot(self, scan_id: str, package: str, app_version: Optional[str], payload: dict) -> None:
        self.db.execute(
            "INSERT INTO snapshots (id, scan_id, package, app_version, payload, created_at) "
            "VALUES (:id, :s, :p, :v, :pl, :n)",
            {"id": _id(), "s": scan_id, "p": package, "v": app_version,
             "pl": json.dumps(payload), "n": _now()},
        )

    def latest_snapshot(self, package: str) -> Optional[dict]:
        rows = self.db.query(
            "SELECT * FROM snapshots WHERE package = :p ORDER BY created_at DESC", {"p": package}
        )
        if not rows:
            return None
        rows[0]["payload"] = _loads(rows[0]["payload"], {})
        return rows[0]
