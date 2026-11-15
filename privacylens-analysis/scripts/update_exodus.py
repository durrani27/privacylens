"""Download the full Exodus Privacy tracker database into data/exodus_full.json.

Usage:  python scripts/update_exodus.py
Then point the analyzer at it:  export EXODUS_SIGNATURES=data/exodus_full.json
"""
import json
import sys
import urllib.request
from pathlib import Path

URL = "https://reports.exodus-privacy.eu.org/api/trackers"
OUT = Path(__file__).resolve().parents[1] / "data" / "exodus_full.json"

req = urllib.request.Request(URL, headers={"User-Agent": "PrivacyLensPlus/0.1 (university project)"})
with urllib.request.urlopen(req, timeout=60) as resp:
    data = json.load(resp)
if "trackers" not in data:
    sys.exit("Unexpected response shape: no 'trackers' key")
OUT.write_text(json.dumps(data), encoding="utf-8")
print(f"saved {len(data['trackers'])} trackers to {OUT}")
