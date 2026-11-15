# PrivacyLens+ — Member 3: Normalisation, Consistency Engine & Dashboard

Evidence normalisation layer · rule-based **Consistency Engine** (Consistent / Potentially Inconsistent / Uncertain, every
verdict linked to its evidence) · React dashboard (submission, progress polling, verdict table, Recharts charts, evidence list).

This package is **self-contained**: the engine is plain Python (standard library only) and the dashboard talks to a
**mock API** that mirrors Member 1's real endpoints, so you can run everything without the other two members' code.

## What this package owns

| Area | Where |
|---|---|
| Shared taxonomy mapping (permissions, APIs, SDK categories, Data Safety types and purposes) | `consistency/normalizer.py` |
| Rule table R1–R12 and finding generation | `consistency/engine.py` |
| Plug-in entry point for Member 1 | `consistency/service.py` |
| CLI to run the engine on a saved scan | `consistency/cli.py` |
| Mock backend (same routes/JSON as the real API) | `mock_api/server.py` |
| React dashboard | `frontend/` |

## Folder structure

```
member3-engine-dashboard/
├── consistency/           contract.py, normalizer.py, engine.py, service.py, cli.py
├── sample/sample_scan.json   15 evidence rows covering all three verdicts
├── mock_api/server.py
├── tests/                 21 pytest tests
├── frontend/
│   ├── package.json · vite.config.js · index.html
│   └── src/  main.jsx · App.jsx · api.js · styles.css
│             components/ SubmitForm · ScanProgress · Charts · VerdictTable · EvidencePanel
│             lib/ witnesses.js (+ witnesses.test.js, 7 tests)
└── pytest.ini
```

## Setup

Python 3.11+ and Node 18+ (Node 20+ recommended).

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # the engine itself needs nothing but pytest for tests

cd frontend && npm install && cd ..
```

## Run

**Engine only (CLI):**

```bash
python -m consistency.cli sample/sample_scan.json
```

**Dashboard with the mock API** (two terminals):

```bash
# terminal 1: mock API on :8000 (a scan "runs" for ~6 s; send the query "fail" to see the error state)
python mock_api/server.py

# terminal 2: dashboard on http://localhost:5173
cd frontend && npm run dev
```

**Dashboard with Member 1's real backend:** stop the mock, start Member 1's API on port 8000 with
`FINDINGS_ENGINE=consistency.service:build_findings`; no frontend change is needed.

## Test

```bash
pytest -q                                  # engine + normaliser (21 tests)
cd frontend && npm test                    # dashboard helper logic (7 tests, no install needed)
```

## The verdict logic in one table

First matching rule wins. `code`, `datasafety` and `policy` are the verifiable sources; user reviews are shown but never change a verdict.

| Rule | Verdict | When |
|---|---|---|
| R1 | Uncertain | fewer than 2 verifiable sources available |
| R2 | Potentially inconsistent | policy denies the practice, but code or the Data Safety label shows it |
| R3 | Uncertain | policy both states and denies it |
| R4 | Potentially inconsistent | used in code, not on the Data Safety label |
| R5 | Potentially inconsistent | used in code, policy silent |
| R6 | Potentially inconsistent | on the label, policy silent |
| R7 | Potentially inconsistent | policy describes it, label does not declare it |
| R8 | Uncertain | declared, but no matching code found (server-side or obfuscated?) |
| R9 | Consistent | policy denies it and nothing contradicts that |
| R10 | Consistent | every available verifiable source agrees |
| R11 | Uncertain | only user reviews mention it |
| R12 | Uncertain | fallback |

## Integration contract

* **Engine input** (from Member 1): `{"evidence": [row + id…], "availability": {"code","datasafety","policy","reviews": bool}}`.
* **Engine output:** `[{"category","verdict","rule_id","explanation","evidence_ids"}]`, worst verdicts first.
* **Dashboard ↔ API:** `POST /api/scans`, `GET /api/scans/{id}` (polled every 2 s), `GET /api/scans/{id}/evidence`.
* Evidence rows follow `consistency/contract.py` (frozen in Iteration 1).

## Assumptions and known limits

* **The React components were not compiled or run in the environment where this package was written** (no package installs
  were possible). The Python engine, mock API and the dashboard's helper logic *were* executed and tested. Run
  `npm install && npm run dev` once and fix any typo-level issue first.
* The interactive **Evidence Graph** (`react-force-graph`) and **version-drift panel** are Iteration 6; today each verdict
  opens a plain evidence list.
* Categories with no evidence in any source are omitted rather than shown as a fourth verdict.
* Data Safety types outside the taxonomy (e.g. Financial info) are dropped by the normaliser; extend `DATA_SAFETY_CATEGORY_MAP`
  and `TAXONOMY` together, and bump the contract version.
