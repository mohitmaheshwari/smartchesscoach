"""Searchable tags for a whole game, derived from its ledger.

Mohit, 2026-10-22: "each game should give us tags, so it becomes easy for us
to choose games from user and community, like
user_trapped_queen_opponent_missed ... user_trapped_opponent_rook".

Tags are DERIVED from the ledger (services.game_ledger) and the plan's
opening verdict, and from nothing else. So a tag can never say something the
game's story could not: one source of truth, read two ways.

Each tag also carries the moves behind it, so a lesson can open the exact
position instead of just the game.

Measured over 2,000 production games before the list was fixed: rare tags are
the valuable ones for choosing games (a trapped queen the opponent missed is
in 14 of 2,000), and some tags fire in most games (a punished blunder is in
three in four) and are only useful in combination.

Left out on purpose: executed tactics such as a fork. They are recorded only
once a game's review captions exist, which is after analysis, so new games
would never carry them.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional

GAME_TAGS_VERSION = "game_tags.v2"  # v2: absolute facts and named mistakes

# Detector-named mistakes, tagged only when the quality gate already lets a
# player be shown the name (QualitySurface.CAPTION). Readable ids for the
# common ones; any other authorised subtype is tagged as user_<subtype>.
_NAMED_MISTAKES = {
    "simple_hang": "user_hung_piece",
    "destination_safety_exact": "user_moved_piece_to_unsafe_square",
    "tactical_seq_loss": "user_lost_material_to_tactic",
    "ignored_king_attack": "user_ignored_king_attack",
    "missed_fork": "user_missed_fork",
    "missed_pin": "user_missed_pin",
    "missed_skewer": "user_missed_skewer",
    "missed_mate": "user_missed_mate",
}

# Tactical successes that make a game "tactically active": blunders punished,
# critical moves found, pieces shut in. Over 2,000 games half had two or more
# and 29% had three or more; three marks roughly the top third (Mohit agreed
# 2026-10-22).
TACTICALLY_ACTIVE_MIN = 3

_DANGER_TAGS = {
    "queen_trapped": "user_queen_trapped",
    "queen_lost": "user_queen_lost",
    "rook_trapped": "user_rook_trapped",
    "mate_allowed": "user_mate_allowed",
}


async def ensure_game_tag_indexes(db) -> None:
    """Tags are searched per player and across the community."""
    await db.game_analyses.create_index("game_tags")
    await db.game_analyses.create_index([("user_id", 1), ("game_tags", 1)])


def _named_mistake_allowed(quality_id: str) -> bool:
    """The one authority on whether a detector's name may be shown."""
    try:
        from services.detector_quality import QualitySurface, is_authorized

        return is_authorized(quality_id, QualitySurface.CAPTION)
    except Exception:
        return False


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower().replace("'", "")).strip("_")


def derive_game_tags(
    ledger: Mapping[str, Any],
    plan: Optional[Mapping[str, Any]] = None,
    *,
    game: Optional[Mapping[str, Any]] = None,
    observations: Optional[List[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """{"version", "ids": [sorted tag ids], "moves": {tag: [move refs]}}.

    `game` adds the absolute facts read off the PGN and headers
    (services.game_facts); `observations` adds the detector-named mistakes
    the quality gate allows a player to see.
    """
    moves: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    tactical = 0

    def add(tag: str, event: Optional[Mapping[str, Any]] = None):
        refs = moves[tag]
        if event is not None and event.get("san"):
            ref = {"move_number": event.get("move_number"), "san": event.get("san"),
                   "side": event.get("side")}
            if ref not in refs:
                refs.append(ref)

    for e in ledger.get("events") or []:
        kind = e.get("kind")
        if kind == "your_mistake":
            let_off = e.get("punished") is False
            danger = (e.get("danger") or {}).get("kind")
            if danger in _DANGER_TAGS:
                suffix = "opponent_missed" if let_off else "opponent_punished"
                add(f"{_DANGER_TAGS[danger]}_{suffix}", e)
            if e.get("decisive"):
                add("user_let_off" if let_off else "user_lost_winning_position", e)
        elif kind == "missed_mate":
            add("user_missed_mate", e)
        elif kind == "their_mistake" and e.get("decisive"):
            if e.get("taken"):
                add("user_punished_blunder", e)
                tactical += 1
            else:
                add("user_missed_their_blunder", e)
        elif kind == "you_boxed_in":
            add(f"user_trapped_opponent_{e.get('piece')}", e)
            if e.get("won_it"):
                add(f"user_won_trapped_{e.get('piece')}", e)
            tactical += 1
        elif kind == "your_good_move" and e.get("label") == "found_best_in_critical":
            add("user_found_critical_move", e)
            tactical += 1

    if tactical >= TACTICALLY_ACTIVE_MIN:
        add("user_tactically_active")

    outcome = ledger.get("outcome")
    if outcome in ("win", "loss", "draw"):
        add(f"result_{outcome}")

    opening = ledger.get("opening") or {}
    if opening.get("name") and opening.get("name") != "Other":
        add(f"opening_{_slug(opening['name'])}")
    from services.game_story_plan import opening_verdict
    verdict = opening_verdict(opening)
    add({"perfect": "opening_played_perfectly", "well": "opening_played_well",
         "better": "opening_came_out_better", "worse": "opening_came_out_worse",
         "level": "opening_came_out_level"}[verdict])

    if plan and (plan.get("type") or {}).get("id"):
        add(f"story_{plan['type']['id']}")

    if game is not None:
        from services.game_facts import game_facts

        for tag, refs in game_facts(game, outcome).items():
            moves[tag]
            for ref in refs:
                if ref not in moves[tag]:
                    moves[tag].append(ref)

    for observation in observations or []:
        subtype = observation.get("subtype")
        pattern = observation.get("missed_pattern")
        if not subtype or not pattern or not _named_mistake_allowed(f"gap:{pattern}:{subtype}"):
            continue
        tag = _NAMED_MISTAKES.get(str(subtype), f"user_{_slug(str(subtype))}")
        add(tag, {"move_number": observation.get("move_number"),
                  "san": observation.get("move_san"), "side": "you"})

    return {
        "version": GAME_TAGS_VERSION,
        "ids": sorted(moves),
        "moves": {tag: refs for tag, refs in moves.items() if refs},
    }
