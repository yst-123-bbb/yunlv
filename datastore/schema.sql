-- CloudTrip 数据层 Schema（幂等，可重复执行）

CREATE TABLE IF NOT EXISTS sync_batch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    city TEXT,
    category TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    total INTEGER DEFAULT 0,
    success INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS entity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    city TEXT NOT NULL,
    name TEXT NOT NULL,
    alias TEXT,
    canonical_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS field_value (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL REFERENCES entity(id),
    field_name TEXT NOT NULL,
    value_json TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT,
    confidence REAL NOT NULL DEFAULT 0.3,
    fetched_at TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 1,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    old_value_json TEXT,
    new_value_json TEXT,
    source TEXT NOT NULL,
    operator TEXT NOT NULL DEFAULT 'system',
    batch_id INTEGER,
    changed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER,
    field_name TEXT NOT NULL,
    proposed_value_json TEXT NOT NULL,
    current_value_json TEXT,
    reason TEXT NOT NULL,
    raw_excerpt TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewer_note TEXT
);

CREATE TABLE IF NOT EXISTS fetch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    url TEXT NOT NULL,
    status_code INTEGER,
    ok INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    error TEXT,
    fetched_at TEXT NOT NULL,
    batch_id INTEGER
);

CREATE TABLE IF NOT EXISTS kv_cache (
    key TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    value_json TEXT NOT NULL,
    expires_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS share_link (
    short_id TEXT PRIMARY KEY,
    session_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    session_id TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS city_comment (
    id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    target_type TEXT NOT NULL,
    author TEXT NOT NULL,
    text TEXT NOT NULL,
    likes INTEGER NOT NULL DEFAULT 0,
    source_url TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'xiaohongshu',
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_comment_target ON city_comment(target_type, target);

CREATE UNIQUE INDEX IF NOT EXISTS ux_field_current ON field_value(entity_id, field_name) WHERE is_current = 1;
CREATE INDEX IF NOT EXISTS ix_entity_city_type ON entity(city, type);
CREATE INDEX IF NOT EXISTS ix_review_status ON review_queue(status);