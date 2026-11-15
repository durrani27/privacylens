"""Runtime configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _csv(value: Optional[str]) -> tuple[str, ...]:
    return tuple(p.strip() for p in (value or "").split(",") if p.strip())


@dataclass(frozen=True)
class Settings:
    # Storage / queue
    database_url: str = "sqlite:///./privacylens.db"
    queue_backend: str = "inline"          # inline | celery | sync (tests)
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_hours: int = 24              # scan-result cache window
    apk_cache_ttl_hours: int = 24 * 7      # downloaded APK cache window
    data_dir: Path = Path("./data")

    # Curated APK datasets
    fdroid_index_url: str = "https://f-droid.org/repo/index-v2.json"
    fdroid_base_url: str = "https://f-droid.org/repo/"
    androzoo_api_key: Optional[str] = None
    androzoo_csv: Optional[Path] = None    # local copy of AndroZoo latest.csv
    max_apk_bytes: int = 300 * 1024 * 1024

    # Last-resort acquisition
    enable_emulator: bool = False
    adb_serial: Optional[str] = None

    # Plug-in points (dotted "module:function" paths)
    analyzers: tuple[str, ...] = ()
    findings_engine: Optional[str] = None

    cors_origins: tuple[str, ...] = ("http://localhost:5173",)

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        return cls(
            database_url=e("DATABASE_URL", cls.database_url),
            queue_backend=e("QUEUE_BACKEND", cls.queue_backend),
            redis_url=e("REDIS_URL", cls.redis_url),
            cache_ttl_hours=int(e("CACHE_TTL_HOURS", cls.cache_ttl_hours)),
            apk_cache_ttl_hours=int(e("APK_CACHE_TTL_HOURS", cls.apk_cache_ttl_hours)),
            data_dir=Path(e("DATA_DIR", "./data")),
            fdroid_index_url=e("FDROID_INDEX_URL", cls.fdroid_index_url),
            androzoo_api_key=e("ANDROZOO_API_KEY") or None,
            androzoo_csv=Path(e("ANDROZOO_CSV")) if e("ANDROZOO_CSV") else None,
            max_apk_bytes=int(e("MAX_APK_BYTES", cls.max_apk_bytes)),
            enable_emulator=e("ENABLE_EMULATOR", "0") == "1",
            adb_serial=e("ADB_SERIAL") or None,
            analyzers=_csv(e("ANALYZERS")),
            findings_engine=e("FINDINGS_ENGINE") or None,
            cors_origins=_csv(e("CORS_ORIGINS", "http://localhost:5173")),
        )
