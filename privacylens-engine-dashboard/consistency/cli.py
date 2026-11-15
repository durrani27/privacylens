"""
Run the normaliser + engine on a saved scan file.

    python -m consistency.cli sample/sample_scan.json
    python -m consistency.cli sample/sample_scan.json --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .service import build_findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="consistency")
    ap.add_argument("scan_file", help='JSON: {"evidence": [...], "availability": {...}}')
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    args = ap.parse_args(argv)
    payload = json.loads(Path(args.scan_file).read_text(encoding="utf-8"))
    findings = build_findings(payload)
    if args.json:
        print(json.dumps(findings, indent=2))
        return 0
    print(f"{'CATEGORY':<12} {'VERDICT':<26} RULE")
    for f in findings:
        print(f"{f['category']:<12} {f['verdict']:<26} {f['rule_id']}")
        print(f"    {f['explanation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
