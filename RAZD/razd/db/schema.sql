CREATE TABLE IF NOT EXISTS processes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    category_id INTEGER REFERENCES categories(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT '#888888',
    is_productive INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS url_mappings (
    id INTEGER PRIMARY KEY,
    pattern TEXT NOT NULL UNIQUE,
    category_id INTEGER REFERENCES categories(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_decisions (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    subject_type TEXT NOT NULL CHECK (subject_type IN ('process', 'url')),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    decided_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    event_type TEXT NOT NULL,
    process_name TEXT,
    window_title TEXT,
    url TEXT,
    idle_seconds INTEGER NOT NULL DEFAULT 0,
    category_id INTEGER REFERENCES categories(id),
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_process ON events(process_name);
