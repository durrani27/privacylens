import json
from pathlib import Path

import pytest

from consistency.contract import TAXONOMY, make_evidence as ev
from consistency.engine import CONSISTENT, INCONSISTENT, RULES, UNCERTAIN, evaluate
from consistency.service import build_findings

ALL = {"code": True, "datasafety": True, "policy": True, "reviews": True}
_n = 0


def row(source, polarity="declares", category="location", rtype=None, value="x"):
    global _n
    _n += 1
    raw_type = rtype or {"static": "permission", "sdk": "sdk", "datasafety": "data_safety_field",
                         "policy": "policy_sentence", "reviews": "review_sentence"}[source]
    r = ev(source, raw_type, value, category=category, polarity=polarity)
    r["id"] = f"id{_n}"
    return r


def verdict(rows, availability=ALL):
    (f,) = evaluate(rows, availability)
    return f["verdict"], f["rule_id"]


@pytest.mark.parametrize("rows,availability,expected", [
    # all three agree
    ([row("static"), row("datasafety"), row("policy")], ALL, (CONSISTENT, "R10-sources-agree")),
    # code + policy agree, label unavailable
    ([row("sdk"), row("policy")], {**ALL, "datasafety": False}, (CONSISTENT, "R10-sources-agree")),
    # used in code, missing from label
    ([row("static"), row("policy")], ALL, (INCONSISTENT, "R4-observed-not-in-datasafety")),
    # used in code + on label, silent policy
    ([row("static"), row("datasafety")], ALL, (INCONSISTENT, "R5-observed-not-in-policy")),
    # label only, silent policy, code looked and found nothing -> R6 outranks R8
    ([row("datasafety")], ALL, (INCONSISTENT, "R6-datasafety-not-in-policy")),
    # policy denies but code uses it
    ([row("static"), row("policy", "denies")], ALL, (INCONSISTENT, "R2-policy-denies-but-observed")),
    # policy admits collection, label silent, no code
    ([row("policy")], ALL, (INCONSISTENT, "R7-policy-not-in-datasafety")),
    # declared on label + policy but code found nothing
    ([row("datasafety"), row("policy")], ALL, (UNCERTAIN, "R8-declared-not-observed")),
    # denial confirmed
    ([row("policy", "denies")], ALL, (CONSISTENT, "R9-denial-confirmed")),
    # policy contradicts itself
    ([row("policy"), row("policy", "denies")], ALL, (UNCERTAIN, "R3-policy-mixed-statements")),
    # reviews are only a signal
    ([row("reviews")], ALL, (UNCERTAIN, "R11-reviews-only")),
    # only one verifiable source available
    ([row("static")], {"code": True, "datasafety": False, "policy": False, "reviews": True},
     (UNCERTAIN, "R1-insufficient-sources")),
])
def test_rule_table(rows, availability, expected):
    assert verdict(rows, availability) == expected


def test_reviews_never_change_a_verdict_but_are_mentioned():
    base = [row("static"), row("datasafety"), row("policy")]
    (plain,) = evaluate(base, ALL)
    (with_reviews,) = evaluate(base + [row("reviews"), row("reviews")], ALL)
    assert plain["verdict"] == with_reviews["verdict"] == CONSISTENT
    assert "2 user review(s)" in with_reviews["explanation"]
    assert len(with_reviews["evidence_ids"]) == 5


def test_every_finding_links_back_to_its_evidence():
    rows = [row("static"), row("policy", "denies")]
    (f,) = evaluate(rows, ALL)
    assert set(f["evidence_ids"]) == {r["id"] for r in rows}


def test_categories_without_evidence_are_omitted_and_sorted_worst_first():
    rows = [row("static", category="camera"), row("datasafety", category="camera"), row("policy", category="camera"),
            row("static", category="location"), row("policy", category="location")]
    out = evaluate(rows, ALL)
    assert [f["category"] for f in out] == ["location", "camera"]        # inconsistent first, consistent last
    assert {f["category"] for f in out} <= set(TAXONOMY)


def test_rule_table_is_well_formed():
    ids = [r.id for r in RULES]
    assert len(ids) == len(set(ids)) and ids[-1] == "R12-fallback"


def test_sample_scan_end_to_end():
    payload = json.loads((Path(__file__).parents[1] / "sample" / "sample_scan.json").read_text())
    findings = {f["category"]: (f["verdict"], f["rule_id"]) for f in build_findings(payload)}
    assert findings == {
        "camera": (INCONSISTENT, "R4-observed-not-in-datasafety"),
        "contacts": (INCONSISTENT, "R2-policy-denies-but-observed"),
        "analytics": (INCONSISTENT, "R4-observed-not-in-datasafety"),
        "identifiers": (UNCERTAIN, "R8-declared-not-observed"),
        "phone_sms": (UNCERTAIN, "R11-reviews-only"),
        "location": (CONSISTENT, "R10-sources-agree"),
        "microphone": (CONSISTENT, "R9-denial-confirmed"),
        "advertising": (CONSISTENT, "R10-sources-agree"),
    }
