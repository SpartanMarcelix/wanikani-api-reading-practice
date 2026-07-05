"""Query the local DB: stats and the reading-seed selector.

The seed is intentionally compact (PLAN.md "context window strategy"): a handful
of target vocabulary plus an allowed-kanji set and generation constraints — never
the full known-item list, never raw_json.
"""

from __future__ import annotations

import sqlite3

# SRS stage -> bucket name, matching the WaniKani dashboard Item Spread.
SRS_BUCKETS = {
    1: "apprentice", 2: "apprentice", 3: "apprentice", 4: "apprentice",
    5: "guru", 6: "guru",
    7: "master",
    8: "enlightened",
    9: "burned",
}


def get_stats(conn: sqlite3.Connection) -> dict:
    """Counts by subject type and SRS bucket for started, non-hidden items."""
    rows = conn.execute(
        """
        SELECT subject_type, srs_stage, COUNT(*) AS n
        FROM assignments
        WHERE hidden = 0 AND started_at IS NOT NULL
        GROUP BY subject_type, srs_stage
        """
    ).fetchall()

    by_type: dict[str, int] = {"kanji": 0, "vocabulary": 0}
    by_bucket: dict[str, int] = {
        "apprentice": 0, "guru": 0, "master": 0, "enlightened": 0, "burned": 0
    }
    total = 0
    for row in rows:
        n = row["n"]
        total += n
        by_type[row["subject_type"]] = by_type.get(row["subject_type"], 0) + n
        bucket = SRS_BUCKETS.get(row["srs_stage"])
        if bucket:
            by_bucket[bucket] += n

    return {"total_started": total, "by_type": by_type, "by_srs_bucket": by_bucket}


def _started_where(srs_min: int) -> str:
    return (
        "a.hidden = 0 AND a.started_at IS NOT NULL "
        f"AND a.srs_stage >= {int(srs_min)}"
    )


def select_target_vocabulary(
    conn: sqlite3.Connection, srs_min: int, count: int
) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT s.id, s.characters, s.primary_reading AS reading,
               s.primary_meaning AS meaning, a.srs_stage
        FROM assignments a
        JOIN subjects s ON s.id = a.subject_id
        WHERE a.subject_type = 'vocabulary' AND {_started_where(srs_min)}
          AND s.characters IS NOT NULL
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (count,),
    ).fetchall()
    return [dict(r) for r in rows]


def select_allowed_kanji(conn: sqlite3.Connection, srs_min: int) -> list[str]:
    rows = conn.execute(
        f"""
        SELECT s.characters
        FROM assignments a
        JOIN subjects s ON s.id = a.subject_id
        WHERE a.subject_type = 'kanji' AND {_started_where(srs_min)}
          AND s.characters IS NOT NULL
        ORDER BY s.characters
        """,
    ).fetchall()
    return [r["characters"] for r in rows]


def build_reading_seed(
    conn: sqlite3.Connection,
    srs_min: int = 5,
    vocab_count: int = 12,
    kanji_count: int = 20,
    difficulty: str = "n4_n3",
) -> dict:
    """Assemble a compact, prompt-ready reading seed from the local DB."""
    target_vocab = select_target_vocabulary(conn, srs_min, vocab_count)
    all_allowed = select_allowed_kanji(conn, srs_min)

    # Ensure kanji used by the chosen vocab are allowed, then top up to kanji_count.
    from_vocab = {
        ch
        for v in target_vocab
        for ch in (v.get("characters") or "")
        if "一" <= ch <= "鿿"
    }
    ordered = list(from_vocab) + [k for k in all_allowed if k not in from_vocab]
    allowed_kanji = ordered[: max(kanji_count, len(from_vocab))]

    return {
        "learner_profile": {
            "known_vocab_count": _count(conn, "vocabulary", srs_min),
            "known_kanji_count": _count(conn, "kanji", srs_min),
            "srs_min_used": srs_min,
        },
        "target_vocabulary": target_vocab,
        "allowed_kanji": allowed_kanji,
        "constraints": {
            "difficulty": difficulty,
            "length": "120-180 Japanese characters",
            "style": "simple slice-of-life paragraph",
            "furigana_policy": (
                "Use allowed_kanji freely. For any kanji outside allowed_kanji, "
                "prefer kana or add furigana."
            ),
            "output_sections": [
                "Japanese passage",
                "English translation",
                "Vocabulary checklist",
                "3 comprehension questions",
                "1 grammar note",
            ],
        },
    }


def _count(conn: sqlite3.Connection, subject_type: str, srs_min: int) -> int:
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS n FROM assignments a
        WHERE a.subject_type = ? AND {_started_where(srs_min)}
        """,
        (subject_type,),
    ).fetchone()
    return row["n"]
