-- NEVA ПАМЯТЬ v3 — схема SQLite
-- Дата: 2026-06-28 | Архитектор: Claude | Директор: Серж
-- КРАСНАЯ ЗОНА: не менять без решения Директора

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ============================================================
-- ПОЛКА 1: ЧТО ПРОИСХОДИЛО (эпизоды, чаты, события, аудиты)
-- ============================================================
CREATE TABLE IF NOT EXISTS episodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    type        TEXT NOT NULL CHECK(type IN ('AUDIT','EVENT','CHAT','SESSION')),
    status      TEXT NOT NULL DEFAULT 'АКТУАЛЬНО'
                CHECK(status IN ('АКТУАЛЬНО','ОТМЕНЕНО','УСТАРЕЛО','ОБЪЕДИНЕНО','ТРЕБУЕТ_ПРОВЕРКИ','ОЖИДАЕТ_ВЕКТОРИЗАЦИИ')),
    importance  INTEGER NOT NULL DEFAULT 2 CHECK(importance BETWEEN 1 AND 5),
    source      TEXT NOT NULL,
    source_path TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    confirmed_at TEXT,
    embedding   BLOB,
    merged_into INTEGER REFERENCES episodes(id)
);

-- ============================================================
-- ПОЛКА 2: ЧТО ИЗВЕСТНО (факты, решения, архитектура)
-- ============================================================
CREATE TABLE IF NOT EXISTS facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    type        TEXT NOT NULL CHECK(type IN ('DECISION','FACT','ARCHITECTURE','COMPONENT')),
    status      TEXT NOT NULL DEFAULT 'АКТУАЛЬНО'
                CHECK(status IN ('АКТУАЛЬНО','ОТМЕНЕНО','УСТАРЕЛО','ОБЪЕДИНЕНО','ТРЕБУЕТ_ПРОВЕРКИ','ОЖИДАЕТ_ВЕКТОРИЗАЦИИ')),
    importance  INTEGER NOT NULL CHECK(importance BETWEEN 1 AND 5),
    source      TEXT NOT NULL,
    source_path TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    confirmed_at TEXT,
    embedding   BLOB,
    merged_into INTEGER REFERENCES facts(id)
);

-- ============================================================
-- ПОЛКА 3: КАК ДЕЛАТЬ (процедуры, инструкции, шаблоны)
-- ============================================================
CREATE TABLE IF NOT EXISTS procedures (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    type        TEXT NOT NULL CHECK(type IN ('PROCEDURE','TEMPLATE','RULE')),
    status      TEXT NOT NULL DEFAULT 'АКТУАЛЬНО'
                CHECK(status IN ('АКТУАЛЬНО','ОТМЕНЕНО','УСТАРЕЛО','ОБЪЕДИНЕНО','ТРЕБУЕТ_ПРОВЕРКИ','ОЖИДАЕТ_ВЕКТОРИЗАЦИИ')),
    importance  INTEGER NOT NULL CHECK(importance BETWEEN 1 AND 5),
    source      TEXT NOT NULL,
    source_path TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    confirmed_at TEXT,
    embedding   BLOB,
    merged_into INTEGER REFERENCES procedures(id)
);

-- ============================================================
-- ЛОГ ПОИСКОВЫХ ЗАПРОСОВ
-- ============================================================
CREATE TABLE IF NOT EXISTS search_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asked_by    TEXT NOT NULL,
    query       TEXT NOT NULL,
    level_found INTEGER,
    result_text TEXT,
    source      TEXT,
    importance  INTEGER,
    status      TEXT,
    duration_ms INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- ИНДЕКСЫ
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_facts_status    ON facts(status, importance);
CREATE INDEX IF NOT EXISTS idx_facts_type      ON facts(type);
CREATE INDEX IF NOT EXISTS idx_facts_source    ON facts(source_path);
CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes(status, importance);
CREATE INDEX IF NOT EXISTS idx_procedures_status ON procedures(status, importance);

-- Полнотекстовый поиск (FTS5)
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    text, source, content='facts', content_rowid='id'
);
CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
    text, source, content='episodes', content_rowid='id'
);
CREATE VIRTUAL TABLE IF NOT EXISTS procedures_fts USING fts5(
    text, source, content='procedures', content_rowid='id'
);

-- Триггеры синхронизации FTS
CREATE TRIGGER IF NOT EXISTS facts_fts_insert AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, text, source) VALUES (new.id, new.text, new.source);
END;
CREATE TRIGGER IF NOT EXISTS facts_fts_update AFTER UPDATE ON facts BEGIN
    DELETE FROM facts_fts WHERE rowid = old.id;
    INSERT INTO facts_fts(rowid, text, source) VALUES (new.id, new.text, new.source);
END;
CREATE TRIGGER IF NOT EXISTS episodes_fts_insert AFTER INSERT ON episodes BEGIN
    INSERT INTO episodes_fts(rowid, text, source) VALUES (new.id, new.text, new.source);
END;
CREATE TRIGGER IF NOT EXISTS procedures_fts_insert AFTER INSERT ON procedures BEGIN
    INSERT INTO procedures_fts(rowid, text, source) VALUES (new.id, new.text, new.source);
END;
