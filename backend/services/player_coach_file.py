"""The player file: one document per player that the coach pages read.

docs/coach_pages_scope.md. Every coach page (Home, Games, Learn, Progress,
Play, and the academy view of a student) reads this one document by player id,
so no page computes anything when it opens. It is a CACHE derived from `games`,
`game_analyses` and `move_observations`; it is never a source of truth, and
deleting it loses nothing (the next build writes it again).

Who writes it:
  - the analysis worker, after every analysed game, for players who already
    have a file (`refresh_if_present_sync`);
  - the page endpoint, in the background, the first time a player is opened
    (`build_and_store`).

What is in it (schema 2):
  - `openings`: his costliest opening HABITS. A habit is the same move idea
    (same piece to the same square) in the same opening family, in three or
    more games and at least two positions. Only real opening CHOICES count:
    when the better move was a capture or a check (a missed shot) or his move
    left a piece hanging (a safety slip), that instance belongs to the
    tactics and safety coaching, not the opening file. Measured 2026-11-12 on
    50 players: those were 40% of the instances under 1000 and 10-35% above.
  - `traps`: his traps in four cases (caught him / waiting for him / he could
    set it / he sprang it), read from the analysis worker's stored trap scan
    (game_analyses.trap_fires), with the side each trap wins for decided by
    Stockfish (data/trap_roles_verified.json); each links to the trap school.
  - `last_game`: the newest analysed game's deciding move (his costliest move,
    150+), and whether it repeats one of his opening habits. "Same as before"
    is said ONLY through a habit key (side + opening + move idea): that key
    beat the other-player control in three bands of four (q: coach_measure.py,
    2026-11-12); pattern ids did not (scope Q4).
  - `habit`, `habit_check`, `progress`: the problem he trains and whether each
    trusted problem is changing (services/player_coach_habit.py).
  - `play_positions`: positions from his own games to spar from.
  - `sitting`: whether long sittings cost THIS player, from his own history
    with a permutation test. Across 53 players the game's number in a sitting
    barely moves the score (0.47-0.56), so it is never said as a general rule.

Player-facing sentences carry no digits. Chess notation lives in separate
fields (`line`, `san`, `better_san`) that the page renders as notation.
"""
from __future__ import annotations

import io
import json
import logging
import os
import random
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import chess
import chess.pgn

from services import player_coach_habit as pch

logger = logging.getLogger(__name__)

COLLECTION = "player_coach_files"
SCHEMA_VERSION = 3
FLAG_ENV = "BETWEEN_GAMES_USERS"

# Newest analysed games read for the opening habits, traps and progress.
OPENING_GAMES = 60
# The opening is the player's first twelve moves.
OPENING_LAST_MOVE = 12
PLIES_READ = 30
HABIT_MIN_GAMES = 3
HABIT_MIN_POSITIONS = 2
HABITS_SHOWN = 3

# Average Stockfish loss a habit must reach to be shown, per rating band.
# Locked 2026-11-12 from the 90th percentile of the average loss of every habit
# seen in 3+ games, newest 60 games of 53 players (q234.py): <1000 p90 140,
# 1000-1399 p90 86, 1400-1799 p90 73, 1800+ p90 64. One cut for every band
# would be wrong: a typical repeated move costs 31 under 1000 and 19 at 1800+.
HABIT_CUT_BY_BAND = {"<1000": 140, "1000-1399": 86, "1400-1799": 73, "1800+": 64}

# The deciding move of a game: his costliest move, at least this much. At
# every band 86-91% of games have one (53 players, 2026-11-12).
DECIDING_CP = 150

# Traps shown per case (caught / waiting / could set / sprang).
TRAPS_SHOWN = 2
TRAP_ROLES_PATH = Path(__file__).resolve().parent.parent / "data" / "trap_roles_verified.json"

PLAY_POSITIONS_SHOWN = 4

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


def is_enabled_for_request(request: Any, user_id: str) -> bool:
    """The flag, or a super-admin viewing this player through view-as.

    View-as lets Mohit review the coach pages on any player at any level
    without anyone else seeing them: the player himself still gets the old
    pages until his id is in the flag. `request.state.view_as` is set only by
    routes/auth._resolve_view_as after it re-checks the super-admin session.
    """
    if is_enabled_for(user_id):
        return True
    state = getattr(request, "state", None)
    session = getattr(state, "view_as", None) if state is not None else None
    return bool(session) and session.get("target_user_id") == user_id


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


def _idea(san: str) -> str:
    return san.replace("x", "").replace("+", "").replace("#", "")


def instance_kind(fen: str, san: str, best: str) -> Optional[str]:
    """'shot' when the better move was a capture or a check; 'safety' when his
    move left one of his pieces hanging that was not hanging before (or the
    moved piece itself); otherwise 'choice'. None when the move is unreadable."""
    from services.first_steps import is_hanging

    try:
        board = chess.Board(fen)
        move = board.parse_san(san)
    except (ValueError, AssertionError):
        return None
    if best:
        try:
            better = board.parse_san(best)
            if board.is_capture(better) or board.gives_check(better):
                return "shot"
        except (ValueError, AssertionError):
            pass
    me = board.turn
    before = {sq for sq, p in board.piece_map().items() if p.color == me and is_hanging(board, sq)}
    after_board = board.copy(stack=False)
    after_board.push(move)
    after = {sq for sq, p in after_board.piece_map().items() if p.color == me and is_hanging(after_board, sq)}
    if (after - before) or move.to_square in after:
        return "safety"
    return "choice"


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
            idea = _idea(san)
            # Castling is never the idea to replace: when castling is
            # expensive, something else was left loose, which is a safety
            # habit and belongs to the safety coaching, not the opening file.
            if idea.startswith("O-O"):
                continue
            key = (parts[1], family, idea)
            # One instance per game: the same idea twice in one game is one game.
            if game_id in habits[key]:
                continue
            best = str(row.get("best_move") or "")
            # A missed shot or a piece left hanging is not opening knowledge.
            if instance_kind(fen, san, best) != "choice":
                continue
            habits[key][game_id] = {
                "cp": min(float(cp), 1000.0),
                "fen": fen,
                "position": " ".join(parts[:4]),
                "san": san,
                "best": best,
                "game_id": game_id,
                "move_number": int(parts[5]),
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
                "game_id": inst["game_id"],
                "review_url": f"/game/{inst['game_id']}?move={inst['move_number']}",
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
# Traps
# --------------------------------------------------------------------------
_TRAP_ROLES: Optional[Dict[str, Dict[str, Any]]] = None


def trap_roles() -> Dict[str, Dict[str, Any]]:
    """Each trap with the side it wins for, decided by Stockfish (depth 18,
    eval after the setup vs after the trap line, 150+). Traps the engine could
    not decide, and opening-plan lessons, are left out."""
    global _TRAP_ROLES
    if _TRAP_ROLES is None:
        try:
            raw = json.loads(TRAP_ROLES_PATH.read_text(encoding="utf-8")).get("traps") or {}
        except (OSError, ValueError):
            logger.warning("trap roles file missing: %s", TRAP_ROLES_PATH)
            raw = {}
        _TRAP_ROLES = {k: v for k, v in raw.items()
                       if v.get("setter") in ("white", "black") and v.get("lesson_kind") != "opening_plan"
                       and v.get("setup_san")}
    return _TRAP_ROLES


def _practice_link(practice_key: Optional[str]) -> Optional[str]:
    """A trap lesson exists only for keys the trick library knows."""
    if not practice_key:
        return None
    try:
        from trick_library_service import TRAPS_DATABASE
    except Exception:  # pragma: no cover - library import trouble: no link
        return None
    return f"/play-with-coach?trap={practice_key}" if practice_key in TRAPS_DATABASE else None


TRAP_SCHOOL_PATH = TRAP_ROLES_PATH.parent / "trap_school.json"
_TRAP_SCHOOL_KEYS: Optional[set] = None

TRAP_WORDS = {
    "caught": ("This trap has caught you.", "Learn the line, so you see it coming next time."),
    "waiting": ("This trap was waiting for you, and your opponent missed it.",
                "Next time they may not. Learn the line."),
    "could_set": ("You could have set this trap.", "Your games reach the position. Learn the line and set it."),
    "sprang": ("You sprang this trap. Well played.", "It keeps working, so keep it in your games."),
}


def trap_slug(key: str) -> str:
    """The trap school's address for a trap key ("italian-game#0" -> "italian-game-0")."""
    return key.replace("#", "-")


def _school_keys() -> set:
    global _TRAP_SCHOOL_KEYS
    if _TRAP_SCHOOL_KEYS is None:
        try:
            raw = json.loads(TRAP_SCHOOL_PATH.read_text(encoding="utf-8"))
            _TRAP_SCHOOL_KEYS = {t["key"] for t in raw.get("traps") or []}
        except (OSError, ValueError):
            _TRAP_SCHOOL_KEYS = set()
    return _TRAP_SCHOOL_KEYS


def trap_record(fires: Iterable[Mapping[str, Any]], practice_keys: Mapping[str, str]) -> Dict[str, List[Dict[str, Any]]]:
    """His traps, in four cases, from the analysis worker's stored trap scan.

    ONE source: `game_analyses.trap_fires`, written for every analysed game by
    services/trap_scanner.py (2026-11-12 census: 532 games). An earlier version
    of this file re-scanned PGNs itself and found traps for 5 of 78 players.
    The scanner's setter/victim role comes from move-count parity, which is
    wrong on some traps, so the side is the engine's (trap_roles_verified.json).
    "Sprang" and "caught" need the whole line (`full_sprung`), not its first move.

    `fires`: {game_id, user_color, fire}, newest game first.
    """
    by_name = {t.get("name"): (k, t) for k, t in trap_roles().items()}
    tally: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for f in fires or ():
        fire = f.get("fire") or {}
        hit = by_name.get(fire.get("trap_name"))
        colour = f.get("user_color")
        if not hit or colour not in ("white", "black"):
            continue
        key, trap = hit
        full = bool(fire.get("full_sprung"))
        if trap["setter"] == colour:
            case = "sprang" if full else "could_set"
        else:
            case = "caught" if full else "waiting"
        if f.get("game_id") not in tally[(case, key)]:
            tally[(case, key)].append(f.get("game_id"))

    out: Dict[str, List[Dict[str, Any]]] = {case: [] for case in TRAP_WORDS}
    for (case, key), games in tally.items():
        trap = trap_roles()[key]
        setter = trap["setter"]
        side = setter if case in ("sprang", "could_set") else ("black" if setter == "white" else "white")
        headline, detail = TRAP_WORDS[case]
        out[case].append({
            "key": key, "name": trap.get("name"), "side": side,
            "setup_san": trap["setup_san"], "trap_line_san": trap.get("trap_line_san") or [],
            "setup_fen": trap.get("setup_fen"),
            "school_url": f"/learn/traps/{trap_slug(key)}" if key in _school_keys() else None,
            "practice_url": _practice_link(practice_keys.get(key)),
            "headline": headline, "detail": detail,
            "game_id": games[0],
            "measured": {"games": len(games)},
        })
    for rows in out.values():
        rows.sort(key=lambda r: -r["measured"]["games"])
        del rows[TRAPS_SHOWN:]
    return out


def _practice_keys() -> Dict[str, str]:
    try:
        raw = json.loads((TRAP_ROLES_PATH.parent / "traps.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: Dict[str, str] = {}
    for family, recs in raw.items():
        recs = recs if isinstance(recs, list) else [recs]
        for i, r in enumerate(recs):
            if r.get("practice_key"):
                out[f"{family}#{i}"] = r["practice_key"]
    return out


# --------------------------------------------------------------------------
# The last game
# --------------------------------------------------------------------------
def last_game_read(game: Optional[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]],
                   habits: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """The newest analysed game's deciding move, and whether it is one of his
    opening habits. `rows` are that game's move_evaluations."""
    if not game:
        return None
    own = [r for r in rows if not r.get("is_opponent_move") and isinstance(r.get("cp_loss"), (int, float))
           and r.get("fen_before") and r.get("move")]
    family = " ".join(str(r.get("move") or "") for r in rows[:2]).strip()
    base = {"game_id": game.get("game_id"), "user_color": game.get("user_color"),
            "result": _score(game.get("result"), game.get("user_color")),
            "played_at": game.get("played_at_utc")}
    worst = max(own, key=lambda r: r["cp_loss"], default=None)
    if worst is None or worst["cp_loss"] < DECIDING_CP:
        return {**base, "clean": True, "headline": "No single move decided your last game.",
                "detail": "Nothing big to fix from it."}
    fen, san, best = worst["fen_before"], str(worst["move"]), str(worst.get("best_move") or "")
    played = _squares(fen, san)
    better = _squares(fen, best) if best and best != san else None
    if not played:
        return {**base, "clean": True, "headline": "No single move decided your last game.",
                "detail": "Nothing big to fix from it."}
    side = fen.split()[1]
    try:
        move_number = int(fen.split()[5])
    except (IndexError, ValueError):
        move_number = None
    repeat = None
    if move_number is not None and move_number <= OPENING_LAST_MOVE:
        colour = "white" if side == "w" else "black"
        for h in habits:
            if h["side"] == colour and h["line"] == family and h["idea"] == _idea(san):
                repeat = {"line": h["line"], "idea": h["idea"],
                          "words": "You have played this move in this opening before, and it cost you then too."}
                break
    return {
        **base,
        "clean": False,
        "fen": fen,
        "san": san,
        "better_san": best if better else None,
        "played_from": played[0], "played_to": played[1],
        "better_from": better[0] if better else None, "better_to": better[1] if better else None,
        "move_number": move_number,
        "review_url": f"/game/{game.get('game_id')}" + (f"?move={move_number}" if move_number else ""),
        "headline": "One move decided your last game.",
        "repeat": repeat,
        "measured": {"cp_loss": worst["cp_loss"]},
    }


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
# Play positions
# --------------------------------------------------------------------------
def play_positions(openings: Sequence[Mapping[str, Any]], last_game: Optional[Mapping[str, Any]],
                   habit: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Positions from his own games to spar from, with the side he played."""
    out: List[Dict[str, Any]] = []
    seen = set()

    def add(fen: Optional[str], colour: Optional[str], title: str, detail: str, game_id: Any) -> None:
        if not fen or colour not in ("white", "black"):
            return
        position = " ".join(fen.split()[:4])
        if position in seen:
            return
        try:
            board = chess.Board(fen)
        except ValueError:
            return
        # He must be the side to move, and the game must not be over.
        if (board.turn == chess.WHITE) != (colour == "white") or board.is_game_over():
            return
        seen.add(position)
        out.append({"fen": fen, "user_color": colour, "title": title, "detail": detail,
                    "source_game_id": game_id})

    if last_game and not last_game.get("clean"):
        add(last_game.get("fen"), last_game.get("user_color"), "Your last game, from the move that decided it",
            "Play it again from here and find a better way.", last_game.get("game_id"))
    for h in openings:
        add(h.get("fen"), h.get("side"), f"Your opening as {str(h.get('side')).capitalize()}",
            "The position where your habit costs you. Play it the better way.", h.get("game_id"))
    for m in (habit or {}).get("moments") or []:
        add(m.get("fen_before"), m.get("color"), f"A moment from your games: {str(habit.get('label') or '').lower()}",
            "Play on from the position where it happened.", m.get("game_id"))
    return out[:PLAY_POSITIONS_SHOWN]


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
    observations: Sequence[Mapping[str, Any]] = (),
    last_rows: Sequence[Mapping[str, Any]] = (),
    previous: Optional[Mapping[str, Any]] = None,
    fires: Sequence[Mapping[str, Any]] = (),
    moments_fn: Optional[Callable[[Dict[str, Any], Dict[str, Dict[str, Any]]], List[Dict[str, Any]]]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Pure: everything is read by the caller. `moments_fn(habit, games_by_id)`
    builds the habit's board moments with the engine (None in tests)."""
    games_newest_first = dedupe_games(games_newest_first)
    kept_ids = {g.get("game_id") for g in games_newest_first}
    rating = _rating(games_newest_first)
    band = _band(rating)
    analyses = [a for a in analyses if a.get("game_id") in kept_ids]
    analysed = [g for g in games_newest_first if g.get("is_analyzed")][:OPENING_GAMES]
    analysed_ids = [g["game_id"] for g in analysed]
    by_id = {g["game_id"]: g for g in games_newest_first}

    openings = opening_habits(analyses, band)
    traps = trap_record(fires, _practice_keys())
    last = last_game_read(analysed[0] if analysed else None, last_rows, openings)

    observations = [o for o in observations if o.get("game_id") in set(analysed_ids)]
    gmap = pch.games_map(analysed)
    habit = pch.choose_habit(analysed_ids, gmap, observations, (previous or {}).get("habit"), now=now)
    habit_check = None
    if habit:
        evidence = habit.pop("_evidence", [])
        cached = {m.get("key"): m for m in ((previous or {}).get("habit") or {}).get("moments") or []}
        moments: List[Dict[str, Any]] = []
        if moments_fn and evidence:
            games_with_pgn = {gid: {**gmap[gid], "pgn": by_id[gid].get("pgn") or ""} for gid in gmap}
            try:
                moments = moments_fn({"evidence": evidence, "cached": cached}, games_with_pgn)
            except Exception:
                logger.exception("habit moments failed for %s", user_id)
                moments = list(cached.values())
        habit["moments"] = moments[:pch.HABIT_MOMENTS]
        habit_check = pch.habit_check(habit, analysed_ids, gmap, observations)

    return {
        "user_id": user_id,
        "schema_version": SCHEMA_VERSION,
        "built_at": now or datetime.now(timezone.utc),
        "rating": rating,
        "band": band,
        "last_game": last,
        "openings": openings,
        "traps": traps,
        "habit": habit,
        "habit_check": habit_check,
        "progress": pch.progress(analysed_ids, gmap, observations),
        "play_positions": play_positions(openings, last, habit),
        "sitting": sitting_finding(list(reversed(list(games_newest_first))), seed=user_id),
        "source": {
            "games": len(games_newest_first),
            "analysed_games_read": len(analyses),
            "observations_read": len(observations),
        },
    }


# --------------------------------------------------------------------------
# Reading and writing
# --------------------------------------------------------------------------
_GAME_FIELDS = {"_id": 0, "game_id": 1, "played_at_utc": 1, "result": 1, "user_color": 1,
                "is_analyzed": 1, "user_rating": 1, "user_rating_at_time": 1,
                "white_rating": 1, "black_rating": 1, "pgn": 1, "platform": 1,
                "platform_game_id": 1, "url": 1, "termination": 1, "game_outcome": 1}

_OBS_FILTER_OR = [{"missed_pattern": {"$ne": None}}, {"development_decision": "missed"}]
_OBS_FIELDS = {"_id": 0, "game_id": 1, "ply": 1, "move_number": 1, "fen_before": 1, "move_uci": 1,
               "missed_pattern": 1, "subtype": 1, "eval_before": 1, "time_spent_seconds": 1,
               "development_decision": 1}


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


def _last_rows_pipeline(game_id: str) -> List[Dict[str, Any]]:
    return [
        {"$match": {"game_id": game_id}},
        {"$limit": 1},
        {"$project": {"_id": 0, "rows": {"$map": {
            "input": {"$ifNull": ["$stockfish_analysis.move_evaluations", []]},
            "as": "m",
            "in": {"fen_before": "$$m.fen_before", "move": "$$m.move", "cp_loss": "$$m.cp_loss",
                   "is_opponent_move": "$$m.is_opponent_move", "best_move": "$$m.best_move"},
        }}}},
    ]


def _fires(games: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Stored trap fires as {game_id, user_color, fire}, newest game first.
    Duplicate imports of one game count once (dedupe_games)."""
    kept = dedupe_games(games)
    order = {g["game_id"]: i for i, g in enumerate(kept)}
    colour = {g["game_id"]: g.get("user_color") for g in kept}
    out = []
    for r in sorted((r for r in rows if r.get("game_id") in order), key=lambda r: order[r["game_id"]]):
        for fire in r.get("trap_fires") or []:
            out.append({"game_id": r["game_id"], "user_color": colour[r["game_id"]], "fire": fire})
    return out


def _mark_development(observations: List[Dict[str, Any]], dev_rows: Sequence[Mapping[str, Any]]) -> None:
    """Lock A1 of the coach plan: development counts only for a player whose
    development rate over his last 80 analysed games passed the cut-off."""
    from services import coach_plan_service as cp

    if cp.development_rate(dev_rows)["eligible"]:
        for o in observations:
            o["_development_eligible"] = True


def engine_moments(job: Mapping[str, Any], games: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Runs in a worker thread (or the worker itself): one engine for the few
    moments of one player. Same builder as the academy plan."""
    import chess.engine
    from config import STOCKFISH_PATH
    from services import coach_plan_service as cp

    out: List[Dict[str, Any]] = []
    engine = None
    try:
        for o in job.get("evidence") or []:
            key = cp.moment_key(o)
            if key in (job.get("cached") or {}):
                out.append(job["cached"][key])
            else:
                game = games.get(o["game_id"])
                if not game:
                    continue
                if engine is None:
                    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
                m = cp.build_moment(o, game, engine)
                if not m:
                    continue
                out.append({**cp.public_moment(m), "game_id": o["game_id"],
                            "move_number": o.get("move_number")})
            if len(out) >= pch.HABIT_MOMENTS:
                break
    finally:
        if engine is not None:
            engine.quit()
    return out


def _store_fields(doc: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(doc)


def build_and_store_sync(db, user_id: str) -> Dict[str, Any]:
    games = list(db.games.find({"user_id": user_id}, _GAME_FIELDS)
                 .sort("played_at_utc", -1).limit(SITTING_GAMES_READ))
    analysed_ids = [g["game_id"] for g in dedupe_games(games) if g.get("is_analyzed")][:OPENING_GAMES]
    analyses = list(db.game_analyses.aggregate(_analysis_pipeline(analysed_ids))) if analysed_ids else []
    last_rows: List[Dict[str, Any]] = []
    if analysed_ids:
        found = list(db.game_analyses.aggregate(_last_rows_pipeline(analysed_ids[0])))
        last_rows = (found[0].get("rows") if found else None) or []
    observations = list(db.move_observations.find(
        {"user_id": user_id, "game_id": {"$in": analysed_ids}, "$or": _OBS_FILTER_OR}, _OBS_FIELDS)) if analysed_ids else []
    dev_ids = [g["game_id"] for g in games if g.get("is_analyzed")][:80]
    dev_rows = list(db.move_observations.find(
        {"user_id": user_id, "game_id": {"$in": dev_ids}, "development_decision": {"$in": ["applied", "missed"]}},
        {"_id": 0, "development_decision": 1, "missed_pattern": 1})) if dev_ids else []
    _mark_development(observations, dev_rows)
    previous = db[COLLECTION].find_one({"user_id": user_id}, {"_id": 0, "habit": 1})
    fires = _fires(games, list(db.game_analyses.find(
        {"game_id": {"$in": [g["game_id"] for g in games if g.get("is_analyzed")]}, "trap_fires.0": {"$exists": True}},
        {"_id": 0, "game_id": 1, "trap_fires": 1})))
    doc = build_file(user_id, games, analyses, observations, last_rows, previous, fires, engine_moments)
    db[COLLECTION].update_one({"user_id": user_id}, {"$set": _store_fields(doc)}, upsert=True)
    return doc


async def build_and_store(db, user_id: str) -> Dict[str, Any]:
    import asyncio

    games = await (db.games.find({"user_id": user_id}, _GAME_FIELDS)
                   .sort("played_at_utc", -1).limit(SITTING_GAMES_READ).to_list(None))
    analysed_ids = [g["game_id"] for g in dedupe_games(games) if g.get("is_analyzed")][:OPENING_GAMES]
    analyses: List[Dict[str, Any]] = []
    last_rows: List[Dict[str, Any]] = []
    observations: List[Dict[str, Any]] = []
    dev_rows: List[Dict[str, Any]] = []
    if analysed_ids:
        analyses = await db.game_analyses.aggregate(_analysis_pipeline(analysed_ids)).to_list(None)
        found = await db.game_analyses.aggregate(_last_rows_pipeline(analysed_ids[0])).to_list(1)
        last_rows = (found[0].get("rows") if found else None) or []
        observations = await db.move_observations.find(
            {"user_id": user_id, "game_id": {"$in": analysed_ids}, "$or": _OBS_FILTER_OR}, _OBS_FIELDS).to_list(None)
        dev_ids = [g["game_id"] for g in games if g.get("is_analyzed")][:80]
        dev_rows = await db.move_observations.find(
            {"user_id": user_id, "game_id": {"$in": dev_ids}, "development_decision": {"$in": ["applied", "missed"]}},
            {"_id": 0, "development_decision": 1, "missed_pattern": 1}).to_list(None)
    _mark_development(observations, dev_rows)
    previous = await db[COLLECTION].find_one({"user_id": user_id}, {"_id": 0, "habit": 1})
    fires = _fires(games, await db.game_analyses.find(
        {"game_id": {"$in": [g["game_id"] for g in games if g.get("is_analyzed")]}, "trap_fires.0": {"$exists": True}},
        {"_id": 0, "game_id": 1, "trap_fires": 1}).to_list(None))
    # The build may run the engine: keep it off the event loop.
    doc = await asyncio.to_thread(build_file, user_id, games, analyses, observations, last_rows,
                                  previous, fires, engine_moments)
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


# --------------------------------------------------------------------------
# What the pages receive
# --------------------------------------------------------------------------
def _public_habit(habit: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    if not habit:
        return None
    keep = ("quality_id", "label", "kind", "pattern", "warning_sign", "rule", "practice_key",
            "started_at", "moments", "measured")
    return {k: habit.get(k) for k in keep}


def payload(doc: Optional[Mapping[str, Any]], recent: Sequence[Mapping[str, Any]],
            now: Optional[datetime] = None) -> Dict[str, Any]:
    """What the pages receive. `measured` blocks stay in for review; the pages
    never render them."""
    if not doc:
        return {"enabled": True, "state": "building"}
    band = doc.get("band")
    return {
        "enabled": True,
        "state": "ready",
        "schema_version": doc.get("schema_version"),
        "built_at": doc.get("built_at"),
        "band": band,
        # Under 1000 the boards carry the moves; notation stays off the page.
        "notation": band != "<1000",
        "last_game": doc.get("last_game"),
        "openings": list(doc.get("openings") or []),
        "traps": doc.get("traps") or {case: [] for case in TRAP_WORDS},
        "habit": _public_habit(doc.get("habit")),
        "habit_check": doc.get("habit_check"),
        "progress": doc.get("progress") or {"habits": [], "kept": []},
        "play_positions": list(doc.get("play_positions") or []),
        "sitting": sitting_now(doc.get("sitting") or {}, recent, now=now),
        "sitting_measured": (doc.get("sitting") or {}).get("measured"),
        "source": doc.get("source"),
    }
