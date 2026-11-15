"""
Sentence -> privacy-category classifiers. All return the same shape so they are swappable:

    classify(sentences) -> list[list[Prediction]]     (multi-label; [] = not privacy-relevant)

  KeywordClassifier   offline, deterministic baseline with clause-aware negation   (Iteration 3)
  ZeroShotClassifier  Hugging Face BART-large-MNLI zero-shot                       (Iteration 3, optional)
  CascadeClassifier   primary model, falling back when it is unavailable
  (a DistilBERT / Legal-BERT model fine-tuned on OPP-115 plugs in as another primary in Iteration 5)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

from ..contract import TAXONOMY
from .text import clauses, is_negated


@dataclass(frozen=True)
class Prediction:
    category: str
    confidence: float
    polarity: str = "declares"          # "declares" | "denies"


class Classifier(Protocol):
    name: str

    def classify(self, sentences: Sequence[str]) -> list[list[Prediction]]: ...


_LEXICON: dict[str, re.Pattern] = {
    c: re.compile(p, re.I) for c, p in {
        "location": r"\b(gps|geo-?location|location (data|information|history|services)|(precise|approximate|exact|physical|current|your|device) location|geographic(al)? (location|position)|whereabouts|cell tower)\b",
        "camera": r"\b(camera|take (photos?|pictures?)|photographs?|scan(ning)? (a )?(qr|barcode))\b",
        "microphone": r"\b(microphone|record(ing)? (your )?(voice|audio|sound)|voice (recordings?|commands?|data)|audio (recordings?|data))\b",
        "contacts": r"\b(contacts?\b(?! us)|address ?book|phone ?book|contact list)",
        "identifiers": r"\b(advertising (id|identifier)|device (id|identifiers?)|android id|imei|unique (device )?identifiers?|mac address|ip address|identifiers?)\b",
        "analytics": r"\b(analytics|usage (data|statistics|information)|crash (reports?|logs?)|diagnostics?|performance data|how you (use|interact))\b",
        "advertising": r"\b(advertis\w*|ad (network|partners?|networks)|personali[sz]ed ads?|targeted ads?|interest-based|marketing (partners?|purposes?))\b",
        "storage": r"\b((external|device|local) storage|files? (and|or) (documents?|media)|media files|photos, media)\b",
        "phone_sms": r"\b(sms|text messages?|call (log|history|records?)|phone number|phone state)\b",
        "calendar": r"\b(calendar( events?| data| information)?)\b",
    }.items()
}
assert set(_LEXICON) == set(TAXONOMY), "lexicon must cover the whole taxonomy"


class KeywordClassifier:
    name = "keyword"
    CONFIDENCE = 0.7

    def classify(self, sentences: Sequence[str]) -> list[list[Prediction]]:
        out: list[list[Prediction]] = []
        for sentence in sentences:
            preds: dict[str, Prediction] = {}
            for clause in clauses(sentence):
                negated = is_negated(clause)
                for category, pattern in _LEXICON.items():
                    if pattern.search(clause):
                        polarity = "denies" if negated else "declares"
                        prev = preds.get(category)
                        # a 'declares' clause wins if the same sentence both denies and declares
                        if prev is None or polarity == "declares":
                            preds[category] = Prediction(category, self.CONFIDENCE, polarity)
            out.append(list(preds.values()))
        return out


class ZeroShotClassifier:
    """facebook/bart-large-mnli via transformers (downloads ~1.6 GB on first use)."""

    name = "zeroshot"
    LABELS = {
        "location": "location", "camera": "camera or photos", "microphone": "microphone or audio recording",
        "contacts": "contacts", "identifiers": "device identifiers", "analytics": "analytics or usage data",
        "advertising": "advertising", "storage": "files and storage", "phone_sms": "SMS or phone calls",
        "calendar": "calendar",
    }

    def __init__(self, model: str = "facebook/bart-large-mnli", threshold: float = 0.8, batch_size: int = 16):
        self.model, self.threshold, self.batch_size = model, threshold, batch_size
        self._pipe = None

    def _load(self):
        if self._pipe is None:
            from transformers import pipeline  # lazy: heavy import

            self._pipe = pipeline("zero-shot-classification", model=self.model)
        return self._pipe

    def classify(self, sentences: Sequence[str]) -> list[list[Prediction]]:
        if not sentences:
            return []
        pipe = self._load()
        by_text = {v: k for k, v in self.LABELS.items()}
        results = pipe(list(sentences), candidate_labels=list(by_text), multi_label=True,
                       hypothesis_template="This text is about the app using the user's {}.",
                       batch_size=self.batch_size)
        if isinstance(results, dict):          # single input -> single dict
            results = [results]
        out = []
        for sentence, res in zip(sentences, results):
            # polarity is judged per sentence here (coarser than the keyword path); see README
            polarity = "denies" if is_negated(sentence) else "declares"
            out.append([Prediction(by_text[label], float(score), polarity)
                        for label, score in zip(res["labels"], res["scores"]) if score >= self.threshold])
        return out


class CascadeClassifier:
    """Use `primary`; if it cannot run (model missing, no network) fall back to `fallback`."""

    def __init__(self, primary: Classifier, fallback: Classifier):
        self.primary, self.fallback = primary, fallback
        self.name = f"{primary.name}->{fallback.name}"
        self.used: Optional[str] = None

    def classify(self, sentences: Sequence[str]) -> list[list[Prediction]]:
        try:
            result = self.primary.classify(sentences)
            self.used = self.primary.name
            return result
        except Exception:  # noqa: BLE001 - ImportError, OSError (download), RuntimeError (OOM)...
            self.used = self.fallback.name
            return self.fallback.classify(sentences)


def build_classifier(kind: str = "keyword") -> Classifier:
    if kind == "keyword":
        return KeywordClassifier()
    if kind == "zeroshot":
        return ZeroShotClassifier()
    if kind == "auto":
        return CascadeClassifier(ZeroShotClassifier(), KeywordClassifier())
    raise ValueError(f"unknown classifier kind: {kind!r} (keyword | zeroshot | auto)")
