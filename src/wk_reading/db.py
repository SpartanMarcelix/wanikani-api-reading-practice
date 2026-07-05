"""SQLite storage for WaniKani subjects and assignments.

Minimal by design (PLAN.md Phase 1): two tables, a few normalized columns for
querying, plus raw_json for anything we haven't normalized yet.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from wk_reading import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    id                   INTEGER PRIMARY KEY,
    object               TEXT NOT NULL,   -- 'kanji' | 'vocabulary'
    characters           TEXT,
    level                INTEGER,
    primary_reading      TEXT,
    primary_meaning      TEXT,
    meanings_json        TEXT,
    readings_json        TEXT,
    parts_of_speech_json TEXT,
    raw_json             TEXT,
    data_updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS assignments (
    id              INTEGER PRIMARY KEY,
    subject_id      INTEGER NOT NULL,
    subject_type    TEXT NOT NULL,   -- 'kanji' | 'vocabulary'
    srs_stage       INTEGER,
    started_at      TEXT,
    passed_at       TEXT,
    hidden          INTEGER NOT NULL DEFAULT 0,
    raw_json        TEXT,
    data_updated_at TEXT,
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);

CREATE INDEX IF NOT EXISTS idx_assignments_type_srs
    ON assignments (subject_type, srs_stage);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    config.ensure_data_dir()
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def upsert_subjects(conn: sqlite3.Connection, rows: list[dict]) -> int:
    conn.executemany(
        """
        INSERT INTO subjects (
            id, object, characters, level, primary_reading, primary_meaning,
            meanings_json, readings_json, parts_of_speech_json, raw_json,
            data_updated_at
        ) VALUES (
            :id, :object, :characters, :level, :primary_reading, :primary_meaning,
            :meanings_json, :readings_json, :parts_of_speech_json, :raw_json,
            :data_updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            object=excluded.object,
            characters=excluded.characters,
            level=excluded.level,
            primary_reading=excluded.primary_reading,
            primary_meaning=excluded.primary_meaning,
            meanings_json=excluded.meanings_json,
            readings_json=excluded.readings_json,
            parts_of_speech_json=excluded.parts_of_speech_json,
            raw_json=excluded.raw_json,
            data_updated_at=excluded.data_updated_at
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def upsert_assignments(conn: sqlite3.Connection, rows: list[dict]) -> int:
    conn.executemany(
        """
        INSERT INTO assignments (
            id, subject_id, subject_type, srs_stage, started_at, passed_at,
            hidden, raw_json, data_updated_at
        ) VALUES (
            :id, :subject_id, :subject_type, :srs_stage, :started_at, :passed_at,
            :hidden, :raw_json, :data_updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            subject_id=excluded.subject_id,
            subject_type=excluded.subject_type,
            srs_stage=excluded.srs_stage,
            started_at=excluded.started_at,
            passed_at=excluded.passed_at,
            hidden=excluded.hidden,
            raw_json=excluded.raw_json,
            data_updated_at=excluded.data_updated_at
        """,
        rows,
    )
    conn.commit()
    return len(rows)
