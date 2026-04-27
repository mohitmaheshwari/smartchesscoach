"""
Lichess Puzzle DB Importer
==========================

Streams the Lichess puzzle database (CC0 license) into MongoDB so the
coach can prescribe theme-tagged puzzles based on the user's diagnosed
weakness pattern. ~5M puzzles total in the source; we filter to a
useful subset by rating range and popularity.

Source: https://database.lichess.org/lichess_db_puzzle.csv.zst
Format: PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags

Each puzzle in MongoDB collection `lichess_puzzles`:
  {
    puzzle_id: "00008",
    fen: "rnbqkbnr/...",
    moves: ["f2g3", "e6e7", ...],     # UCI sequence
    rating: 1885,
    rating_dev: 75,
    popularity: 87,                    # -100..+100, higher is better
    nb_plays: 3719,
    themes: ["fork", "mateIn3", ...],
    game_url: "https://lichess.org/...",
    opening_tags: ["Italian_Game"],
    imported_at: <iso>,
  }

Indexes created on first import: themes (multikey), rating, popularity.

Usage (inside the chess-coach-backend container):
    python scripts/import_lichess_puzzles.py --dry-run
    python scripts/import_lichess_puzzles.py
    python scripts/import_lichess_puzzles.py --rating-min 800 --rating-max 1800
    python scripts/import_lichess_puzzles.py --min-popularity 80
    python scripts/import_lichess_puzzles.py --limit 500000

Defaults: rating 600-2200, popularity >= 80. Yields ~1-2M puzzles
(~750MB-1GB on disk). Override --min-popularity 0 to keep all.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import zstandard  # noqa: F401 — needed for streaming decompression
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, UpdateOne

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

LICHESS_PUZZLE_URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
COLLECTION = "lichess_puzzles"

# Default filters — keep "high quality" puzzles in the rating range our
# users will encounter. A 1200 player gets puzzles in 800-1600 range;
# 600-2200 covers the entire user base with margin.
DEFAULT_RATING_MIN = 600
DEFAULT_RATING_MAX = 2200
DEFAULT_MIN_POPULARITY = 80   # Lichess scale: 80 = 80%+ of solvers liked it

BATCH_SIZE = 1000


def _stream_decompressed_lines(url: str) -> Iterator[str]:
    """Stream-download the zstd-compressed CSV and yield decoded text
    lines without holding the full file in memory.
    """
    logger.info(f"Streaming download: {url}")
    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()

    total_bytes = int(response.headers.get("content-length", 0))
    logger.info(f"Compressed size: {total_bytes / 1024 / 1024:.1f} MB")

    dctx = zstandard.ZstdDecompressor()
    stream_reader = dctx.stream_reader(response.raw)
    text_stream = io.TextIOWrapper(stream_reader, encoding="utf-8", newline="")
    for line in text_stream:
        yield line


def _row_passes_filters(
    row: dict,
    rating_min: int,
    rating_max: int,
    min_popularity: int,
) -> bool:
    try:
        rating = int(row.get("Rating") or 0)
        popularity = int(row.get("Popularity") or 0)
    except (TypeError, ValueError):
        return False
    if rating < rating_min or rating > rating_max:
        return False
    if popularity < min_popularity:
        return False
    return True


def _row_to_doc(row: dict) -> dict:
    themes = (row.get("Themes") or "").split()
    moves = (row.get("Moves") or "").split()
    opening_tags = (row.get("OpeningTags") or "").split()
    return {
        "puzzle_id": row["PuzzleId"],
        "fen": row.get("FEN", ""),
        "moves": moves,
        "rating": int(row.get("Rating") or 0),
        "rating_dev": int(row.get("RatingDeviation") or 0),
        "popularity": int(row.get("Popularity") or 0),
        "nb_plays": int(row.get("NbPlays") or 0),
        "themes": themes,
        "game_url": row.get("GameUrl") or None,
        "opening_tags": opening_tags or None,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }


async def _ensure_indexes(db) -> None:
    coll = db[COLLECTION]
    await coll.create_index([("puzzle_id", ASCENDING)], unique=True)
    await coll.create_index([("themes", ASCENDING)])
    await coll.create_index([("rating", ASCENDING)])
    await coll.create_index([("popularity", ASCENDING)])


async def main(
    rating_min: int,
    rating_max: int,
    min_popularity: int,
    limit: int | None,
    dry_run: bool,
) -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    db = AsyncIOMotorClient(mongo_url)[db_name]

    print(f"DB: {db_name}")
    print(f"Filters: rating={rating_min}..{rating_max}, popularity>={min_popularity}"
          + (f", limit={limit}" if limit else ""))
    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    print()

    if not dry_run:
        await _ensure_indexes(db)

    coll = db[COLLECTION]
    existing_count = await coll.estimated_document_count()
    print(f"Existing docs in {COLLECTION}: {existing_count}")
    print()

    started = time.monotonic()
    seen_rows = 0
    kept_rows = 0
    written = 0
    batch: List[UpdateOne] = []

    line_iter = _stream_decompressed_lines(LICHESS_PUZZLE_URL)

    # First line is the CSV header.
    header_line = next(line_iter)
    reader = csv.DictReader(io.StringIO(header_line + "".join([])), fieldnames=None)
    headers = [h.strip() for h in header_line.strip().split(",")]
    logger.info(f"CSV headers: {headers}")

    for raw_line in line_iter:
        seen_rows += 1
        if not raw_line.strip():
            continue

        # csv module handles quoted fields — parse one line at a time.
        try:
            row = next(csv.DictReader(io.StringIO(raw_line), fieldnames=headers))
        except StopIteration:
            continue

        if not _row_passes_filters(row, rating_min, rating_max, min_popularity):
            continue

        if not row.get("PuzzleId"):
            continue

        kept_rows += 1
        if limit and kept_rows > limit:
            break

        doc = _row_to_doc(row)
        if not dry_run:
            batch.append(UpdateOne(
                {"puzzle_id": doc["puzzle_id"]},
                {"$set": doc},
                upsert=True,
            ))

        if len(batch) >= BATCH_SIZE:
            result = await coll.bulk_write(batch, ordered=False)
            written += (result.upserted_count or 0) + (result.modified_count or 0)
            batch = []
            elapsed = time.monotonic() - started
            rate = kept_rows / elapsed if elapsed > 0 else 0
            print(
                f"  scanned={seen_rows:>10,d}  kept={kept_rows:>9,d}  "
                f"written={written:>9,d}  rate={rate:>6.0f}/s",
                flush=True,
            )

        # Periodic progress on dry-run so user can see something.
        if dry_run and kept_rows % 50000 == 0 and kept_rows > 0:
            print(f"  scanned={seen_rows:>10,d}  kept={kept_rows:>9,d}  (dry-run)", flush=True)

    # Final batch flush.
    if batch and not dry_run:
        result = await coll.bulk_write(batch, ordered=False)
        written += (result.upserted_count or 0) + (result.modified_count or 0)

    elapsed = time.monotonic() - started
    print()
    print(f"Done in {elapsed:.1f}s")
    print(f"  CSV rows scanned: {seen_rows:,}")
    print(f"  Rows passing filters: {kept_rows:,}")
    if not dry_run:
        print(f"  Rows written/upserted: {written:,}")
        new_count = await coll.estimated_document_count()
        print(f"  Total docs in {COLLECTION}: {new_count:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rating-min", type=int, default=DEFAULT_RATING_MIN)
    parser.add_argument("--rating-max", type=int, default=DEFAULT_RATING_MAX)
    parser.add_argument("--min-popularity", type=int, default=DEFAULT_MIN_POPULARITY)
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap on number of imported puzzles (after filtering).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't write — just count rows passing filters.")
    args = parser.parse_args()

    asyncio.run(main(
        rating_min=args.rating_min,
        rating_max=args.rating_max,
        min_popularity=args.min_popularity,
        limit=args.limit,
        dry_run=args.dry_run,
    ))
