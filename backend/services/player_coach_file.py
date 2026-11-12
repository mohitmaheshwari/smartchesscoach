"""The player file: one document per player that the coach pages read.

docs/coach_pages_scope.md. Every coach page reads this one document by player
id, so no page computes anything when it opens. It is a CACHE derived from
`games` and `game_analyses`; it is never a source of truth, and deleting it
loses nothing (the next build writes it again).

Who writes it:
  - the analysis worker, after every analysed game, for players who already
    have a file (`refresh_if_present_sync`);
  - the home endpoint, in the background, the first time a flagged player
    opens Home (`build_and_store`).

What is in it (V1, the between-games slice):
  - `openings`: the player's costliest opening HABITS. A habit is the same
    move idea (same piece to the same square) in the same opening family, in
    three or more games and at least two different positions. Matching the
    idea instead of the exact position is what makes it visible early:
    measured 2026-11-12 over 53 players, with only the newest 20 games a habit
    leak shows for 21/26 (<1000), 8/11, 7/9, 7/7 (1800+) players, against
    9/26, 3/11, 0/9, 4/7 for exact positions.
  - `sitting`: whether long sittings cost THIS player, decided from his own
    history with a permutation test. Across all 53 players the game's number
    in a sitting barely moves the score (0.47-0.56), so this is never said as
    a general rule -- only when his own games show it beyond chance.

Player-facing sentences carry no digits. Chess notation lives in separate
fields (`line`, `san`, `better_san`) that the page renders as notation.
"""
from __future__ import annotations

import io
import logging
import os
import random
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import chess
import chess.pgn

logger = logging.getLogger(__name__)

COLLECTION = "player_coach_files"
SCHEMA_VERSION = 1
FLAG_ENV = "BETWEEN_GAMES_USERS"

# Newest analysed games read for the opening habits.
OPENING_GAMES = 60
# The opening is the player's first twelve moves.
OPENING_LAST_MOVE = 12
PLIES_READ = 30
HABIT_MIN_GAMES = 3
HABIT_MIN_POSITIONS = 2
HABITS_SHOWN = 2

# Average Stockfish loss a habit must reach to be shown, per rating band.
# Locked 2026-11-12 from the 90th percentile of the average loss of every habit
# seen in 3+ games, newest 60 games of 53 players (q234.py): <1000 p90 140,
# 1000-1399 p90 86, 1400-1799 p90 73, 1800+ p90 64. One cut for every band
# would be wrong: a typical repeated move costs 31 under 1000 and 19 at 1800+.
HABIT_CUT_BY_BAND = {"<1000": 140, "1000-1399": 86, "1400-1799": 73, "1800+": 64}

# Sittings. A new sitting starts after a gap of more than 45 minutes between
# game starts (the median start-to-start gap is 10-16 minutes at every band).
SITTING_GAP_MIN = 45
# "Later in a sitting" means the seventh game onwards.
SITTING_LATE_FROM = 7
SITTING_MIN_GAMES_EACH_SIDE = 20
SITTING_PERMUTATIONS = 300
SITTING_GAMES_READ = 600
# The live "good place to stop" line needs him to be mid-sitting right now.
SITTING_ACTIVE_WITHIN_MIN = 60


# --------------------------------------------------------------------------
# Flag
# --------------------------------------------------------------------------
def is_enabled_for(user_id: str) -> bool:
    raw = os.environ.get(FLAG_ENV, "")
    ids = {x.strip() for x in raw.split(",") if x.strip()}
    return "*" in ids or user_id in ids


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _band(rating: Optional[int]) -> str:
    if rating is None:
        return "1000-1399"
    if rating < 1000:
        return "<1000"
    if rating < 1400:
        return "1000-1399"
    if rating < 1800:
        return "1400-1799"
    return "1800+"


def _score(result: Any, colour: Any) -> Optional[float]:
    result, colour = str(result or ""), str(colour or "")
    if result == "1/2-1/2":
        return 0.5
    if result in ("1-0", "0-1") and colour in ("white", "black"):
        return 1.0 if (result == "1-0") == (colour == "white") else 0.0
    return None


def _when(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _rating(games_newest_first: Sequence[Mapping[str, Any]]) -> Optional[int]:
    """Median of the three newest game ratings: the window the rating
    resolver's 2026-09-01 bake-off chose (services/rating_resolver.py)."""
    from services.rating_resolver import get_game_user_rating

    found: List[int] = []
    for game in games_newest_first:
        value = get_game_user_rating(dict(game))
        if value:
            found.append(int(value))
        if len(found) == 3:
            break
    return int(statistics.median(found)) if found else None


def _squares(fen: str, san: str) -> Optional[Tuple[str, str]]:
    try:
        board = chess.Board(fen)
        move = board.parse_san(san)
    except (ValueError, AssertionError):
        return None
    return chess.square_name(move.from_square), chess.square_name(move.to_square)


# --------------------------------------------------------------------------
# Openings
# --------------------------------------------------------------------------
def opening_habits(
    analyses: Iterable[Mapping[str, Any]], band: str
) -> List[Dict[str, Any]]:
    """The costliest opening habits, most expensive first.

    `analyses` are {game_id, rows}; `rows` are the first plies of
    move_evaluations in game order (fen_before, move, cp_loss,
    is_opponent_move, best_move).
    """
    cut = HABIT_CUT_BY_BAND.get(band, HABIT_CUT_BY_BAND["1000-1399"])
    habits: Dict[Tuple[str, str, str], Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for doc in analyses:
        rows = list(doc.get("rows") or [])
        if len(rows) < 2:
            continue
        family = " ".join(str(r.get("move") or "") for r in rows[:2]).strip()
        game_id = doc.get("game_id")
        for row in rows:
            if row.get("is_opponent_move"):
                continue
            cp = row.get("cp_loss")
            fen = row.get("fen_before") or ""
            san = str(row.get("move") or "")
            parts = fen.split()
            if not isinstance(cp, (int, float)) or len(parts) < 6 or not san:
                continue
            try:
                if int(parts[5]) > OPENING_LAST_MOVE:
                    continue
            except ValueError:
                continue
            idea = san.replace("x", "").replace("+", "").replace("#", "")
            # Castling is never the idea to replace: when castling is
            # expensive, something else was left loose, which is a safety
            # habit and belongs to the safety coaching, not the opening file.
            if idea.startswith("O-O"):
                continue
            key = (parts[1], family, idea)
            # One instance per game: the same idea twice in one game is one game.
            if game_id in habits[key]:
                continue
            habits[key][game_id] = {
                "cp": min(float(cp), 1000.0),
                "fen": fen,
                "position": " ".join(parts[:4]),
                "san": san,
                "best": str(row.get("best_move") or ""),
            }

    found: List[Dict[str, Any]] = []
    for (side, family, idea), by_game in habits.items():
        instances = list(by_game.values())
        if len(instances) < HABIT_MIN_GAMES:
            continue
        if len({i["position"] for i in instances}) < HABIT_MIN_POSITIONS:
            continue
        average = statistics.mean(i["cp"] for i in instances)
        if average < cut:
            continue
        # The clearest picture of the cost: the instance that cost most and
        # whose better move is legal on its board.
        example = None
        for inst in sorted(instances, key=lambda i: -i["cp"]):
            played = _squares(inst["fen"], inst["san"])
            better = _squares(inst["fen"], inst["best"]) if inst["best"] else None
            if played and better and inst["best"] != inst["san"]:
                example = (inst, played, better)
                break
        if example is None:
            continue
        inst, played, better = example
        colour = "white" if side == "w" else "black"
        found.append(
            {
                "side": colour,
                "line": family,
                "idea": idea,
                "san": inst["san"],
                "fen": inst["fen"],
                "played_from": played[0],
                "played_to": played[1],
                "better_san": inst["best"],
                "better_from": better[0],
                "better_to": better[1],
                "headline": (
                    f"As {colour.capitalize()}, you keep playing this move early, "
                    "and it keeps costing you."
                ),
                "detail": "Here is the clearest time it went wrong, and the better move.",
                # For review and tests. Never rendered.
                "measured": {
                    "games": len(instances),
                    "positions": len({i["position"] for i in instances}),
                    "average_cp": round(average, 1),
                    "band_cut_cp": cut,
                    "example_cp": inst["cp"],
                },
                "_rank": len(instances) * average,
            }
        )
    found.sort(key=lambda h: -h["_rank"])
    for habit in found:
        habit.pop("_rank", None)
    return found[:HABITS_SHOWN]


# --------------------------------------------------------------------------
# Sittings
# --------------------------------------------------------------------------
def _sitting_slots(games_oldest_first: Sequence[Mapping[str, Any]]) -> List[Tuple[int, float]]:
    """(index in its sitting, score) per finished game, oldest first."""
    slots: List[Tuple[int, float]] = []
    previous: Optional[datetime] = None
    index = 0
    for game in games_oldest_first:
        started = _when(game.get("played_at_utc"))
        score = _score(game.get("result"), game.get("user_color"))
        if started is None or score is None:
            continue
        if previous is not None and (started - previous) <= timedelta(minutes=SITTING_GAP_MIN):
            index += 1
        else:
            index = 1
        previous = started
        slots.append((index, score))
    return slots


def sitting_finding(games_oldest_first: Sequence[Mapping[str, Any]], seed: str) -> Dict[str, Any]:
    """Does a long sitting cost THIS player, beyond chance?"""
    slots = _sitting_slots(games_oldest_first)
    early = [s for i, s in slots if i < SITTING_LATE_FROM]
    late = [s for i, s in slots if i >= SITTING_LATE_FROM]
    result: Dict[str, Any] = {
        "proven": False,
        "measured": {"early_games": len(early), "late_games": len(late)},
    }
    if len(early) < SITTING_MIN_GAMES_EACH_SIDE or len(late) < SITTING_MIN_GAMES_EACH_SIDE:
        result["measured"]["why_not"] = "not enough games on both sides"
        return result
    drop = statistics.mean(early) - statistics.mean(late)
    scores = [s for _, s in slots]
    is_late = [i >= SITTING_LATE_FROM for i, _ in slots]
    rng = random.Random(f"sitting:{seed}")
    null: List[float] = []
    for _ in range(SITTING_PERMUTATIONS):
        shuffled = scores[:]
        rng.shuffle(shuffled)
        e = [s for s, late_slot in zip(shuffled, is_late) if not late_slot]
        l = [s for s, late_slot in zip(shuffled, is_late) if late_slot]
        null.append(statistics.mean(e) - statistics.mean(l))
    null.sort()
    p95 = null[int(len(null) * 0.95) - 1]
    result["measured"].update(
        {
            "early_score": round(statistics.mean(early), 3),
            "late_score": round(statistics.mean(late), 3),
            "drop": round(drop, 3),
            "chance_p95": round(p95, 3),
        }
    )
    result["proven"] = drop > 0 and drop > p95
    return result


def sitting_now(
    finding: Mapping[str, Any],
    recent_games_newest_first: Sequence[Mapping[str, Any]],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """The sitting lines for this moment. Computed when the page asks, from a
    small indexed read of his latest game start times."""
    if not finding.get("proven"):
        return {"show": False}
    now = now or datetime.now(timezone.utc)
    starts = [t for t in (_when(g.get("played_at_utc")) for g in recent_games_newest_first) if t]
    length = 0
    if starts and now - starts[0] <= timedelta(minutes=SITTING_ACTIVE_WITHIN_MIN):
        length = 1
        for newer, older in zip(starts, starts[1:]):
            if newer - older <= timedelta(minutes=SITTING_GAP_MIN):
                length += 1
            else:
                break
    if length >= SITTING_LATE_FROM - 1:
        # Six games in, the next one is where his results drop.
        return {
            "show": True,
            "live": True,
            "headline": "You've played a long sitting today.",
            "detail": "Your games go worse late in a long sitting. This is a good place to stop.",
        }
    return {
        "show": True,
        "live": False,
        "headline": "Long sittings cost you.",
        "detail": "Your games go worse after many in a row. Take a break before that point.",
    }


# --------------------------------------------------------------------------
# Building the file
# --------------------------------------------------------------------------
def _game_key(game: Mapping[str, Any]) -> str:
    """The same game imported twice has two game_ids but one platform game.

    The PGN's Site tag is the reliable key: the 2026-11-11 duplicates of
    user_65360395020a share it while their platform_game_id and url differ
    or are missing."""
    pgn = game.get("pgn") or ""
    # Chess.com puts the constant "Chess.com" in Site and the game's address
    # in Link; Lichess puts the address in Site. Only a real address is a key.
    for marker in ('[Link "', '[Site "'):
        start = pgn.find(marker)
        if start >= 0:
            end = pgn.find('"', start + len(marker))
            value = pgn[start + len(marker):end].strip()
            if value.startswith("http"):
                return value.rstrip("/")
    platform_id = game.get("platform_game_id")
    if platform_id:
        return f"{game.get('platform')}:{platform_id}"
    url = game.get("url")
    if url:
        return str(url).rstrip("/")
    return str(game.get("game_id"))


def dedupe_games(games: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    """Keep the first copy of each platform game. Duplicate imports exist in
    prod (two records of one game); counted twice they look like two games
    played seconds apart and inflate every sitting they fall in."""
    seen = set()
    kept = []
    for game in games:
        key = _game_key(game)
        if key in seen:
            continue
        seen.add(key)
        kept.append(game)
    return kept


def build_file(
    user_id: str,
    games_newest_first: Sequence[Mapping[str, Any]],
    analyses: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    games_newest_first = dedupe_games(games_newest_first)
    kept_ids = {g.get("game_id") for g in games_newest_first}
    rating = _rating(games_newest_first)
    band = _band(rating)
    analyses = [a for a in analyses if a.get("game_id") in kept_ids]
    return {
        "user_id": user_id,
        "schema_version": SCHEMA_VERSION,
        "built_at": datetime.now(timezone.utc),
        "rating": rating,
        "band": band,
        "openings": opening_habits(analyses, band),
        "sitting": sitting_finding(list(reversed(list(games_newest_first))), seed=user_id),
        "source": {
            "games": len(games_newest_first),
            "analysed_games_read": len(analyses),
        },
    }


_GAME_FIELDS = {"_id": 0, "game_id": 1, "played_at_utc": 1, "result": 1, "user_color": 1,
                "is_analyzed": 1, "user_rating": 1, "user_rating_at_time": 1,
                "white_rating": 1, "black_rating": 1, "pgn": 1, "platform": 1,
                "platform_game_id": 1, "url": 1}


def _analysis_pipeline(game_ids: List[str]) -> List[Dict[str, Any]]:
    return [
        {"$match": {"game_id": {"$in": game_ids}}},
        {"$project": {"_id": 0, "game_id": 1, "rows": {"$map": {
            "input": {"$slice": [{"$ifNull": ["$stockfish_analysis.move_evaluations", []]}, PLIES_READ]},
            "as": "m",
            "in": {"fen_before": "$$m.fen_before", "move": "$$m.move", "cp_loss": "$$m.cp_loss",
                   "is_opponent_move": "$$m.is_opponent_move", "best_move": "$$m.best_move"},
        }}}},
    ]


def _store_fields(doc: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(doc)


def build_and_store_sync(db, user_id: str) -> Dict[str, Any]:
    games = list(db.games.find({"user_id": user_id}, _GAME_FIELDS)
                 .sort("played_at_utc", -1).limit(SITTING_GAMES_READ))
    analysed_ids = [g["game_id"] for g in games if g.get("is_analyzed")][:OPENING_GAMES]
    analyses = list(db.game_analyses.aggregate(_analysis_pipeline(analysed_ids))) if analysed_ids else []
    doc = build_file(user_id, games, analyses)
    db[COLLECTION].update_one({"user_id": user_id}, {"$set": _store_fields(doc)}, upsert=True)
    return doc


async def build_and_store(db, user_id: str) -> Dict[str, Any]:
    games = await (db.games.find({"user_id": user_id}, _GAME_FIELDS)
                   .sort("played_at_utc", -1).limit(SITTING_GAMES_READ).to_list(None))
    analysed_ids = [g["game_id"] for g in games if g.get("is_analyzed")][:OPENING_GAMES]
    analyses = []
    if analysed_ids:
        analyses = await db.game_analyses.aggregate(_analysis_pipeline(analysed_ids)).to_list(None)
    doc = build_file(user_id, games, analyses)
    await db[COLLECTION].update_one({"user_id": user_id}, {"$set": _store_fields(doc)}, upsert=True)
    return doc


def refresh_if_present_sync(db, user_id: str) -> bool:
    """Called by the analysis worker after every game. Rebuilds only for a
    player who already has a file, so the cost lands where the page is used."""
    if not db[COLLECTION].find_one({"user_id": user_id}, {"_id": 1}):
        return False
    build_and_store_sync(db, user_id)
    return True


async def recent_starts(db, user_id: str, limit: int = 16) -> List[Dict[str, Any]]:
    games = await (db.games.find({"user_id": user_id},
                                 {"_id": 0, "game_id": 1, "played_at_utc": 1, "platform": 1,
                                  "platform_game_id": 1, "url": 1, "pgn": 1})
                   .sort("played_at_utc", -1).limit(limit).to_list(None))
    return dedupe_games(games)


def payload(doc: Optional[Mapping[str, Any]], recent: Sequence[Mapping[str, Any]],
            now: Optional[datetime] = None) -> Dict[str, Any]:
    """What the page receives. `measured` blocks stay in for review."""
    if not doc:
        return {"enabled": True, "state": "building"}
    return {
        "enabled": True,
        "state": "ready",
        "schema_version": doc.get("schema_version"),
        "built_at": doc.get("built_at"),
        "openings": list(doc.get("openings") or []),
        "sitting": sitting_now(doc.get("sitting") or {}, recent, now=now),
        "sitting_measured": (doc.get("sitting") or {}).get("measured"),
    }
