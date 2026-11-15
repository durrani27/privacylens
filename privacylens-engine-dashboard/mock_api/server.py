"""
Stand-alone mock of Member 1's API so the dashboard runs WITHOUT the real backend.

It exposes the same four routes and JSON shapes as the real API and answers with the sample scan
(sample/sample_scan.json) run through the REAL normaliser + Consistency Engine, so the verdicts
you see are genuine engine output. A scan "runs" for ~6 seconds (queued -> running -> done).

    python mock_api/server.py            # http://localhost:8000
    query "fail"  -> the scan ends in status "failed" (to test the error UI)
"""
from __future__ import annotations

import json
import re
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from consistency.service import build_findings  # noqa: E402

SAMPLE = json.loads((ROOT / "sample" / "sample_scan.json").read_text(encoding="utf-8"))
DURATION = 6.0
SCANS: dict[str, dict] = {}
PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")


def _package_from(query: str) -> str:
    m = re.search(r"[?&]id=([\w.]+)", query)
    if m:
        return m.group(1)
    return query if PACKAGE_RE.match(query) else SAMPLE["package"]


def _view(scan_id: str) -> dict:
    scan = SCANS[scan_id]
    elapsed = time.time() - scan["t0"]
    view = {"scan_id": scan_id, "package": scan["package"], "title": "Demo Fitness (mock data)",
            "developer": "Mock Developer", "app_version": "2.4.1", "created_at": scan["created_at"],
            "error": None, "source_status": SAMPLE["availability"] and
            {"code": "ok", "datasafety": "ok", "policy": "ok", "reviews": "ok", "apk_source": "mock"},
            "findings": []}
    if elapsed < 1.0:
        view.update(status="queued", stage="queued", progress=0)
    elif elapsed < DURATION:
        view.update(status="running", stage="analysis", progress=min(95, int(elapsed / DURATION * 100)))
    elif scan["fail"]:
        view.update(status="failed", stage="analysis", progress=40, error="RuntimeError: mock failure")
    else:
        findings = build_findings({"evidence": SAMPLE["evidence"], "availability": SAMPLE["availability"]})
        view.update(status="done", stage="finished", progress=100,
                    findings=[{"id": f"f{i}", "scan_id": scan_id, **f} for i, f in enumerate(findings)])
    return view


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):  # CORS preflight
        self._send(204, {})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/health":
            return self._send(200, {"status": "ok", "queue": "mock"})
        m = re.fullmatch(r"/api/scans/([\w-]+)(/evidence)?", path)
        if m and m.group(1) in SCANS:
            if m.group(2):
                return self._send(200, [{**e, "scan_id": m.group(1)} for e in SAMPLE["evidence"]])
            return self._send(200, _view(m.group(1)))
        self._send(404, {"detail": "Not found"})

    def do_POST(self):
        if self.path != "/api/scans":
            return self._send(404, {"detail": "Not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            query = str(body.get("query", "")).strip()
        except ValueError:
            return self._send(422, {"detail": "Invalid JSON"})
        if not query:
            return self._send(422, {"detail": "Empty query"})
        scan_id = uuid.uuid4().hex
        SCANS[scan_id] = {"t0": time.time(), "package": _package_from(query), "fail": query == "fail",
                          "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self._send(202, {"scan_id": scan_id, "package": SCANS[scan_id]["package"],
                         "status": "queued", "cached": False})

    def log_message(self, fmt, *args):  # quiet
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Mock PrivacyLens+ API on http://127.0.0.1:8000  (Ctrl+C to stop)")
    server.serve_forever()
