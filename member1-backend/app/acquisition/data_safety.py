"""
Play Store "Data Safety" declaration: parsing + conversion to contract evidence rows.

ASSUMPTION (verify in Iteration 1 spike): the Python `google-play-scraper` package is not
confirmed to expose Data Safety. The Node.js `google-play-scraper` has `datasafety()`
returning sharedData / collectedData / securityPractices / privacyPolicyUrl, so the default
provider shells out to tools/datasafety.mjs. A file-based provider lets a team member drop a
JSON export into DATA_DIR/datasafety/<package>.json when scraping is blocked.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional, Protocol

from ..contract import make_evidence

_TOOLS = Path(__file__).resolve().parents[2] / "tools"


def _split_purposes(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [p.strip() for p in str(value).split(",") if p.strip()]


def parse_data_safety(raw: Optional[dict]) -> Optional[dict]:
    """Normalise a provider payload. Returns None when the declaration is unavailable.

    An EMPTY declaration ("No data collected / shared") is a real, meaningful answer and is
    returned as a dict with empty lists.
    """
    if raw is None or not isinstance(raw, dict):
        return None
    out: dict = {
        "collected": [],
        "shared": [],
        "privacy_policy_url": raw.get("privacyPolicyUrl") or raw.get("privacy_policy_url"),
    }
    for key_in, key_out in (
        ("collectedData", "collected"),
        ("collected", "collected"),
        ("sharedData", "shared"),
        ("shared", "shared"),
    ):
        for item in raw.get(key_in) or []:
            category = item.get("category") or item.get("type") or "Unknown"
            specific = (
                item.get("data")
                or item.get("name")
                or (item.get("type") if item.get("category") else None)
                or category
            )
            out[key_out].append(
                {
                    "category": category,
                    "type": specific,
                    "optional": bool(item.get("optional")),
                    "purposes": _split_purposes(item.get("purpose") or item.get("purposes")),
                }
            )
    return out


def data_safety_to_evidence(ds: dict) -> list[dict]:
    """One evidence row per declared (action, data type)."""
    rows = []
    for action in ("collected", "shared"):
        for item in ds.get(action, []):
            rows.append(
                make_evidence(
                    "datasafety",
                    "data_safety_field",
                    f"{item['category']} > {item['type']}",
                    snippet=f"Declared as {action} on the Play Store Data Safety label",
                    meta={
                        "action": action,
                        "ds_category": item["category"],
                        "purposes": item["purposes"],
                        "optional": item["optional"],
                    },
                )
            )
    return rows


class DataSafetyProvider(Protocol):
    def fetch(self, package: str) -> Optional[dict]: ...


class NodeDataSafetyProvider:
    """Calls `node tools/datasafety.mjs <package>` (needs `npm install` in tools/)."""

    def __init__(self, script: Path = _TOOLS / "datasafety.mjs", node: str = "node", timeout: int = 60):
        self.script, self.node, self.timeout = script, node, timeout

    def fetch(self, package: str) -> Optional[dict]:
        try:
            proc = subprocess.run(
                [self.node, str(self.script), package],
                capture_output=True, text=True, timeout=self.timeout, check=True,
            )
            return parse_data_safety(json.loads(proc.stdout))
        except (OSError, subprocess.SubprocessError, ValueError):
            return None


class FileDataSafetyProvider:
    """Reads DATA_DIR/datasafety/<package>.json (manual export / fixtures)."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def fetch(self, package: str) -> Optional[dict]:
        path = self.directory / f"{package}.json"
        if not path.is_file():
            return None
        try:
            return parse_data_safety(json.loads(path.read_text(encoding="utf-8")))
        except ValueError:
            return None
