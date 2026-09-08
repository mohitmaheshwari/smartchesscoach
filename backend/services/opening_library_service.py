"""Compatibility library projected from the canonical opening curriculum.

There is deliberately no opening content in this module.  Every public
record is derived from ``data/opening_curriculum.json`` and filtered through
the offline curriculum truth gate before a route can expose it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
import re
from typing import Any, Dict, List, Optional

import chess

from services.curriculum_content_validator import (
    get_publishable_content_ids,
    trap_content_id,
)
from services.opening_theory_json_service import (
    get_lesson_move_steps,
    resolve_opening_key,
)
from services.opening_unified_source import get_unified_source


def _public_key(canonical_key: str) -> str:
    return canonical_key.replace("_", "-")


def _eco_codes(opening: Dict[str, Any]) -> List[str]:
    prefixes = opening.get("eco_prefix") or []
    if isinstance(prefixes, str):
        prefixes = [prefixes]
    if opening.get("eco"):
        prefixes = [*prefixes, opening["eco"]]
    return list(dict.fromkeys(str(code).upper() for code in prefixes if code))


def _verified_traps(canonical_key: str) -> List[Dict[str, Any]]:
    from services.trap_library import get_traps_for_opening

    opening_key = _public_key(canonical_key)
    publishable = get_publishable_content_ids("traps")
    return [
        trap
        for trap in get_traps_for_opening(opening_key)
        if trap_content_id(opening_key, trap.get("name", "")) in publishable
    ]


def _build_opening_database() -> Dict[str, Dict[str, Any]]:
    source = get_unified_source().get_all_openings()
    publishable = get_publishable_content_ids("openings")
    database: Dict[str, Dict[str, Any]] = {}
    for canonical_key in sorted(publishable):
        opening = source.get(canonical_key)
        if not isinstance(opening, dict):
            continue
        steps = get_lesson_move_steps(canonical_key)
        if not steps:
            # The truth gate requires a lesson line.  This extra delivery gate
            # protects legacy practice callers if a new schema is introduced.
            continue
        white_plan = str(opening.get("white_plan") or "").strip()
        black_plan = str(opening.get("black_plan") or "").strip()
        summary = str(opening.get("summary") or "").strip()
        description = summary or " / ".join(
            plan for plan in (white_plan, black_plan) if plan
        )
        key_ideas = (
            opening.get("common_learnings")
            or opening.get("golden_rules")
            or [plan for plan in (white_plan, black_plan) if plan]
        )
        database[_public_key(canonical_key)] = {
            "canonical_key": canonical_key,
            "name": opening.get("name") or canonical_key.replace("_", " ").title(),
            "eco": ", ".join(_eco_codes(opening)),
            "eco_codes": _eco_codes(opening),
            "description": description,
            "color": opening.get("color"),
            "first_moves": [step["move"] for step in steps[:5]],
            "main_line": steps,
            "key_ideas": list(key_ideas),
            "common_mistakes": list(opening.get("common_mistakes") or []),
            "traps": [],
            "what_if": list(opening.get("what_if") or []),
        }
    return database


# Backwards-compatible public name.  This is a derived, validated view—not a
# second authored database.
OPENING_DATABASE: Dict[str, Dict[str, Any]] = _build_opening_database()


@dataclass
class OpeningProgress:
    """Tracks a user's progress on a specific opening."""

    opening_key: str
    user_id: str
    main_line_progress: int = 0
    traps_learned: List[str] = field(default_factory=list)
    times_practiced: int = 0
    last_practiced: Optional[datetime] = None
    mastery_level: str = "unknown"


@dataclass(frozen=True)
class OpeningPosition:
    """Exact canonical-line recognition result for the Play route."""

    key: str
    name: str
    main_ideas: List[str]
    key_squares: List[str]
    typical_mistakes: List[str]
    simple_explanation: str
    eco_codes: List[str]


def _normalize_text(value: str) -> str:
    # Provider labels vary between "King's", "Kings" and Unicode apostrophes.
    # Treat the possessive spelling as the same token instead of splitting it
    # into "king s", which previously broke exact family routing.
    lowered = str(value or "").lower()
    lowered = re.sub(r"[’']s\b", "s", lowered)
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def _normalize_opening_key(opening_key: str) -> Optional[str]:
    if not opening_key:
        return None
    resolved = resolve_opening_key(opening_key)
    if resolved:
        public = _public_key(resolved)
        if public in OPENING_DATABASE:
            return public

    parts = _normalize_text(opening_key).split()
    while parts:
        candidate = "-".join(parts)
        if candidate in OPENING_DATABASE:
            return candidate
        parts.pop()
    return None


def get_opening_data(opening_key: str) -> Optional[Dict[str, Any]]:
    """Return one verified opening lesson and its verified traps."""
    resolved = _normalize_opening_key(opening_key)
    if not resolved:
        return None
    opening = OPENING_DATABASE.get(resolved)
    if not opening:
        return None
    return {**opening, "traps": _verified_traps(opening["canonical_key"])}


def resolve_teachable_opening(opening_key: str) -> Optional[Dict[str, str]]:
    """Resolve a recognized opening record to an honest verified lesson.

    A complete curriculum record is an ``exact_lesson``.  A recognition-only
    provider variation may reuse a verified base-family lesson, but the caller
    must present that relationship as ``family_foundation``.  Name-based
    resolution is intentional: ECO-only fallback is too broad to prove that a
    variation belongs to the lesson we are about to teach.
    """
    requested_key = resolve_opening_key(opening_key)
    if not requested_key:
        return None

    source_record = get_unified_source().get_all_openings().get(requested_key)
    if not isinstance(source_record, dict):
        return None
    recognized_name = str(
        source_record.get("name") or requested_key.replace("_", " ").title()
    ).strip()

    direct_public_key = _public_key(requested_key)
    if direct_public_key in OPENING_DATABASE:
        return {
            "requested_key": requested_key,
            "lesson_key": requested_key,
            "public_lesson_key": direct_public_key,
            "recognized_opening_name": recognized_name,
            "lesson_relation": "exact_lesson",
        }

    # Provider/ECO feeds often give several labels to the same playable
    # foundation.  Keep that relationship in the canonical curriculum rather
    # than guessing it again from display text at runtime.
    foundation_key = str(source_record.get("foundation_key") or "").strip()
    foundation_public_key = _public_key(foundation_key) if foundation_key else ""
    foundation = OPENING_DATABASE.get(foundation_public_key)
    if foundation:
        return {
            "requested_key": requested_key,
            "lesson_key": foundation["canonical_key"],
            "public_lesson_key": foundation_public_key,
            "recognized_opening_name": recognized_name,
            "lesson_relation": "family_foundation",
        }

    from services.opening_variation_resolver import get_resolver

    resolved_variation = get_resolver().resolve(recognized_name)
    base_name = (
        resolved_variation.get("base_opening")
        if isinstance(resolved_variation, dict)
        else None
    )
    public_lesson_key = match_opening_to_library(base_name or recognized_name)
    lesson = OPENING_DATABASE.get(public_lesson_key or "")
    if not lesson:
        return None
    return {
        "requested_key": requested_key,
        "lesson_key": lesson["canonical_key"],
        "public_lesson_key": public_lesson_key,
        "recognized_opening_name": recognized_name,
        "lesson_relation": "family_foundation",
    }


def get_all_openings() -> List[Dict[str, Any]]:
    result = []
    for key, data in OPENING_DATABASE.items():
        result.append(
            {
                "key": key,
                "name": data["name"],
                "eco": data["eco"],
                "color": data["color"],
                "description": data["description"],
                "trap_count": len(_verified_traps(data["canonical_key"])),
            }
        )
    return result


def get_openings_for_color(color: str) -> List[Dict[str, Any]]:
    wanted = str(color or "").lower()
    return [opening for opening in get_all_openings() if opening["color"] == wanted]


def match_opening_to_library(opening_name: str, eco: str = None) -> Optional[str]:
    """Match a provider opening name/ECO to a verified canonical lesson."""
    query = _normalize_text(opening_name)

    # Prefer the most specific canonical name before collapsing provider
    # variants to a family ("Sicilian Najdorf" must not become the broader
    # "Sicilian Defense" when the verified Najdorf lesson exists).
    if query:
        matches = []
        for key, data in OPENING_DATABASE.items():
            canonical_name = _normalize_text(data["name"])
            if canonical_name and (
                canonical_name == query
                or canonical_name in query
                or query in canonical_name
            ):
                matches.append((len(canonical_name), key))
        if matches:
            return max(matches)[1]

        # Reuse the repository's provider-name normalizer for aliases such as
        # Giuoco Piano -> Italian Game.  No alias table lives in this module.
        from services.opening_normalizer import normalize_opening

        normalized_family = _normalize_text(normalize_opening(opening_name))
        for key, data in OPENING_DATABASE.items():
            if _normalize_text(data["name"]) == normalized_family:
                return key

    eco_code = str(eco or "").upper().strip()
    if eco_code:
        eco_matches = [
            (len(data["eco_codes"]), key)
            for key, data in OPENING_DATABASE.items()
            if eco_code in data["eco_codes"]
        ]
        if eco_matches:
            # The narrower authored ECO family is the more specific match.
            return min(eco_matches)[1]
    return None


def _position_key(board: chess.Board) -> str:
    return " ".join(board.fen().split()[:4])


@lru_cache(maxsize=1)
def _position_index() -> Dict[str, OpeningPosition]:
    index: Dict[str, OpeningPosition] = {}
    for key, data in OPENING_DATABASE.items():
        board = chess.Board()
        info = OpeningPosition(
            key=key,
            name=data["name"],
            main_ideas=list(data["key_ideas"]),
            key_squares=[],
            typical_mistakes=[
                str(item.get("mistake") if isinstance(item, dict) else item)
                for item in data["common_mistakes"]
            ],
            simple_explanation=data["description"],
            eco_codes=list(data["eco_codes"]),
        )
        for step in data["main_line"]:
            try:
                board.push_san(step["move"])
            except ValueError:
                break
            index[_position_key(board)] = info
    return index


def get_opening_for_position(fen: str) -> Optional[OpeningPosition]:
    """Recognize only exact positions reached by a verified lesson line."""
    try:
        board = chess.Board(fen)
    except (TypeError, ValueError):
        return None
    return _position_index().get(_position_key(board))


async def get_opening_name(fen: str) -> str:
    opening = get_opening_for_position(fen)
    return opening.name if opening else ""


# A coach recommends from what the player actually plays and loses, not from
# what they have never seen. Below this many games a win rate is noise.
_MIN_GAMES_FOR_OPENING_ADVICE = 4
# Above this the moves are not the problem, so the lesson is about the plan.
_ACCURATE_ENOUGH_PCT = 75.0


def _opening_teaching_reason(entry: dict) -> str:
    """Say why THIS opening is worth this player's time, from their record.

    Ranked on opening-phase accuracy, not the whole game. A player who
    scores 87% across a Ruy Lopez and never wins it does not have an
    opening problem, and sending them to an opening lesson wastes the one
    thing they already own.
    """
    games = int(entry.get("games_played") or 0)
    wins = int(entry.get("wins") or 0)
    win_rate = float(entry.get("win_rate") or 0.0)
    band = entry.get("knowledge_band")
    cp = entry.get("opening_cp_per_move")
    if games < _MIN_GAMES_FOR_OPENING_ADVICE or not band or cp is None:
        return ""

    played = "You have played this %d times and won %d." % (games, wins)
    opening_quality = "You lose about %d centipawns a move over the first %d moves." % (
        round(cp), OPENING_PHASE_PLIES
    )

    if band in ("learn", "drill") and win_rate >= 50.0:
        # Winning anyway. Say the true thing -- they are starting each game
        # behind and recovering -- rather than calling a winning opening a
        # weakness.
        return (
            "%s %s You win these anyway, so drilling it would stop you "
            "climbing out of a hole first." % (played, opening_quality)
        )
    if band == "learn":
        return "%s %s That is where the games are going wrong." % (played, opening_quality)
    if band == "drill":
        return "%s %s You half know this one - drilling it will hold it together." % (
            played, opening_quality
        )
    # band == "know"
    if win_rate < 40.0:
        return (
            "%s You play the opening well, so the opening is not what is "
            "costing you - what happens after it is." % played
        )
    return "%s You know this one and it is working." % played


def _opening_teaching_priority(entry: dict) -> tuple:
    """Worst-known openings first; ones the player already knows go last.

    Previously ranked by games played weighted by losses, which put the
    Italian Game -- 15cp a move over the opening -- at the top of "what
    I'd teach next" for a player who plainly knows it.
    """
    band = entry.get("knowledge_band")
    games = int(entry.get("games_played") or 0)
    cp = float(entry.get("opening_cp_per_move") or 0.0)
    if games < _MIN_GAMES_FOR_OPENING_ADVICE or not band:
        return (3, 0, 0)
    rank = {"learn": 0, "drill": 1, "know": 2}.get(band, 3)
    return (rank, -cp, -games)


# Opening-phase cp/move tertiles, taken from 13,909 analysed games rather
# than chosen: p33 = 23, p66 = 48. Below the first a player knows the
# opening; above the second they do not.
OPENING_PHASE_PLIES = 12
_KNOWS_OPENING_CP = 23.0
_LEARNING_OPENING_CP = 48.0


async def get_opening_phase_accuracy(db, user_id: str) -> dict:
    """Mean cp lost per move over the first moves, per opening.

    Whole-game accuracy cannot answer "do I know this opening". A player
    can score 87% across a Ruy Lopez and still lose it, which is evidence
    the opening is NOT the problem. Only the opening phase separates the
    two, so the reduction happens in Mongo -- a game_analyses document
    averages ~190KB and there is no reason to pull them.
    """
    game_openings = {}
    async for game in db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "opening": 1, "opening_name": 1},
    ):
        name = game.get("opening_name")
        opening = game.get("opening")
        if isinstance(opening, dict):
            name = opening.get("name") or name
        elif isinstance(opening, str):
            name = name or opening
        if name and game.get("game_id"):
            game_openings[game["game_id"]] = name
    if not game_openings:
        return {}

    rows = await db.game_analyses.aggregate([
        {"$match": {"game_id": {"$in": list(game_openings)}}},
        {"$project": {"game_id": 1, "m": "$stockfish_analysis.move_evaluations"}},
        {"$unwind": "$m"},
        {"$match": {
            "m.is_opponent_move": {"$ne": True},
            "m.move_number": {"$lte": OPENING_PHASE_PLIES},
        }},
        {"$group": {
            "_id": "$game_id",
            "cp": {"$avg": "$m.cp_loss"},
            "moves": {"$sum": 1},
        }},
        {"$match": {"moves": {"$gte": 6}}},
    ]).to_list(length=5000)

    per_opening: dict = {}
    for row in rows:
        name = game_openings.get(row.get("_id"))
        if not name:
            continue
        per_opening.setdefault(name, []).append(float(row.get("cp") or 0.0))
    return {
        name: {"cp_per_move": sum(v) / len(v), "games": len(v)}
        for name, v in per_opening.items()
        if v
    }


def opening_knowledge_band(cp_per_move: float) -> str:
    """know / drill / learn, from the corpus tertiles above."""
    if cp_per_move < _KNOWS_OPENING_CP:
        return "know"
    if cp_per_move < _LEARNING_OPENING_CP:
        return "drill"
    return "learn"


async def get_user_opening_repertoire(db, user_id: str) -> Dict[str, Any]:
    from opening_trainer_service import get_user_opening_stats

    user_stats = await get_user_opening_stats(db, user_id)
    opening_phase = await get_opening_phase_accuracy(db, user_id)
    progress_records = await db.opening_learning_progress.find(
        {"user_id": user_id}
    ).to_list(100)
    progress_map = {}
    for progress in progress_records:
        key = _normalize_opening_key(progress.get("opening_key", ""))
        if key:
            progress_map[key] = progress

    white_openings: List[Dict[str, Any]] = []
    black_openings: List[Dict[str, Any]] = []
    played_keys = set()
    for stat in user_stats:
        opening_name = stat.get("name", "")
        opening_key = match_opening_to_library(opening_name, stat.get("eco"))
        if opening_key:
            played_keys.add(opening_key)
        progress = progress_map.get(opening_key, {})
        entry = {
            "name": opening_name,
            "games_played": stat.get("games_played", 0),
            "win_rate": stat.get("win_rate", 0),
            "avg_accuracy": stat.get("avg_accuracy", 0),
            # Carried through so the coaching reason can count real wins
            # rather than infer them; without these it printed "won 0"
            # above a 16.7% win rate.
            "wins": stat.get("wins", 0),
            "as_white": stat.get("as_white", 0),
            "opening_cp_per_move": (
                opening_phase.get(opening_name, {}).get("cp_per_move")
            ),
            "knowledge_band": (
                opening_knowledge_band(
                    opening_phase[opening_name]["cp_per_move"]
                )
                if opening_name in opening_phase
                else None
            ),
            "as_black": stat.get("as_black", 0),
            "losses": stat.get("losses", 0),
            "draws": stat.get("draws", 0),
            "in_library": opening_key is not None,
            "library_key": opening_key,
            "learning_progress": progress.get("main_line_progress", 0),
            "traps_learned": progress.get("traps_learned", []),
        }
        as_white = int(entry.get("as_white") or 0)
        as_black = int(entry.get("as_black") or 0)
        if as_white or as_black:
            color = "black" if as_black > as_white else "white"
        else:
            color = OPENING_DATABASE.get(opening_key, {}).get("color")
        if color == "black":
            black_openings.append(entry)
        else:
            white_openings.append(entry)

    # Recommend from the player's own record first. Openings they have never
    # touched only fill the remaining slots, and only when there is nothing
    # measured to work on.
    recommended_white = []
    recommended_black = []
    for entry in sorted(
        white_openings + black_openings, key=_opening_teaching_priority
    ):
        reason = _opening_teaching_reason(entry)
        if not reason:
            continue
        key = entry.get("library_key")
        data = OPENING_DATABASE.get(key, {}) if key else {}
        recommendation = {
            "key": key,
            "name": entry.get("name"),
            "description": data.get("description", ""),
            "reason": reason,
            "games_played": entry.get("games_played"),
            "win_rate": entry.get("win_rate"),
            "avg_accuracy": entry.get("avg_accuracy"),
            "opening_cp_per_move": entry.get("opening_cp_per_move"),
            "knowledge_band": entry.get("knowledge_band"),
            "from_your_games": True,
        }
        rec_as_white = int(entry.get("as_white") or 0)
        rec_as_black = int(entry.get("as_black") or 0)
        if rec_as_white or rec_as_black:
            rec_is_black = rec_as_black > rec_as_white
        else:
            rec_is_black = data.get("color") == "black"
        target = recommended_black if rec_is_black else recommended_white
        if len(target) < 3:
            target.append(recommendation)

    for key, data in OPENING_DATABASE.items():
        if key in played_keys:
            continue
        target = recommended_black if data["color"] == "black" else recommended_white
        if len(target) >= 3:
            continue
        target.append({
            "key": key,
            "name": data["name"],
            "description": data["description"],
            "reason": "New ground. A verified lesson you can practise move by move.",
            "from_your_games": False,
        })

    return {
        "white_repertoire": sorted(white_openings, key=lambda item: -item["games_played"]),
        "black_repertoire": sorted(black_openings, key=lambda item: -item["games_played"]),
        "recommended_white": recommended_white[:3],
        "recommended_black": recommended_black[:3],
        "total_openings_played": len(user_stats),
        "library_openings_available": len(OPENING_DATABASE),
    }


async def get_opening_lesson(db, user_id: str, opening_key: str) -> Optional[Dict[str, Any]]:
    opening = get_opening_data(opening_key)
    if not opening:
        return None
    resolved_key = _normalize_opening_key(opening_key)

    from opening_trainer_service import get_user_opening_stats

    user_stats = await get_user_opening_stats(db, user_id)
    user_opening_stats = next(
        (
            stat
            for stat in user_stats
            if match_opening_to_library(stat.get("name", ""), stat.get("eco"))
            == resolved_key
        ),
        None,
    )

    progress = await db.opening_learning_progress.find_one(
        {"user_id": user_id, "opening_key": {"$in": [opening_key, resolved_key, opening["canonical_key"]]}}
    )
    lesson = {
        "opening": opening,
        "user_stats": user_opening_stats,
        "user_mistakes": [],
        "learning_progress": {
            "main_line_progress": progress.get("main_line_progress", 0) if progress else 0,
            "traps_learned": progress.get("traps_learned", []) if progress else [],
            "times_practiced": progress.get("times_practiced", 0) if progress else 0,
            "mastery_level": progress.get("mastery_level", "unknown") if progress else "unknown",
        },
    }

    from services.opening_correction_service import apply_opening_lesson_corrections

    return await apply_opening_lesson_corrections(db, resolved_key, lesson)


async def update_learning_progress(
    db,
    user_id: str,
    opening_key: str,
    main_line_progress: int = None,
    trap_learned: str = None,
    practiced: bool = False,
) -> Dict[str, str]:
    """Record lesson exposure without accepting browser-declared mastery."""
    resolved_key = _normalize_opening_key(opening_key)
    if not resolved_key:
        return {"mastery_level": "unknown"}
    now = datetime.now(timezone.utc)
    await db.opening_learning_progress.update_one(
        {"user_id": user_id, "opening_key": resolved_key},
        {
            "$set": {
                "last_viewed": now,
                "evidence_status": "seen_only",
                "verification_required": True,
            },
            "$inc": {"lesson_views": 1},
            "$setOnInsert": {
                "user_id": user_id,
                "opening_key": resolved_key,
                "created_at": now,
                "mastery_level": "unknown",
            },
        },
        upsert=True,
    )
    progress = await db.opening_learning_progress.find_one(
        {"user_id": user_id, "opening_key": resolved_key}
    )
    return {
        "mastery_level": progress.get("mastery_level", "unknown"),
        "evidence_status": "seen_only",
        "verification_required": True,
    }
