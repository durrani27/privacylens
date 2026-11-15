"""Policy text cleaning and sentence splitting (pure Python, no model needed)."""
from __future__ import annotations

import re
from html.parser import HTMLParser

_SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "header", "svg", "form"}
_BLOCK_TAGS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "ul", "ol"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """Fallback extractor used when `trafilatura` is not installed."""
    parser = _TextExtractor()
    parser.feed(html)
    return clean_text("".join(parser.parts))


def clean_text(text: str) -> str:
    text = text.replace(" ", " ").replace("’", "'").replace("‘", "'")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+(?=[A-Z0-9\"'(\[])")
MIN_LEN, MAX_LEN = 25, 600


def split_sentences(text: str) -> list[str]:
    """Split on line breaks and sentence punctuation, keeping only sentence-sized pieces."""
    sentences: list[str] = []
    for line in clean_text(text).split("\n"):
        for piece in _SENT_SPLIT.split(line.strip()):
            piece = piece.strip(" -*•\t")
            if MIN_LEN <= len(piece) <= MAX_LEN:
                sentences.append(piece)
    return sentences


_NEGATION = re.compile(
    r"\b(?:do|does|did|will|shall|would|can|could)\s*(?:not|n't)\b"
    r"|\b(?:don't|doesn't|won't|cannot|can't)\b"
    r"|\bnever\b|\bno\s+(?:\w+\s+){0,3}(?:is|are|will be)\s+(?:collected|stored|shared|accessed)\b"
    r"|\bwithout\s+(?:collecting|accessing|storing|sharing|recording)\b"
    r"|\bnot\s+(?:collect|share|sell|store|access|track|record|use|transmit)\b",
    re.I,
)
_CLAUSE_SPLIT = re.compile(r"\bbut\b|\bhowever\b|\bexcept\b|;|\balthough\b|\bwhile\b", re.I)


def clauses(sentence: str) -> list[str]:
    """Contrasting clauses are judged separately: 'we do not sell data, but we collect location'."""
    return [c.strip() for c in _CLAUSE_SPLIT.split(sentence) if c.strip()]


def is_negated(clause: str) -> bool:
    return bool(_NEGATION.search(clause))
