from pathlib import Path

from privacylens_analysis.entry import analyze_policy, analyze_static
from privacylens_analysis.nlp.classifier import (CascadeClassifier, KeywordClassifier, Prediction,
                                                 ZeroShotClassifier, build_classifier)
from privacylens_analysis.nlp.fetch import extract_text, is_safe_url
from privacylens_analysis.nlp.policy import policy_text_to_evidence
from privacylens_analysis.nlp.text import html_to_text, is_negated, split_sentences

FIX = Path(__file__).parent / "fixtures"


def preds(sentence):
    return {p.category: p.polarity for p in KeywordClassifier().classify([sentence])[0]}


def test_html_cleaning_drops_scripts_nav_and_footer():
    text = html_to_text((FIX / "sample_policy.html").read_text())
    assert "precise location" in text
    assert "var x" not in text and "Home | About" not in text and "cookies" not in text


def test_sentence_splitting_keeps_sentence_sized_pieces():
    s = split_sentences("Short.\nWe collect your location when you open the app. We never sell it to anyone at all!")
    assert s == ["We collect your location when you open the app.", "We never sell it to anyone at all!"]


def test_negation_detection():
    assert is_negated("We do not collect your contacts")
    assert is_negated("We don't share data")
    assert is_negated("We never record audio")
    assert not is_negated("We collect your location")


def test_keyword_classifier_polarity_and_clauses():
    assert preds("We collect your precise location from GPS.") == {"location": "declares"}
    assert preds("We do not collect your contacts or address book information.") == {"contacts": "denies"}
    # negation applies only to the clause it is in
    both = preds("We do not sell your data, but we collect crash reports and diagnostics.")
    assert both == {"analytics": "declares"}
    assert preds("We share your advertising ID with advertising partners for personalized ads.") == \
        {"identifiers": "declares", "advertising": "declares"}
    assert preds("Contact us at privacy@example.com for questions.") == {}      # 'contact us' is not 'contacts'


def test_policy_pipeline_on_fixture():
    text = html_to_text((FIX / "sample_policy.html").read_text())
    rows = policy_text_to_evidence(text, KeywordClassifier(), url="https://example.com/privacy")
    got = {(r["category"], r["polarity"]) for r in rows}
    assert ("location", "declares") in got and ("analytics", "declares") in got
    assert ("advertising", "declares") in got and ("identifiers", "declares") in got
    assert ("contacts", "denies") in got and ("microphone", "denies") in got
    assert ("contacts", "declares") not in got
    assert all(r["source"] == "policy" and r["meta"]["classifier"] == "keyword" for r in rows)


def test_per_category_cap():
    text = "\n".join(f"We collect your location data in situation number {i}." for i in range(30))
    rows = policy_text_to_evidence(text, KeywordClassifier(), max_per_category=3)
    assert len(rows) == 3


class Boom:
    name = "boom"

    def classify(self, sentences):
        raise ImportError("no transformers")


def test_cascade_falls_back_when_primary_is_unavailable():
    c = CascadeClassifier(Boom(), KeywordClassifier())
    out = c.classify(["We collect your location data."])
    assert out[0][0].category == "location" and c.used == "keyword"


def test_zeroshot_adapter_parses_pipeline_output():
    z = ZeroShotClassifier(threshold=0.8)
    z._pipe = lambda sents, **kw: [{"labels": ["location", "camera or photos"], "scores": [0.95, 0.2]} for _ in sents]
    out = z.classify(["We do not collect your location."])
    assert out == [[Prediction("location", 0.95, "denies")]]


def test_build_classifier_validation():
    import pytest
    with pytest.raises(ValueError):
        build_classifier("magic")
    assert build_classifier("auto").name == "zeroshot->keyword"


def test_ssrf_guard():
    public = lambda host, port: [(2, 1, 6, "", ("93.184.216.34", port))]
    private = lambda host, port: [(2, 1, 6, "", ("10.0.0.5", port))]
    loop = lambda host, port: [(2, 1, 6, "", ("127.0.0.1", port))]
    assert is_safe_url("https://example.com/privacy", resolver=public)
    assert not is_safe_url("https://intranet.local/x", resolver=private)
    assert not is_safe_url("http://localhost/x", resolver=loop)
    assert not is_safe_url("file:///etc/passwd", resolver=public)
    assert not is_safe_url("ftp://example.com/x", resolver=public)


def test_extract_text_fallback_without_trafilatura():
    assert "precise location" in extract_text((FIX / "sample_policy.html").read_text())


def test_entry_points_degrade_gracefully():
    assert analyze_static({"apk_path": None}) == {"evidence": [], "source_status": {}}
    assert analyze_policy({"privacy_policy_url": None}) == {"evidence": [], "source_status": {}}
    bad = analyze_static({"apk_path": "/no/such.apk"})
    assert bad["source_status"]["code"] == "failed:ApkReadError"
    unsafe = analyze_policy({"privacy_policy_url": "file:///etc/passwd"})
    assert unsafe["source_status"]["policy"] == "failed:FetchError"
