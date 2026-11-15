"""
PrivacyLens+ INTERFACE CONTRACT v1.0  (frozen at the end of Iteration 1)

This file is copied verbatim into all three member packages. It is an interface
specification (shared vocabulary + evidence row shape), not implemented feature
work, so it does not make the three packages overlap.

Every piece of evidence in the system is a plain dict with this shape:

    {
      "source":     one of SOURCES,
      "raw_type":   one of RAW_TYPES,
      "raw_value":  str   e.g. "android.permission.ACCESS_FINE_LOCATION",
      "snippet":    str | None   human-readable context (policy sentence, ...),
      "category":   one of TAXONOMY | None   (None until normalised),
      "polarity":   "declares" | "denies",
      "confidence": float | None,
      "meta":       dict   free-form extras (purposes, action, ...)
    }
"""
from __future__ import annotations

from typing import Any, Optional

TAXONOMY = (
    "location",
    "camera",
    "microphone",
    "contacts",
    "identifiers",
    "analytics",
    "advertising",
    "storage",
    "phone_sms",
    "calendar",
)

SOURCES = ("static", "sdk", "datasafety", "policy", "reviews")
RAW_TYPES = (
    "permission",
    "api_call",
    "sdk",
    "data_safety_field",
    "policy_sentence",
    "review_sentence",
)
POLARITIES = ("declares", "denies")

# The four "witnesses" the Consistency Engine reasons about.
WITNESSES = ("code", "datasafety", "policy", "reviews")


def make_evidence(
    source: str,
    raw_type: str,
    raw_value: str,
    *,
    snippet: Optional[str] = None,
    category: Optional[str] = None,
    polarity: str = "declares",
    confidence: Optional[float] = None,
    meta: Optional[dict] = None,
) -> dict:
    """Build and validate one evidence row."""
    row = {
        "source": source,
        "raw_type": raw_type,
        "raw_value": raw_value,
        "snippet": snippet,
        "category": category,
        "polarity": polarity,
        "confidence": confidence,
        "meta": dict(meta or {}),
    }
    validate_evidence(row)
    return row


def validate_evidence(row: dict[str, Any]) -> None:
    """Raise ValueError if `row` violates the contract."""
    if not isinstance(row, dict):
        raise ValueError("evidence must be a dict")
    if row.get("source") not in SOURCES:
        raise ValueError(f"bad source: {row.get('source')!r}")
    if row.get("raw_type") not in RAW_TYPES:
        raise ValueError(f"bad raw_type: {row.get('raw_type')!r}")
    if not isinstance(row.get("raw_value"), str) or not row["raw_value"]:
        raise ValueError("raw_value must be a non-empty string")
    if row.get("polarity", "declares") not in POLARITIES:
        raise ValueError(f"bad polarity: {row.get('polarity')!r}")
    cat = row.get("category")
    if cat is not None and cat not in TAXONOMY:
        raise ValueError(f"bad category: {cat!r}")
    conf = row.get("confidence")
    if conf is not None and not (0.0 <= float(conf) <= 1.0):
        raise ValueError("confidence must be within [0, 1]")
