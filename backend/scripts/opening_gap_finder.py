"""
Opening gap finder — mines the 2985-game corpus for SAN move
prefixes that are played frequently but NOT recognised by
opening_book._OPENINGS. Output is a prioritised list of opening
lines we should add captions for.

Strategy:
  1. Walk every game; extract the first N SAN moves (default 14).
  2. For each prefix length 3..10, count how many games share that
     exact prefix (separately for white-to-move and black-to-move
     prefixes).
  3. Drop prefixes that already match an entry in _OPENINGS.
  4. Mark "extension" prefixes — popular sequences whose immediate
     parent (prefix minus the last move) IS in the book. These are
     known mainlines branching into uncovered sub-variations.
  5. Sort by frequency; print the top entries.

Output flags each candidate with:
  - count of games
  - whether the parent prefix is recognised (▸ extension)
  - whether the prefix would be reached as a transposition

Usage:
    python scripts/opening_gap_finder.py
    python scripts/opening_gap_finder.py --limit 200
    python scripts/opening_gap_finder.py --min-count 5
    python scripts/opening_gap_finder.py --output /tmp/openings.txt
"""

import argparse
import asyncio
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

MAX_PLY = 14         # how many half-moves to look at per game
MIN_PREFIX_LEN = 3   # ignore "1. e4" — too generic
MAX_PREFIX_LEN = 10


def _load_book_prefixes() -> tuple[set, dict]:
    """Returns (set_of_book_tuples, book_name_by_tuple)."""
    from services.decryption_voice.opening_book import _OPENINGS
    book_tuples = set()
    name_by_tuple = {}
    for entry in _OPENINGS:
        t = tuple(entry["moves"])
        book_tuples.add(t)
        name_by_tuple[t] = entry["name"]
    return book_tuples, name_by_tuple


async def main(args) -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    book_tuples, book_names = _load_book_prefixes()

    # Read SAN sequences from games. The decryption_v5_data record has
    # move_san per ply (both colours), so we walk it in order.
    cursor = db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True, "$ne": []}},
        {"_id": 0, "game_id": 1, "decryption_v5_data": 1},
    )
    if args.limit and args.limit > 0:
        cursor = cursor.limit(args.limit)

    # prefix_counts[length] -> Counter[tuple-of-san]
    prefix_counts: dict[int, Counter] = defaultdict(Counter)
    games_processed = 0

    async for ga in cursor:
        v5 = ga.get("decryption_v5_data") or []
        history = []
        for rec in v5[:MAX_PLY]:
            san = rec.get("move_san")
            if not san:
                break
            history.append(san)

        if len(history) < MIN_PREFIX_LEN:
            games_processed += 1
            continue

        # Count every prefix from MIN..MAX as observed in this game.
        for length in range(MIN_PREFIX_LEN, min(MAX_PREFIX_LEN, len(history)) + 1):
            prefix_counts[length][tuple(history[:length])] += 1

        games_processed += 1

    client.close()

    # ── Build candidate list ─────────────────────────────────────────
    candidates = []
    for length in range(MIN_PREFIX_LEN, MAX_PREFIX_LEN + 1):
        for prefix, n in prefix_counts[length].items():
            if n < args.min_count:
                continue
            if prefix in book_tuples:
                continue  # already covered
            parent = prefix[:-1]
            parent_in_book = parent in book_tuples
            parent_name = book_names.get(parent)
            candidates.append({
                "prefix": prefix,
                "length": length,
                "count": n,
                "parent_in_book": parent_in_book,
                "parent_name": parent_name,
            })

    # Sort: extensions first (parent in book) then by count.
    candidates.sort(key=lambda c: (not c["parent_in_book"], -c["count"], c["length"]))

    # ── Build report ─────────────────────────────────────────────────
    lines = []
    lines.append("=" * 78)
    lines.append("OPENING GAP FINDER")
    lines.append("=" * 78)
    lines.append(f"  games processed:        {games_processed}")
    lines.append(f"  book entries loaded:    {len(book_tuples)}")
    lines.append(f"  min count threshold:    {args.min_count}")
    lines.append(f"  candidate prefixes:     {len(candidates)}")
    lines.append("")
    lines.append("Legend:")
    lines.append("  ▸ EXTENSION = parent prefix is already named in opening_book")
    lines.append("                (high leverage — finishes a known line)")
    lines.append("  · NEW       = neither this nor any shorter prefix is in book")
    lines.append("")

    # Section 1: extensions (parent in book) — easiest wins
    extensions = [c for c in candidates if c["parent_in_book"]]
    lines.append(f"EXTENSIONS — {len(extensions)} candidates")
    lines.append("(Parent line is named; sub-variation isn't.)")
    lines.append("-" * 78)
    for c in extensions[: args.top]:
        side = "(W)" if c["length"] % 2 == 1 else "(B)"
        prefix_str = " ".join(c["prefix"])
        lines.append(
            f"  ▸ {c['count']:4d}× len={c['length']} {side}  "
            f"parent={c['parent_name']}"
        )
        lines.append(f"      moves: {prefix_str}")
    lines.append("")

    # Section 2: completely new lines — no parent recognised
    new_lines = [c for c in candidates if not c["parent_in_book"]]
    lines.append(f"NEW LINES — {len(new_lines)} candidates")
    lines.append("(No prefix recognised — whole line is a gap.)")
    lines.append("-" * 78)
    for c in new_lines[: args.top]:
        side = "(W)" if c["length"] % 2 == 1 else "(B)"
        prefix_str = " ".join(c["prefix"])
        lines.append(f"  · {c['count']:4d}× len={c['length']} {side}  {prefix_str}")
    lines.append("")

    # Section 3: most-common shortest gaps — these unlock the most games
    # if we add a single entry. A length-3 gap covers all longer
    # extensions of itself.
    lines.append("HIGHEST-LEVERAGE SHORT GAPS (length 3-5):")
    lines.append("(Add these first — they cover the most descendants.)")
    lines.append("-" * 78)
    short_gaps = [c for c in candidates if c["length"] <= 5]
    short_gaps.sort(key=lambda c: -c["count"])
    for c in short_gaps[:30]:
        side = "(W)" if c["length"] % 2 == 1 else "(B)"
        prefix_str = " ".join(c["prefix"])
        marker = "▸" if c["parent_in_book"] else "·"
        parent_tag = f" parent={c['parent_name']}" if c["parent_in_book"] else ""
        lines.append(f"  {marker} {c['count']:4d}× len={c['length']} {side}  {prefix_str}{parent_tag}")
    lines.append("")

    output = "\n".join(lines)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"\nReport written to {args.output}")
    else:
        print()
        print(output)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="cap to first N games (0 = all)")
    p.add_argument("--min-count", type=int, default=3, help="minimum game count to surface")
    p.add_argument("--top", type=int, default=50, help="rows per section")
    p.add_argument("--output", default=None, help="write report to file")
    args = p.parse_args()
    asyncio.run(main(args))
