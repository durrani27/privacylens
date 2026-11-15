"""
Tracker / ad-SDK detection by matching bundled class names against Exodus Privacy signatures.

Signature file format = the Exodus API (https://reports.exodus-privacy.eu.org/api/trackers):
    {"trackers": {"<id>": {"name": ..., "code_signature": "a.b.c|d.e.f", "categories": [...], ...}}}
`data/exodus_seed.json` ships a SMALL seed so the package works offline; run
`python scripts/update_exodus.py` to download the full database.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from .sensitive_apis import to_dotted

DEFAULT_SIGNATURES = Path(__file__).resolve().parents[2] / "data" / "exodus_seed.json"


@dataclass(frozen=True)
class Tracker:
    id: str
    name: str
    code_signatures: tuple[str, ...]
    categories: tuple[str, ...] = ()
    website: Optional[str] = None


@dataclass
class TrackerMatch:
    tracker: Tracker
    class_count: int = 0
    sample_class: str = ""


def load_trackers(path: Optional[Path] = None) -> list[Tracker]:
    data = json.loads(Path(path or os.environ.get("EXODUS_SIGNATURES") or DEFAULT_SIGNATURES).read_text(encoding="utf-8"))
    trackers = []
    for tid, t in (data.get("trackers") or {}).items():
        parts = tuple(
            p.replace("\\", "").strip(".").strip()
            for p in (t.get("code_signature") or "").split("|")
            if p.strip()
        )
        if parts:  # network-only signatures cannot be matched against code
            trackers.append(Tracker(str(t.get("id", tid)), t["name"], parts,
                                    tuple(t.get("categories") or ()), t.get("website")))
    return trackers


class SignatureIndex:
    """Maps every signature prefix to its tracker so matching is O(classes x depth)."""

    def __init__(self, trackers: Iterable[Tracker]):
        self._by_prefix: dict[str, Tracker] = {}
        for t in trackers:
            for part in t.code_signatures:
                self._by_prefix.setdefault(part, t)

    def match(self, class_names: Iterable[str]) -> list[TrackerMatch]:
        found: dict[str, TrackerMatch] = {}
        for raw in class_names:
            cls = to_dotted(raw).split("$", 1)[0]
            pieces = cls.split(".")
            for depth in range(1, len(pieces) + 1):
                tracker = self._by_prefix.get(".".join(pieces[:depth]))
                if tracker is not None:
                    m = found.setdefault(tracker.id, TrackerMatch(tracker, 0, cls))
                    m.class_count += 1
                    break
        return sorted(found.values(), key=lambda m: m.tracker.name.lower())
