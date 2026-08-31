"""Phase 0 for any human-behaviour model (Maia 2 / Otter): make the inputs exist.

Every skill-conditioned human model needs player Elo, and Otter additionally
needs per-move remaining clock. Neither is reliably stored today, and
date_played is written in two formats which makes any train-on-past /
score-on-future split silently wrong.

Three independent, additive passes. Default is a read-only dry run.

1. ELO      games.user_rating / opponent_rating are missing on ~27% of rows,
            but 95% of PGNs carry [WhiteElo]/[BlackElo]. Fill the gaps into
            human_model.player_elo / human_model.opponent_elo, never
            overwriting an existing stored rating.

2. CLOCK    move_time_stats is aggregate only (median/critical), so it cannot
            produce Otter's clock_fraction. 93.7% of PGNs carry per-move
            [%clk H:MM:SS] tags. Parsed into human_model.clocks_s as whole
            seconds, ply-indexed from move 1.

3. DATE     447 rows use YYYY.MM.DD while 13,787 use YYYY-MM-DD. "." is ASCII
            46 and "-" is 45, so EVERY dotted date sorts after EVERY dashed
            one regardless of the actual day -- a naive temporal split pushes
            all 447 to the end of a player timeline. Normalised into
            date_played_iso; the original date_played is never modified.

Nothing here calls an engine, an LLM, or a network service.

    python backend/scripts/backfill_human_model_prerequisites.py            # dry run
    python backend/scripts/backfill_human_model_prerequisites.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

BATCH_SIZE = 500
SCHEMA_VERSION = "human_model_prereq.v1"

_ELO_TAG = re.compile(r'\[(White|Black)Elo\s+"(\d{3,4})"\]')
_CLK_TAG = re.compile(r"\[%clk\s+(\d+):(\d{2}):(\d{2}(?:\.\d+)?)\]")
_DATE_DOTS = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})")
_DATE_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def parse_elos(pgn: str) -> Dict[str, int]:
    """{'White': 1268, 'Black': 1143} for whichever tags are present."""
    out: Dict[str, int] = {}
    for colour, value in _ELO_TAG.findall(pgn or ""):
        try:
            elo = int(value)
        except ValueError:
            continue
        if 100 <= elo <= 3500:          # reject obvious junk tags
            out[colour] = elo
    return out


def player_opponent_elo(pgn: str, user_color: str) -> Tuple[Optional[int], Optional[int]]:
    elos = parse_elos(pgn)
    if not elos:
        return None, None
    colour = "White" if str(user_color or "").lower().startswith("w") else "Black"
    other = "Black" if colour == "White" else "White"
    return elos.get(colour), elos.get(other)


def parse_clocks_seconds(pgn: str) -> List[int]:
    """Remaining clock per ply, in whole seconds, in game order."""
    out: List[int] = []
    for hh, mm, ss in _CLK_TAG.findall(pgn or ""):
        try:
            out.append(int(hh) * 3600 + int(mm) * 60 + int(float(ss)))
        except ValueError:
            continue
    return out


def normalise_date(value) -> Optional[str]:
    """YYYY-MM-DD, or None when the value cannot be trusted."""
    if value is None:
        return None
    if hasattr(value, "strftime"):           # already a datetime
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    for pattern in (_DATE_ISO, _DATE_DOTS):
        m = pattern.match(text)
        if m:
            year, month, day = m.groups()
            if not (1 <= int(month) <= 12 and 1 <= int(day) <= 31):
                return None
            return f"{year}-{month}-{day}"
    return None


def build_update(row: Dict) -> Tuple[Optional[Dict], Counter]:
    """Fields to $set for one game, plus what changed. None when nothing to do."""
    stats: Counter = Counter()
    pgn = row.get("pgn") or ""
    fields: Dict[str, object] = {}

    # 1. ELO -- prefer an already-stored rating, fall back to the PGN tags.
    stored_player = row.get("user_rating")
    stored_opponent = row.get("opponent_rating")
    pgn_player, pgn_opponent = player_opponent_elo(pgn, row.get("user_color"))
    player = stored_player if isinstance(stored_player, (int, float)) else pgn_player
    opponent = stored_opponent if isinstance(stored_opponent, (int, float)) else pgn_opponent
    if player is not None:
        fields["human_model.player_elo"] = int(player)
        stats["elo_player_from_pgn" if not isinstance(stored_player, (int, float))
              else "elo_player_from_store"] += 1
    else:
        stats["elo_player_missing"] += 1
    if opponent is not None:
        fields["human_model.opponent_elo"] = int(opponent)
        stats["elo_opponent_from_pgn" if not isinstance(stored_opponent, (int, float))
              else "elo_opponent_from_store"] += 1
    else:
        stats["elo_opponent_missing"] += 1

    # 2. CLOCK -- per-ply remaining seconds, straight from the PGN.
    clocks = parse_clocks_seconds(pgn)
    if clocks:
        fields["human_model.clocks_s"] = clocks
        fields["human_model.clock_ply_count"] = len(clocks)
        stats["clocks_parsed"] += 1
    else:
        stats["clocks_absent"] += 1

    # 3. DATE -- normalised copy; the original field is left untouched.
    iso = normalise_date(row.get("date_played"))
    if iso:
        fields["date_played_iso"] = iso
        if iso != str(row.get("date_played") or "")[:10]:
            stats["date_reformatted"] += 1
        else:
            stats["date_already_iso"] += 1
    else:
        stats["date_unparseable"] += 1

    if not fields:
        return None, stats
    fields["human_model.schema_version"] = SCHEMA_VERSION
    return fields, stats


async def run(apply: bool, limit: Optional[int]) -> Counter:
    url = os.environ.get("MONGO_URL")
    if not url:
        raise SystemExit("MONGO_URL is required")
    client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=8000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    totals: Counter = Counter()
    pending: List[UpdateOne] = []
    projection = {
        "pgn": 1, "user_color": 1, "user_rating": 1,
        "opponent_rating": 1, "date_played": 1,
    }
    cursor = db.games.find({}, projection)
    if limit:
        cursor = cursor.limit(limit)

    async for row in cursor:
        totals["rows"] += 1
        fields, stats = build_update(row)
        totals.update(stats)
        if fields:
            totals["rows_updated"] += 1
            pending.append(UpdateOne({"_id": row["_id"]}, {"$set": fields}))
        if apply and len(pending) >= BATCH_SIZE:
            await db.games.bulk_write(pending, ordered=False)
            pending = []
    if apply and pending:
        await db.games.bulk_write(pending, ordered=False)

    client.close()
    return totals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="write updates; default is a read-only dry run")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    totals = asyncio.run(run(args.apply, args.limit))
    mode = "APPLY" if args.apply else "DRY_RUN"
    print(f"mode={mode} rows={totals['rows']} rows_updated={totals['rows_updated']}")
    for key in sorted(k for k in totals if k not in {"rows", "rows_updated"}):
        print(f"  {key}={totals[key]}")
    if not args.apply:
        print("No writes made. Pass --apply after reviewing these aggregates.")


if __name__ == "__main__":
    main()
