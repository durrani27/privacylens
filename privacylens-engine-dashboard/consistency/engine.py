"""
Consistency Engine - a transparent, ordered rule table (plain if/else logic, NOT another model).

For each taxonomy category that has any evidence, the engine summarises what each witness says:

    code        True/False   code evidence exists (permission, API call or tracker SDK); None = APK unavailable
    datasafety  True/False   category declared on the Play Store label;                None = label unavailable
    policy      "declares" | "denies" | "both" | "silent";                               None = policy unavailable
    reviews     int          number of user complaints (an UNVERIFIED signal; never changes a verdict)

The FIRST rule whose condition holds decides the verdict, and every verdict records its rule id
and the ids of the evidence rows behind it (these power the Evidence Graph).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from .contract import TAXONOMY

CONSISTENT = "consistent"
INCONSISTENT = "potentially_inconsistent"
UNCERTAIN = "uncertain"
VERDICT_ORDER = {INCONSISTENT: 0, UNCERTAIN: 1, CONSISTENT: 2}

LABEL = {
    "location": "Location", "camera": "Camera", "microphone": "Microphone", "contacts": "Contacts",
    "identifiers": "Device identifiers", "analytics": "Analytics", "advertising": "Advertising",
    "storage": "Files and storage", "phone_sms": "Phone and SMS", "calendar": "Calendar",
}


@dataclass
class Signals:
    category: str
    code: Optional[bool]
    datasafety: Optional[bool]
    policy: Optional[str]
    reviews: int
    ids: list[str] = field(default_factory=list)
    code_items: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return LABEL[self.category]

    def available(self) -> list[tuple[str, bool]]:
        """(witness, supports-the-category) for the verifiable witnesses that are available."""
        out = []
        if self.code is not None:
            out.append(("code", self.code))
        if self.datasafety is not None:
            out.append(("datasafety", self.datasafety))
        if self.policy is not None:
            out.append(("policy", self.policy == "declares"))
        return out


@dataclass(frozen=True)
class Rule:
    id: str
    verdict: str
    when: Callable[[Signals], bool]
    why: Callable[[Signals], str]


def _all_agree(s: Signals) -> bool:
    flags = [present for _, present in s.available()]
    return len(flags) >= 2 and all(flags)


RULES: list[Rule] = [
    Rule("R1-insufficient-sources", UNCERTAIN,
         lambda s: len(s.available()) < 2,
         lambda s: f"Fewer than two verifiable sources (code, Data Safety label, privacy policy) were available, "
                   f"so {s.label} cannot be cross-checked."),
    Rule("R2-policy-denies-but-observed", INCONSISTENT,
         lambda s: s.policy == "denies" and bool(s.code or s.datasafety),
         lambda s: f"The privacy policy says the app does not collect or use {s.label}, but "
                   f"{'the app code uses it' if s.code else 'the Data Safety label declares it'}."),
    Rule("R3-policy-mixed-statements", UNCERTAIN,
         lambda s: s.policy == "both",
         lambda s: f"The privacy policy both states and denies collection of {s.label}; a human should read it."),
    Rule("R4-observed-not-in-datasafety", INCONSISTENT,
         lambda s: bool(s.code) and s.datasafety is False,
         lambda s: f"{s.label} is used by the app ({', '.join(s.code_items[:3])}) but is not declared on the "
                   f"Play Store Data Safety label."),
    Rule("R5-observed-not-in-policy", INCONSISTENT,
         lambda s: bool(s.code) and s.policy == "silent",
         lambda s: f"{s.label} is used by the app ({', '.join(s.code_items[:3])}) but the privacy policy does not mention it."),
    Rule("R6-datasafety-not-in-policy", INCONSISTENT,
         lambda s: bool(s.datasafety) and s.policy == "silent",
         lambda s: f"{s.label} is declared on the Data Safety label but the privacy policy does not mention it."),
    Rule("R7-policy-not-in-datasafety", INCONSISTENT,
         lambda s: s.policy == "declares" and s.datasafety is False,
         lambda s: f"The privacy policy describes {s.label} collection but the Data Safety label does not declare it."),
    Rule("R8-declared-not-observed", UNCERTAIN,
         lambda s: bool(s.datasafety or s.policy == "declares") and s.code is False,
         lambda s: f"{s.label} is declared, but static analysis found no matching code. It may happen server-side "
                   f"or be hidden by obfuscation."),
    Rule("R9-denial-confirmed", CONSISTENT,
         lambda s: s.policy == "denies",
         lambda s: f"The policy denies {s.label} use and no other available source contradicts it."),
    Rule("R10-sources-agree", CONSISTENT,
         _all_agree,
         lambda s: f"All available sources agree that the app handles {s.label}."),
    Rule("R11-reviews-only", UNCERTAIN,
         lambda s: s.reviews > 0 and not any(p for _, p in s.available()),
         lambda s: f"Only user reviews mention {s.label}. Reviews are an unverified signal."),
    Rule("R12-fallback", UNCERTAIN,
         lambda s: True,
         lambda s: f"The available evidence about {s.label} is not enough to decide."),
]


def _signals(category: str, rows: list[dict], availability: dict) -> Signals:
    code_rows = [r for r in rows if r["source"] in ("static", "sdk")]
    ds_rows = [r for r in rows if r["source"] == "datasafety"]
    pol = [r for r in rows if r["source"] == "policy"]
    declares = any(r.get("polarity", "declares") == "declares" for r in pol)
    denies = any(r.get("polarity") == "denies" for r in pol)

    policy: Optional[str] = None
    if availability.get("policy"):
        policy = "both" if declares and denies else "declares" if declares else "denies" if denies else "silent"
    return Signals(
        category=category,
        code=bool(code_rows) if availability.get("code") else None,
        datasafety=bool(ds_rows) if availability.get("datasafety") else None,
        policy=policy,
        reviews=sum(1 for r in rows if r["source"] == "reviews"),
        ids=sorted({r["id"] for r in rows if r.get("id")}),
        code_items=sorted({r["raw_value"].rsplit(".", 1)[-1] if r["raw_type"] == "permission"
                           else r["raw_value"] for r in code_rows}),
    )


def evaluate(normalized_rows: Iterable[dict], availability: dict) -> list[dict]:
    """Return one finding per category that has evidence, worst verdicts first."""
    by_category: dict[str, list[dict]] = {}
    for row in normalized_rows:
        by_category.setdefault(row["category"], []).append(row)

    findings = []
    for category in TAXONOMY:
        rows = by_category.get(category)
        if not rows:
            continue
        s = _signals(category, rows, availability)
        rule = next(r for r in RULES if r.when(s))          # R12 always matches
        explanation = rule.why(s)
        if s.reviews and rule.id != "R11-reviews-only":
            explanation += f" {s.reviews} user review(s) also raise this (unverified signal; not used for the verdict)."
        findings.append({
            "category": category, "verdict": rule.verdict, "rule_id": rule.id,
            "explanation": explanation, "evidence_ids": s.ids,
        })
    findings.sort(key=lambda f: (VERDICT_ORDER[f["verdict"]], TAXONOMY.index(f["category"])))
    return findings
