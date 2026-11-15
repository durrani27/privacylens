"""Privacy-policy pipeline: text -> sentences -> classifier -> evidence rows."""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from ..contract import make_evidence
from .classifier import Classifier, KeywordClassifier
from .text import split_sentences


def policy_text_to_evidence(text: str, classifier: Optional[Classifier] = None, *, url: Optional[str] = None,
                            max_per_category: int = 8) -> list[dict]:
    """Classify every sentence; keep the strongest `max_per_category` per (category, polarity)."""
    classifier = classifier or KeywordClassifier()
    sentences = split_sentences(text)
    predictions = classifier.classify(sentences)

    candidates = []  # (confidence, index, sentence, prediction)
    for idx, (sentence, preds) in enumerate(zip(sentences, predictions)):
        for p in preds:
            candidates.append((p.confidence, idx, sentence, p))

    kept: dict[tuple[str, str], int] = defaultdict(int)
    rows = []
    for conf, idx, sentence, p in sorted(candidates, key=lambda c: (-c[0], c[1])):
        key = (p.category, p.polarity)
        if kept[key] >= max_per_category:
            continue
        kept[key] += 1
        rows.append(make_evidence(
            "policy", "policy_sentence", sentence[:500], snippet=sentence, category=p.category,
            polarity=p.polarity, confidence=round(conf, 3),
            meta={"url": url, "sentence_index": idx, "classifier": classifier.name}))
    rows.sort(key=lambda r: (r["category"], r["meta"]["sentence_index"]))
    return rows
