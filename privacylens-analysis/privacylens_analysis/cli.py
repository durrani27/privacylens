"""
Command line for running Member 2's work stand-alone (no backend needed).

  python -m privacylens_analysis.cli static --facts tests/fixtures/sample_facts.json
  python -m privacylens_analysis.cli static --apk path/to/app.apk            # needs androguard
  python -m privacylens_analysis.cli policy --file tests/fixtures/sample_policy.html
  python -m privacylens_analysis.cli policy --url https://example.com/privacy # needs httpx
Add  --out evidence.json  to write the contract evidence rows to a file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .nlp.classifier import build_classifier
from .nlp.fetch import extract_text, fetch_policy_text
from .nlp.policy import policy_text_to_evidence
from .static.analyzer import analyze_apk, facts_to_evidence
from .static.apk_reader import ApkFacts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="privacylens_analysis")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("static", help="permissions, sensitive API calls and tracker SDKs")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--apk")
    g.add_argument("--facts", help="pre-extracted ApkFacts JSON (demo without an APK)")

    p = sub.add_parser("policy", help="classify a privacy policy")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--url")
    g.add_argument("--file", help="saved policy HTML or text file")
    p.add_argument("--classifier", default="keyword", choices=["keyword", "zeroshot", "auto"])

    for sp in (s, p):
        sp.add_argument("--out", help="write evidence JSON here")

    args = ap.parse_args(argv)
    if args.cmd == "static":
        rows = analyze_apk(args.apk) if args.apk else facts_to_evidence(ApkFacts.from_json_file(args.facts))
    else:
        if args.url:
            text = fetch_policy_text(args.url)
        else:
            raw = Path(args.file).read_text(encoding="utf-8")
            text = extract_text(raw) if "<" in raw[:2000] else raw
        rows = policy_text_to_evidence(text, build_classifier(args.classifier), url=args.url)

    payload = json.dumps(rows, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"wrote {len(rows)} evidence rows to {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
