"""Full sync: pull started kanji+vocab assignments and their subjects into SQLite.

Phase 1 keeps this simple: a full sync every time (the pool is ~600 items).
Incremental sync via `updated_after` is deliberately deferred (see PLAN.md).
"""

from __future__ import annotations

import json

from wk_reading import db
from wk_reading.wanikani_client import WaniKaniClient


def _primary(items: list[dict], key: str) -> str | None:
    """Return the `key` of the entry marked primary (or the first entry)."""
    if not items:
        return None
    for item in items:
        if item.get("primary"):
            return item.get(key)
    return items[0].get(key)


def _subject_to_row(subject: dict) -> dict:
    data = subject.get("data", {})
    meanings = data.get("meanings", []) or []
    readings = data.get("readings", []) or []
    return {
        "id": subject["id"],
        "object": subject.get("object"),
        "characters": data.get("characters"),
        "level": data.get("level"),
        "primary_reading": _primary(readings, "reading"),
        "primary_meaning": _primary(meanings, "meaning"),
        "meanings_json": json.dumps(meanings, ensure_ascii=False),
        "readings_json": json.dumps(readings, ensure_ascii=False),
        "parts_of_speech_json": json.dumps(
            data.get("parts_of_speech", []), ensure_ascii=False
        ),
        "raw_json": json.dumps(subject, ensure_ascii=False),
        "data_updated_at": subject.get("data_updated_at"),
    }


def _assignment_to_row(assignment: dict) -> dict:
    data = assignment.get("data", {})
    return {
        "id": assignment["id"],
        "subject_id": data.get("subject_id"),
        "subject_type": data.get("subject_type"),
        "srs_stage": data.get("srs_stage"),
        "started_at": data.get("started_at"),
        "passed_at": data.get("passed_at"),
        "hidden": 1 if data.get("hidden") else 0,
        "raw_json": json.dumps(assignment, ensure_ascii=False),
        "data_updated_at": assignment.get("data_updated_at"),
    }


def run_full_sync() -> dict:
    """Fetch from WaniKani, store locally, and return a summary of counts."""
    conn = db.connect()
    db.init_schema(conn)

    with WaniKaniClient() as client:
        print("Fetching started kanji + vocabulary assignments...")
        assignments = client.fetch_started_assignments()
        print(f"  {len(assignments)} assignments")

        subject_ids = sorted(
            {a["data"]["subject_id"] for a in assignments if a["data"].get("subject_id")}
        )
        print(f"Fetching {len(subject_ids)} referenced subjects...")
        subjects = client.fetch_subjects_by_ids(subject_ids)
        print(f"  {len(subjects)} subjects")

    subject_rows = [_subject_to_row(s) for s in subjects]
    assignment_rows = [_assignment_to_row(a) for a in assignments]

    # Subjects first: assignments reference them via a foreign key.
    n_subjects = db.upsert_subjects(conn, subject_rows)
    n_assignments = db.upsert_assignments(conn, assignment_rows)
    conn.close()

    return {
        "assignments_synced": n_assignments,
        "subjects_synced": n_subjects,
    }
