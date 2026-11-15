"""
The scan pipeline (what the Celery worker runs).

  acquisition -> [analyzers in parallel] -> findings engine -> snapshot -> done

Analyzers and the findings engine are PLUG-INS (dotted paths in env vars ANALYZERS and
FINDINGS_ENGINE). Member 2's `privacylens_analysis.entry:analyze` and Member 3's
`consistency.service:build_findings` plug in here without changing this file.

Analyzer contract:   fn(ctx: dict) -> {"evidence": [row, ...], "source_status": {...}}
Engine contract:     fn({"evidence": [row+id, ...], "availability": {witness: bool}}) -> [finding]
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from ..contract import WITNESSES, validate_evidence

log = logging.getLogger("privacylens.pipeline")


def _run_one(fn: Callable, ctx: dict) -> dict:
    try:
        out = fn(ctx) or {}
        return {"evidence": out.get("evidence", []), "source_status": out.get("source_status", {})}
    except Exception as exc:  # noqa: BLE001 - isolate analyzer failures
        log.exception("analyzer %s failed", getattr(fn, "__name__", fn))
        return {"evidence": [], "source_status": {}, "error": f"{getattr(fn, '__name__', 'analyzer')}: {type(exc).__name__}"}


def run_analyzers(analyzers: list, ctx: dict) -> list[dict]:
    """Run all analyzers concurrently (doc Step 5: pipelines run in parallel)."""
    if not analyzers:
        return []
    with ThreadPoolExecutor(max_workers=len(analyzers)) as pool:
        return list(pool.map(lambda fn: _run_one(fn, dict(ctx)), analyzers))


def run_scan(scan_id: str, services) -> None:
    repo = services.repo
    scan = repo.get_scan(scan_id)
    if scan is None:
        raise LookupError(scan_id)
    package = scan["package"]
    try:
        repo.update_scan(scan_id, status="running", stage="acquisition", progress=10)
        acq = services.acquisition.acquire(package)
        repo.upsert_app(
            package,
            title=acq.metadata.get("title"),
            developer=acq.metadata.get("developer"),
            latest_version=acq.metadata.get("version"),
            privacy_policy_url=acq.privacy_policy_url,
        )
        repo.add_evidence(scan_id, acq.data_safety_evidence())
        status = dict(acq.source_status)
        repo.update_scan(
            scan_id, stage="analysis", progress=40,
            app_version=acq.metadata.get("version"), source_status=status,
        )

        ctx = {
            "scan_id": scan_id,
            "package": package,
            "apk_path": acq.apk_path,
            "privacy_policy_url": acq.privacy_policy_url,
            "reviews": acq.reviews,
            "metadata": acq.metadata,
            "data_safety": acq.data_safety,
        }
        analyzer_errors = []
        for res in run_analyzers(services.analyzers, ctx):
            status.update(res["source_status"])
            if res.get("error"):
                analyzer_errors.append(res["error"])
            valid = []
            for row in res["evidence"]:
                try:
                    validate_evidence(row)
                    valid.append(row)
                except ValueError as exc:
                    analyzer_errors.append(f"dropped invalid evidence: {exc}")
            repo.add_evidence(scan_id, valid)
        if analyzer_errors:
            status["analyzer_errors"] = analyzer_errors
        repo.update_scan(scan_id, stage="findings", progress=80, source_status=status)

        evidence = repo.list_evidence(scan_id)
        availability = {w: status.get(w) == "ok" for w in WITNESSES}
        findings = []
        if services.engine is not None:
            findings = services.engine({"evidence": evidence, "availability": availability}) or []
            repo.add_findings(scan_id, findings)
        repo.save_snapshot(
            scan_id, package, acq.metadata.get("version"),
            {"evidence": evidence, "findings": findings, "availability": availability},
        )
        repo.update_scan(scan_id, status="done", stage="finished", progress=100)
    except Exception as exc:  # noqa: BLE001
        log.exception("scan %s failed", scan_id)
        repo.update_scan(scan_id, status="failed", error=f"{type(exc).__name__}: {exc}"[:500])
