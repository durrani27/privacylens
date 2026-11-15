"""
Plug-in entry points called by Member 1's pipeline (see M1 README, "Analyzer contract").

    ANALYZERS=privacylens_analysis.entry:analyze_static,privacylens_analysis.entry:analyze_policy

Each function takes the scan context dict and returns
    {"evidence": [row, ...], "source_status": {"code"|"policy": "ok" | "failed:<Error>"}}
They are independent so the backend can run them in parallel.
"""
from __future__ import annotations

import os

from .nlp.classifier import build_classifier
from .nlp.fetch import fetch_policy_text
from .nlp.policy import policy_text_to_evidence
from .static.analyzer import analyze_apk


def analyze_static(ctx: dict) -> dict:
    """Androguard permissions + sensitive API calls, plus Exodus tracker-SDK detection."""
    apk_path = ctx.get("apk_path")
    if not apk_path:
        return {"evidence": [], "source_status": {}}      # backend already marked code "unavailable"
    try:
        return {"evidence": analyze_apk(apk_path), "source_status": {"code": "ok"}}
    except Exception as exc:  # noqa: BLE001
        return {"evidence": [], "source_status": {"code": f"failed:{type(exc).__name__}"}}


def analyze_policy(ctx: dict) -> dict:
    """Fetch + clean + classify the privacy policy (classifier chosen by POLICY_CLASSIFIER)."""
    url = ctx.get("privacy_policy_url")
    if not url:
        return {"evidence": [], "source_status": {}}
    try:
        text = fetch_policy_text(url)
        classifier = build_classifier(os.environ.get("POLICY_CLASSIFIER", "keyword"))
        rows = policy_text_to_evidence(text, classifier, url=url)
        return {"evidence": rows, "source_status": {"policy": "ok"}}
    except Exception as exc:  # noqa: BLE001
        return {"evidence": [], "source_status": {"policy": f"failed:{type(exc).__name__}"}}
