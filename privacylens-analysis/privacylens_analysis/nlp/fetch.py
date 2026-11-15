"""Fetch a privacy-policy page and reduce it to clean text (httpx + trafilatura, with fallbacks)."""
from __future__ import annotations

import ipaddress
import socket
from typing import Callable, Optional
from urllib.parse import urlparse

from .text import clean_text, html_to_text

USER_AGENT = "PrivacyLensPlus/0.1 (university final-year project)"
MAX_BYTES = 5 * 1024 * 1024


class FetchError(RuntimeError):
    pass


def is_safe_url(url: str, resolver: Callable = socket.getaddrinfo) -> bool:
    """Reject non-http(s) URLs and hosts that resolve to private/loopback/link-local addresses (SSRF guard)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        infos = resolver(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def extract_text(html: str) -> str:
    """trafilatura when available (best boilerplate removal), stdlib parser otherwise."""
    try:
        import trafilatura

        text = trafilatura.extract(html, include_comments=False, include_tables=False)
        if text and len(text) > 200:
            return clean_text(text)
    except ImportError:
        pass
    return html_to_text(html)


def fetch_policy_text(url: str, timeout: float = 15.0) -> str:
    if not is_safe_url(url):
        raise FetchError("refusing to fetch unsafe or non-public URL")
    try:
        import httpx
    except ImportError as exc:
        raise FetchError("httpx is not installed (pip install httpx)") from exc
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(url)
            resp.raise_for_status()
            if len(resp.content) > MAX_BYTES:
                raise FetchError("policy page too large")
            return extract_text(resp.text)
    except httpx.HTTPError as exc:
        raise FetchError(f"{type(exc).__name__}: {exc}") from exc
