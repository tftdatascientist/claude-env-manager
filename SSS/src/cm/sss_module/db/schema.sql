-- SSS Module — LogStore schema
-- event-sourced: jeden rekord = jedno zdarzenie

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    ts          TEXT    NOT NULL,  -- ISO 8601, np. 2026-04-28T21:28:00
    round       INTEGER,           -- numer rundy SSS (NULL dla zdarzeń pre-round)
    kind        TEXT    NOT NULL,  -- 'round_start' | 'round_end' | 'script' | 'buffer' | 'task' | 'milestone' | 'spawn' | 'plan_change' | 'md_read'
    payload     TEXT,              -- JSON z detalami zdarzenia
    file_path   TEXT               -- opcjonalnie: plik którego dotyczy zdarzenie
);

CREATE INDEX IF NOT EXISTS idx_events_session  ON events (session_id);
CREATE INDEX IF NOT EXISTS idx_events_round    ON events (session_id, round);
CREATE INDEX IF NOT EXISTS idx_events_kind     ON events (kind);
CREATE INDEX IF NOT EXISTS idx_events_ts       ON events (ts);
