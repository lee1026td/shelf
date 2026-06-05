-- shelf metadata schema. Mirrors SCHEMA.md §1 exactly.
-- SQLite has no native array/JSON column type; JSON-typed columns are TEXT holding
-- json.dumps(...) output. All timestamps are ISO-8601 UTC strings.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topics (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    slug             TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    intent           TEXT,
    status           TEXT NOT NULL DEFAULT 'active',
    collections      TEXT,   -- JSON array
    discovery_policy TEXT,   -- JSON object
    output_policy    TEXT,   -- JSON object
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    url               TEXT NOT NULL,
    name              TEXT,
    role              TEXT,
    status            TEXT NOT NULL DEFAULT 'candidate',
    topic_id          INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    relevance         REAL,
    authority         REAL,
    originality       REAL,
    freshness         REAL,
    update_frequency  REAL,
    extractability    REAL,
    uniqueness        REAL,
    noise_risk        REAL,
    watchability      REAL,
    extraction_health TEXT,
    discovered_from   TEXT,   -- JSON object {topic, run_id}
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status);
CREATE INDEX IF NOT EXISTS idx_sources_topic ON sources(topic_id);

CREATE TABLE IF NOT EXISTS items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    title        TEXT,
    url          TEXT,
    published_at TEXT,
    captured_at  TEXT NOT NULL,
    summary      TEXT,
    novelty      REAL,
    status       TEXT NOT NULL DEFAULT 'new',
    local_path   TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_id);

CREATE TABLE IF NOT EXISTS item_topics (
    item_id  INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, topic_id)
);

CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    item_id         INTEGER REFERENCES items(id) ON DELETE CASCADE,
    hash            TEXT NOT NULL,
    raw_path        TEXT,
    normalized_path TEXT,
    fetched_at      TEXT NOT NULL,
    parser_version  TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_hash ON snapshots(hash);

CREATE TABLE IF NOT EXISTS claims (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_text    TEXT NOT NULL,
    topic_id      INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    evidence_refs TEXT,   -- JSON array
    confidence    REAL,
    stale_status  TEXT NOT NULL DEFAULT 'fresh',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    type             TEXT NOT NULL,
    priority         TEXT NOT NULL DEFAULT 'normal',
    status           TEXT NOT NULL DEFAULT 'pending',
    title            TEXT,
    suggested_action TEXT,
    evidence         TEXT,   -- JSON
    ref_kind         TEXT,
    ref_id           INTEGER,
    local_ref        TEXT,
    notion_ref       TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_status ON review_items(status);
CREATE INDEX IF NOT EXISTS idx_review_priority ON review_items(priority);

CREATE TABLE IF NOT EXISTS compilations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    topic_id     INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    kind         TEXT,
    source_count INTEGER DEFAULT 0,
    confidence   REAL,
    output_path  TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watch_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id        INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    sources_checked INTEGER DEFAULT 0,
    new_items       INTEGER DEFAULT 0,
    changes         INTEGER DEFAULT 0,
    failures        INTEGER DEFAULT 0,
    cost            REAL,
    model_used      TEXT,
    status          TEXT NOT NULL DEFAULT 'completed'
);
