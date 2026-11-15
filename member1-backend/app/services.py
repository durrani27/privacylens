"""Service container shared by the API process and the Celery worker."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from importlib import import_module
from typing import Callable, Optional

from .acquisition.curated import AndroZooSource, FDroidSource
from .acquisition.data_safety import FileDataSafetyProvider, NodeDataSafetyProvider
from .acquisition.fallbacks import AdbEmulatorSource, UploadSource
from .acquisition.manager import AcquisitionManager
from .acquisition.play_store import GooglePlayScraperClient
from .config import Settings
from .db import Database
from .repository import Repository


def load_callable(path: str) -> Callable:
    """'package.module:function' -> function."""
    module_name, _, attr = path.partition(":")
    if not module_name or not attr:
        raise ValueError(f"expected 'module:function', got {path!r}")
    return getattr(import_module(module_name), attr)


@dataclass
class Services:
    settings: Settings
    db: Database
    repo: Repository
    play: object
    acquisition: AcquisitionManager
    analyzers: list = field(default_factory=list)       # each: fn(ctx: dict) -> dict
    engine: Optional[Callable] = None                   # fn({"evidence","availability"}) -> [finding]


def build_services(settings: Optional[Settings] = None) -> Services:
    s = settings or Settings.from_env()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(s.database_url)
    db.init_schema()
    play = GooglePlayScraperClient()

    sources: list = [
        FDroidSource(s.data_dir / "fdroid-index-v2.json", s.fdroid_index_url, s.fdroid_base_url, s.max_apk_bytes)
    ]
    if s.androzoo_api_key and s.androzoo_csv:
        sources.append(AndroZooSource(s.androzoo_csv, s.androzoo_api_key, s.max_apk_bytes))
    sources.append(UploadSource(s.data_dir / "uploads"))
    if s.enable_emulator:
        sources.append(AdbEmulatorSource(serial=s.adb_serial))

    acquisition = AcquisitionManager(
        play=play,
        ds_providers=[FileDataSafetyProvider(s.data_dir / "datasafety"), NodeDataSafetyProvider()],
        apk_sources=sources,
        apk_dir=s.data_dir / "apks",
        apk_cache_ttl_hours=s.apk_cache_ttl_hours,
    )
    return Services(
        settings=s,
        db=db,
        repo=Repository(db),
        play=play,
        acquisition=acquisition,
        analyzers=[load_callable(p) for p in s.analyzers],
        engine=load_callable(s.findings_engine) if s.findings_engine else None,
    )


@lru_cache(maxsize=1)
def get_services() -> Services:
    return build_services()
