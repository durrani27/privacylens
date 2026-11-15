"""Turn ApkFacts into contract evidence rows: permissions, sensitive API calls, tracker SDKs."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..contract import make_evidence
from .apk_reader import AndroguardReader, ApkFacts
from .sdk_signatures import SignatureIndex, load_trackers


def facts_to_evidence(facts: ApkFacts, index: Optional[SignatureIndex] = None) -> list[dict]:
    index = index or SignatureIndex(load_trackers())
    rows: list[dict] = []

    for perm in facts.permissions:
        rows.append(make_evidence(
            "static", "permission", perm,
            snippet="Requested in AndroidManifest.xml", confidence=1.0))

    for call, sites in sorted(facts.api_calls.items()):
        rows.append(make_evidence(
            "static", "api_call", call,
            snippet=f"Called from {sites} place(s) in the app's code", confidence=0.9,
            meta={"call_sites": sites}))

    for m in index.match(facts.class_names):
        rows.append(make_evidence(
            "sdk", "sdk", m.tracker.name,
            snippet=f"Bundled tracker library detected ({m.class_count} class(es), e.g. {m.sample_class})",
            confidence=0.9,
            meta={"exodus_categories": list(m.tracker.categories), "class_count": m.class_count,
                  "sample_class": m.sample_class, "website": m.tracker.website}))
    return rows


def analyze_apk(apk_path: str | Path, reader: Optional[AndroguardReader] = None,
                index: Optional[SignatureIndex] = None) -> list[dict]:
    facts = (reader or AndroguardReader()).read(apk_path)
    return facts_to_evidence(facts, index)
