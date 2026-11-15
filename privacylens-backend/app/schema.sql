-- PrivacyLens+ schema (portable across PostgreSQL 16 and SQLite).
-- Ids are application-generated UUID hex strings; JSON is stored as TEXT.
-- Iteration 8 plan: migrate JSON columns to JSONB and timestamps to TIMESTAMPTZ.

CREATE TABLE IF NOT EXISTS apps (
    package            TEXT PRIMARY KEY,
    title              TEXT,
    developer          TEXT,
    latest_version     TEXT,
    privacy_policy_url TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scans (
    id            TEXT PRIMARY KEY,
    package       TEXT NOT NULL REFERENCES apps(package),
    app_version   TEXT,
    status        TEXT NOT NULL,          -- queued | running | done | failed
    stage         TEXT,                   -- acquisition | analysis | findings | finished
    progress      INTEGER NOT NULL DEFAULT 0,
    error         TEXT,
    source_status TEXT,                   -- JSON: per-witness availability
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scans_package ON scans(package, created_at);

CREATE TABLE IF NOT EXISTS evidence (
    id         TEXT PRIMARY KEY,
    scan_id    TEXT NOT NULL REFERENCES scans(id),
    source     TEXT NOT NULL,
    raw_type   TEXT NOT NULL,
    raw_value  TEXT NOT NULL,
    category   TEXT,
    polarity   TEXT NOT NULL DEFAULT 'declares',
    confidence REAL,
    snippet    TEXT,
    meta       TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_scan ON evidence(scan_id);

CREATE TABLE IF NOT EXISTS findings (
    id           TEXT PRIMARY KEY,
    scan_id      TEXT NOT NULL REFERENCES scans(id),
    category     TEXT NOT NULL,
    verdict      TEXT NOT NULL,           -- consistent | potentially_inconsistent | uncertain
    rule_id      TEXT,
    explanation  TEXT,
    evidence_ids TEXT NOT NULL,           -- JSON array of evidence.id
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_findings_scan ON findings(scan_id);

CREATE TABLE IF NOT EXISTS snapshots (
    id          TEXT PRIMARY KEY,
    scan_id     TEXT NOT NULL REFERENCES scans(id),
    package     TEXT NOT NULL,
    app_version TEXT,
    payload     TEXT NOT NULL,            -- JSON: evidence + findings (used for version drift)
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_package ON snapshots(package, created_at);
