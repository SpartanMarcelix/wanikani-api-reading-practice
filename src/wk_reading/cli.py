"""Command-line entry point: sync, stats, reading-seed."""

from __future__ import annotations

import argparse
import json
import sys

from wk_reading import db, selectors, sync

# On Windows, Python defaults stdout/stderr to a legacy code page, which mangles
# Japanese. Force UTF-8 so seeds can be copied/piped intact.
for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")


def _cmd_sync(args: argparse.Namespace) -> int:
    summary = sync.run_full_sync()
    print(
        f"\nDone. assignments={summary['assignments_synced']} "
        f"subjects={summary['subjects_synced']}"
    )
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    conn = db.connect()
    db.init_schema(conn)
    stats = selectors.get_stats(conn)
    conn.close()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"\nTotal started (kanji+vocab): {stats['total_started']}", file=sys.stderr)
    return 0


def _emit(data: dict, out: str | None) -> None:
    """Write JSON to a UTF-8 file (shell-encoding-proof) or to stdout."""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"Wrote {out}", file=sys.stderr)
    else:
        print(text)


def _cmd_reading_seed(args: argparse.Namespace) -> int:
    conn = db.connect()
    db.init_schema(conn)
    seed = selectors.build_reading_seed(
        conn,
        srs_min=args.srs_min,
        vocab_count=args.vocab_count,
        kanji_count=args.kanji_count,
        difficulty=args.difficulty,
    )
    conn.close()
    _emit(seed, args.out)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wk-reading")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="Full sync from WaniKani into SQLite")
    p_sync.set_defaults(func=_cmd_sync)

    p_stats = sub.add_parser("stats", help="Show counts by type and SRS bucket")
    p_stats.set_defaults(func=_cmd_stats)

    p_seed = sub.add_parser("reading-seed", help="Emit a compact reading seed (JSON)")
    p_seed.add_argument("--srs-min", type=int, default=5, dest="srs_min")
    p_seed.add_argument("--vocab-count", type=int, default=12, dest="vocab_count")
    p_seed.add_argument("--kanji-count", type=int, default=20, dest="kanji_count")
    p_seed.add_argument("--difficulty", type=str, default="n4_n3")
    p_seed.add_argument(
        "--out", type=str, default=None,
        help="Write the seed to this UTF-8 file instead of stdout",
    )
    p_seed.set_defaults(func=_cmd_reading_seed)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
