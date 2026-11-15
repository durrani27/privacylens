"""
Plug-in entry point for Member 1's pipeline:   FINDINGS_ENGINE=consistency.service:build_findings

    build_findings({"evidence": [row+id, ...], "availability": {"code":bool,"datasafety":bool,"policy":bool,"reviews":bool}})
        -> [ {category, verdict, rule_id, explanation, evidence_ids}, ... ]
"""
from __future__ import annotations

from .engine import evaluate
from .normalizer import normalize


def build_findings(payload: dict) -> list[dict]:
    rows = normalize(payload.get("evidence", []))
    return evaluate(rows, payload.get("availability", {}))
