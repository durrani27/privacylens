"""
Public Play Store access (metadata + reviews) and input resolution.

Reading a public web page needs no installation, no login and nothing risky,
so this tier ALWAYS runs. The client is injected, so tests use a fake.
"""
from __future__ import annotations

import re
from typing import Optional, Protocol
from urllib.parse import parse_qs, urlparse

PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")


class PlayStoreClient(Protocol):
    def search(self, name: str) -> Optional[str]: ...
    def get_app(self, package: str) -> dict: ...
    def get_reviews(self, package: str, count: int = 200) -> list[dict]: ...


def resolve_query(query: str, client: Optional[PlayStoreClient] = None) -> str:
    """Turn what the user typed (Play link, package id, or app name) into a package id."""
    q = (query or "").strip()
    if not q:
        raise ValueError("Empty query")
    if q.startswith(("http://", "https://")):
        parsed = urlparse(q)
        if parsed.netloc.endswith("play.google.com"):
            pkg = (parse_qs(parsed.query).get("id") or [None])[0]
            if pkg and PACKAGE_RE.match(pkg):
                return pkg
        raise ValueError("Not a valid Google Play app link (expected ...details?id=<package>)")
    if PACKAGE_RE.match(q):
        return q
    if client is None:
        raise ValueError("App-name search needs a Play client")
    pkg = client.search(q)
    if not pkg:
        raise LookupError(f"No Play Store app found for {q!r}")
    return pkg


class GooglePlayScraperClient:
    """Adapter over the `google-play-scraper` Python package (imported lazily)."""

    def __init__(self, lang: str = "en", country: str = "us"):
        self.lang, self.country = lang, country

    def _lib(self):
        import google_play_scraper as gps

        return gps

    def search(self, name: str) -> Optional[str]:
        hits = self._lib().search(name, lang=self.lang, country=self.country, n_hits=1)
        return hits[0]["appId"] if hits else None

    def get_app(self, package: str) -> dict:
        r = self._lib().app(package, lang=self.lang, country=self.country)
        return {
            "title": r.get("title"),
            "developer": r.get("developer"),
            "version": r.get("version"),
            "privacy_policy_url": r.get("privacyPolicy"),
            "installs": r.get("installs"),
            "score": r.get("score"),
        }

    def get_reviews(self, package: str, count: int = 200) -> list[dict]:
        gps = self._lib()
        result, _token = gps.reviews(
            package, lang=self.lang, country=self.country, sort=gps.Sort.NEWEST, count=count
        )
        return [
            {
                "id": r.get("reviewId"),
                "text": r.get("content") or "",
                "score": r.get("score"),
                "at": r["at"].isoformat() if r.get("at") else None,
            }
            for r in result
        ]
