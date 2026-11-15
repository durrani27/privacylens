"""
Curated, free APK sources: the F-Droid index and AndroZoo.

Both are tried BEFORE anything riskier. Network I/O is isolated in `download_file`,
which is injectable so the lookup logic is fully unit-testable offline.
"""
from __future__ import annotations

import csv
import hashlib
import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

USER_AGENT = "PrivacyLensPlus/0.1 (university final-year project)"


def download_file(url: str, dest: Path, max_bytes: int, timeout: int = 60) -> str:
    """Stream `url` to `dest` (size-capped). Returns the SHA-256 hex digest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    sha, total = hashlib.sha256(), 0
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as out:
        while chunk := resp.read(1 << 16):
            total += len(chunk)
            if total > max_bytes:
                tmp.unlink(missing_ok=True)
                raise ValueError("download exceeds size cap")
            sha.update(chunk)
            out.write(chunk)
    tmp.replace(dest)
    return sha.hexdigest()


Downloader = Callable[[str, Path, int], str]


@dataclass
class ApkCandidate:
    source: str
    package: str
    version_code: int
    url: str
    sha256: Optional[str] = None


class FDroidSource:
    name = "fdroid"

    def __init__(self, index_path: Path, index_url: str, base_url: str, max_bytes: int,
                 ttl_hours: int = 24, downloader: Downloader = download_file):
        self.index_path, self.index_url, self.base_url = Path(index_path), index_url, base_url
        self.max_bytes, self.ttl_hours, self._download = max_bytes, ttl_hours, downloader
        self._index: Optional[dict] = None

    def _load_index(self) -> dict:
        if self._index is None:
            stale = (not self.index_path.exists()) or (
                time.time() - self.index_path.stat().st_mtime > self.ttl_hours * 3600
            )
            if stale:
                self._download(self.index_url, self.index_path, 512 * 1024 * 1024)
            self._index = json.loads(self.index_path.read_text(encoding="utf-8"))
        return self._index

    def lookup(self, package: str) -> Optional[ApkCandidate]:
        entry = (self._load_index().get("packages") or {}).get(package)
        if not entry:
            return None
        best = None
        for version in (entry.get("versions") or {}).values():
            file_info = version.get("file") or {}
            name = file_info.get("name")
            code = int((version.get("manifest") or {}).get("versionCode") or 0)
            if name and name.endswith(".apk") and (best is None or code > best[0]):
                best = (code, name, file_info.get("sha256"))
        if not best:
            return None
        return ApkCandidate("fdroid", package, best[0], self.base_url.rstrip("/") + "/" + best[1].lstrip("/"), best[2])

    def fetch(self, package: str, dest_dir: Path) -> Optional[Path]:
        cand = self.lookup(package)
        if cand is None:
            return None
        dest = Path(dest_dir) / f"{package}.apk"
        digest = self._download(cand.url, dest, self.max_bytes)
        if cand.sha256 and digest.lower() != cand.sha256.lower():
            dest.unlink(missing_ok=True)
            raise ValueError("F-Droid APK checksum mismatch")
        return dest


class AndroZooSource:
    """Looks a package up in a local copy of AndroZoo's latest.csv and downloads via its API.

    Needs an API key (free for academic use, by request). Tip: pre-filter latest.csv to the
    packages you study; scanning the full file linearly is slow.
    """

    name = "androzoo"
    DOWNLOAD_URL = "https://androzoo.uni.lu/api/download"

    def __init__(self, csv_path: Path, api_key: str, max_bytes: int, downloader: Downloader = download_file):
        self.csv_path, self.api_key, self.max_bytes, self._download = Path(csv_path), api_key, max_bytes, downloader

    def lookup(self, package: str) -> Optional[ApkCandidate]:
        best = None
        with open(self.csv_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("pkg_name") != package:
                    continue
                try:
                    code = int(row.get("vercode") or 0)
                except ValueError:
                    code = 0
                if best is None or code > best[0]:
                    best = (code, row.get("sha256", ""))
        if not best or not best[1]:
            return None
        url = f"{self.DOWNLOAD_URL}?apikey={self.api_key}&sha256={best[1]}"
        return ApkCandidate("androzoo", package, best[0], url, best[1])

    def fetch(self, package: str, dest_dir: Path) -> Optional[Path]:
        cand = self.lookup(package)
        if cand is None:
            return None
        dest = Path(dest_dir) / f"{package}.apk"
        digest = self._download(cand.url, dest, self.max_bytes)
        if cand.sha256 and digest.lower() != cand.sha256.lower():
            dest.unlink(missing_ok=True)
            raise ValueError("AndroZoo APK checksum mismatch")
        return dest
