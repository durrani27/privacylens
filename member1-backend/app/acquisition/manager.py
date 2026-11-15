"""
AcquisitionManager - gathers evidence inputs for one app, cheapest/safest tier first.

  Always      : public Play page -> metadata, reviews, Data Safety declaration
  APK, in order: local APK cache -> F-Droid -> AndroZoo -> user upload -> emulator (last resort)

Every tier failure is recorded in `source_status` (never raised), so one broken source
cannot sink the whole scan.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from .data_safety import DataSafetyProvider, data_safety_to_evidence


@dataclass
class AcquisitionResult:
    package: str
    metadata: dict = field(default_factory=dict)
    reviews: list = field(default_factory=list)
    data_safety: Optional[dict] = None
    privacy_policy_url: Optional[str] = None
    apk_path: Optional[str] = None
    source_status: dict = field(default_factory=dict)

    def data_safety_evidence(self) -> list[dict]:
        return data_safety_to_evidence(self.data_safety) if self.data_safety else []


class AcquisitionManager:
    def __init__(self, play, ds_providers: Sequence[DataSafetyProvider], apk_sources: Sequence,
                 apk_dir: Path, apk_cache_ttl_hours: int = 24 * 7, review_count: int = 200):
        self.play, self.ds_providers, self.apk_sources = play, list(ds_providers), list(apk_sources)
        self.apk_dir, self.apk_cache_ttl_hours, self.review_count = Path(apk_dir), apk_cache_ttl_hours, review_count

    # -- helpers -----------------------------------------------------------
    def _cached_apk(self, package: str) -> Optional[Path]:
        path = self.apk_dir / f"{package}.apk"
        if path.is_file() and time.time() - path.stat().st_mtime <= self.apk_cache_ttl_hours * 3600:
            return path
        return None

    def _acquire_apk(self, package: str, status: dict) -> Optional[Path]:
        tiers: list[str] = []
        found: Optional[Path] = None
        cached = self._cached_apk(package)
        if cached:
            tiers.append("cache:hit")
            found, status["apk_source"] = cached, "cache"
        else:
            tiers.append("cache:miss")
            for source in self.apk_sources:
                try:
                    path = source.fetch(package, self.apk_dir)
                except Exception as exc:  # noqa: BLE001 - tier failures must not abort the scan
                    tiers.append(f"{source.name}:error:{type(exc).__name__}")
                    continue
                if path:
                    tiers.append(f"{source.name}:hit")
                    found, status["apk_source"] = Path(path), source.name
                    break
                tiers.append(f"{source.name}:miss")
        status["apk_tiers"] = tiers
        status.setdefault("apk_source", "none")
        return found

    # -- main entry --------------------------------------------------------
    def acquire(self, package: str) -> AcquisitionResult:
        result = AcquisitionResult(package=package)
        status = result.source_status

        # Tier A: public Play Store data (always)
        try:
            result.metadata = self.play.get_app(package) or {}
            status["metadata"] = "ok"
        except Exception as exc:  # noqa: BLE001
            status["metadata"] = f"failed:{type(exc).__name__}"
        try:
            result.reviews = self.play.get_reviews(package, self.review_count) or []
            status["reviews"] = "ok" if result.reviews else "unavailable"
        except Exception as exc:  # noqa: BLE001
            status["reviews"] = f"failed:{type(exc).__name__}"

        for provider in self.ds_providers:
            try:
                ds = provider.fetch(package)
            except Exception:  # noqa: BLE001
                ds = None
            if ds is not None:
                result.data_safety = ds
                break
        status["datasafety"] = "ok" if result.data_safety is not None else "unavailable"

        result.privacy_policy_url = result.metadata.get("privacy_policy_url") or (
            (result.data_safety or {}).get("privacy_policy_url")
        )
        # The analyzer upgrades these two from "pending" to "ok" / "failed".
        status["policy"] = "pending" if result.privacy_policy_url else "unavailable"

        # Tier B: the APK file
        apk = self._acquire_apk(package, status)
        result.apk_path = str(apk) if apk else None
        status["code"] = "pending" if apk else "unavailable"
        return result
