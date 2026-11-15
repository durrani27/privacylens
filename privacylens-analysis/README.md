# PrivacyLens+ — Member 2: Static Analysis, SDK Detection & Policy NLP

Androguard static analysis · Exodus Privacy tracker detection · privacy-policy fetching, cleaning and classification
(keyword baseline + Hugging Face zero-shot fallback; fine-tuned model slot for Iteration 5).

This package is **self-contained**: you can run it from the command line on a saved policy page or an extracted-facts file
without Member 1's backend or Member 3's engine. Member 1's pipeline calls it through two functions.

## What this package owns

| Area | Where |
|---|---|
| Androguard adapter → `ApkFacts` (permissions, bundled classes, sensitive API call sites) | `privacylens_analysis/static/apk_reader.py` |
| Sensitive-API watch-list | `static/sensitive_apis.py` |
| Exodus tracker/SDK signature matching | `static/sdk_signatures.py`, `data/exodus_seed.json` |
| Facts → contract evidence rows | `static/analyzer.py` |
| Policy fetch (SSRF-guarded) and cleaning | `nlp/fetch.py`, `nlp/text.py` |
| Sentence classifiers (keyword, zero-shot, cascade) with negation handling | `nlp/classifier.py` |
| Policy → evidence rows | `nlp/policy.py` |
| Plug-in entry points for Member 1 | `entry.py` |
| CLI | `cli.py` |

Taxonomy mapping (permission → "location", SDK → "advertising", …) is **Member 3's** normaliser. This package emits *raw*
evidence for code and SDKs, and taxonomy-labelled evidence for policy sentences (the classifier's label space *is* the taxonomy).

## Folder structure

```
member2-analysis/
├── privacylens_analysis/
│   ├── contract.py        shared interface contract v1.0 (identical in all 3 packages)
│   ├── entry.py           analyze_static(ctx), analyze_policy(ctx)  ← Member 1 calls these
│   ├── cli.py
│   ├── static/            apk_reader.py, sensitive_apis.py, sdk_signatures.py, analyzer.py
│   └── nlp/               fetch.py, text.py, classifier.py, policy.py
├── data/exodus_seed.json  small offline seed of trackers (replace with full DB, see below)
├── scripts/update_exodus.py
├── tests/                 pytest suite + fixtures (sample_policy.html, sample_facts.json)
└── requirements.txt · requirements-dev.txt · pytest.ini
```

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

Optional, for the zero-shot model (about 1.6 GB download on first use):

```bash
pip install transformers torch
```

Optional, full tracker database from Exodus Privacy:

```bash
python scripts/update_exodus.py
export EXODUS_SIGNATURES=data/exodus_full.json
```

## Run

Everything below works offline with the bundled fixtures:

```bash
# 1. Policy NLP on a saved HTML page (keyword classifier)
python -m privacylens_analysis.cli policy --file tests/fixtures/sample_policy.html

# 2. Static evidence + tracker detection from pre-extracted facts (no APK needed)
python -m privacylens_analysis.cli static --facts tests/fixtures/sample_facts.json --out evidence.json

# 3. On a real APK (needs androguard)
python -m privacylens_analysis.cli static --apk path/to/app.apk

# 4. Live policy URL, optionally with the zero-shot model
python -m privacylens_analysis.cli policy --url https://example.com/privacy --classifier auto
```

## Test

```bash
pytest -q
```

19 tests cover Dalvik-name conversion, API watch-list matching, signature prefix rules (`com.foo.ads` must not match
`com.foo.adsense`), facts → evidence, HTML cleaning, sentence splitting, clause-aware negation, classifier polarity, the
per-category cap, cascade fallback, the zero-shot output adapter, the SSRF guard and graceful failure of both entry points.

## Plug-in contract (called by Member 1)

```python
analyze_static(ctx) -> {"evidence": [...], "source_status": {"code": "ok" | "failed:<Error>"}}
analyze_policy(ctx) -> {"evidence": [...], "source_status": {"policy": "ok" | "failed:<Error>"}}
```

Set the classifier with `POLICY_CLASSIFIER=keyword|zeroshot|auto` (default `keyword`; `auto` = zero-shot with keyword fallback).

## Assumptions and known limits

* **Androguard, httpx, trafilatura and transformers are thin adapters** that load lazily. The pure logic around them is
  unit-tested; validate the adapters on real APKs and policy pages during Iteration 2/3 acceptance.
* Only **method calls** are detected in code. Field reads (e.g. `ContactsContract` constants) are covered via permissions.
* The keyword classifier is a deterministic **baseline**, not the final model. The OPP-115 fine-tuned DistilBERT / Legal-BERT
  classifier arrives in Iteration 5 behind the same `classify()` interface.
* Zero-shot polarity (declares vs denies) is judged per sentence; the keyword path judges per clause.
* Review mining is not in this package yet (Iteration 5); it reuses the same classifier.
* The bundled tracker seed has 8 entries with illustrative ids; use the full Exodus export for real results.
