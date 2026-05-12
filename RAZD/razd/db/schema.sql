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

CREATE TABLE IF NOT EXISTS focus_sessions (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_s INTEGER NOT NULL DEFAULT 0,
    score INTEGER,
    whitelist_snapshot TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS focus_process_samples (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES focus_sessions(id) ON DELETE CASCADE,
    ts TEXT NOT NULL,
    process_name TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_focus_samples_session ON focus_process_samples(session_id);

CREATE TABLE IF NOT EXISTS cc_sessions (
    id INTEGER PRIMARY KEY,
    project_path TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_s INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cc_snapshots (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES cc_sessions(id) ON DELETE CASCADE,
    ts TEXT NOT NULL,
    pid INTEGER NOT NULL,
    exe TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cc_snapshots_session ON cc_snapshots(session_id);
CREATE INDEX IF NOT EXISTS idx_cc_sessions_started ON cc_sessions(started_at);

CREATE TABLE IF NOT EXISTS break_events (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    minutes_worked INTEGER NOT NULL DEFAULT 0,
    event_type TEXT NOT NULL CHECK (event_type IN ('suggested', 'taken', 'skipped'))
);

CREATE TABLE IF NOT EXISTS distraction_events (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    switches_per_min REAL NOT NULL,
    duration_s INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_break_events_ts ON break_events(ts);
CREATE INDEX IF NOT EXISTS idx_distraction_events_ts ON distraction_events(ts);

CREATE TABLE IF NOT EXISTS web_visits (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    page_title TEXT,
    browser TEXT,
    category_id INTEGER REFERENCES categories(id),
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    visit_count INTEGER NOT NULL DEFAULT 1,
    total_time_s INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_web_visits_domain ON web_visits(domain);
CREATE INDEX IF NOT EXISTS idx_web_visits_last_seen ON web_visits(last_seen_at);

CREATE TABLE IF NOT EXISTS app_usage (
    id INTEGER PRIMARY KEY,
    process_name TEXT NOT NULL UNIQUE,
    exe_path TEXT,
    category_id INTEGER REFERENCES categories(id),
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    total_time_s INTEGER NOT NULL DEFAULT 0,
    focus_switches INTEGER NOT NULL DEFAULT 0,
    is_dev_tool INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_app_usage_last_seen ON app_usage(last_seen_at);

-- Projekty pobrane z Notion
CREATE TABLE IF NOT EXISTS notion_projects (
    id INTEGER PRIMARY KEY,
    notion_page_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT,
    priority TEXT,
    due_date TEXT,
    raw_properties TEXT NOT NULL DEFAULT '{}',  -- JSON z wszystkimi polami z Notion
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notion_projects_page_id ON notion_projects(notion_page_id);

-- Powiązanie sesji focus z projektem Notion lub projektem custom
CREATE TABLE IF NOT EXISTS focus_session_project (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL UNIQUE REFERENCES focus_sessions(id) ON DELETE CASCADE,
    notion_project_id INTEGER REFERENCES notion_projects(id),  -- NULL jeśli custom
    custom_project_name TEXT,                                   -- NULL jeśli z Notion
    notion_synced INTEGER NOT NULL DEFAULT 0,                   -- 1 po wysłaniu do Notion
    synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_fsp_session ON focus_session_project(session_id);
CREATE INDEX IF NOT EXISTS idx_fsp_project ON focus_session_project(notion_project_id);

-- Przypięte projekty priorytetowe (max 4, każdy z kolorem)
CREATE TABLE IF NOT EXISTS pinned_projects (
    slot        INTEGER PRIMARY KEY CHECK (slot BETWEEN 1 AND 4),
    project_id  INTEGER NOT NULL REFERENCES notion_projects(id) ON DELETE CASCADE,
    color       TEXT NOT NULL DEFAULT '#7C3AED'
);

-- Cache zadań z Notion
CREATE TABLE IF NOT EXISTS notion_tasks (
    id              INTEGER PRIMARY KEY,
    notion_page_id  TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Not started',
    deadline        TEXT,
    details         TEXT,
    project_page_id TEXT,           -- notion_page_id projektu (relacja)
    synced_at       TEXT NOT NULL DEFAULT (datetime('now')),
    dirty           INTEGER NOT NULL DEFAULT 0  -- 1 = zmiana lokalna czekająca na sync
);

CREATE INDEX IF NOT EXISTS idx_notion_tasks_project ON notion_tasks(project_page_id);
CREATE INDEX IF NOT EXISTS idx_notion_tasks_status  ON notion_tasks(status);
