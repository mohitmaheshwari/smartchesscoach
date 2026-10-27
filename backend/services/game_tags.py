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
from typing import Any, Dict, List, Mapping, Optional  # noqa: F401

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


# One small document per game: its id, owner, tag ids and the moves behind
# them. Counting and searching tags MUST read this, never game_analyses.
#
# 2026-10-22: the first version counted tags by aggregating game_analyses,
# whose documents average 301 KB (5.9 GB in all). Every Review Queue load
# made Mongo read all of it, took over 90 seconds, and returned a 504 -- on a
# host already short of memory, where it added to the pressure. This
# collection is a derived index of game_story.tags, rebuilt whenever a story
# is written; game_story stays the source.
TAG_INDEX_COLLECTION = "game_tag_index"


async def ensure_game_tag_indexes(db) -> None:
    """Tags are searched per player and across the community."""
    index = db[TAG_INDEX_COLLECTION]
    await index.create_index("game_id", unique=True)
    await index.create_index("tags")
    await index.create_index([("user_id", 1), ("tags", 1)])
    # "Regenerated only" in the Review Queue scans for this field. Without an
    # index it read every 301 KB analysis (60 s, at the gateway's limit).
    #
    # PARTIAL, not sparse: a sparse compound index holds every document that
    # has ANY of its fields, and every analysis has a game_id, so the first
    # (sparse) version indexed all 19,032 and the query still opened each one
    # (28 s). The partial index holds only analyses that were regenerated,
    # so the query is answered from the index alone.
    info = await db.game_analyses.index_information()
    if "decryption_v5_regen_at_1_game_id_1" in info and info[
            "decryption_v5_regen_at_1_game_id_1"].get("sparse"):
        await db.game_analyses.drop_index("decryption_v5_regen_at_1_game_id_1")
    await db.game_analyses.create_index(
        [("decryption_v5_regen_at", 1), ("game_id", 1)],
        name="regen_at_game_id_partial",
        partialFilterExpression={"decryption_v5_regen_at": {"$exists": True}},
    )


def tag_index_doc(game_id: str, user_id: Optional[str], tags: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    tags = tags or {}
    return {
        "game_id": game_id,
        "user_id": user_id,
        "tags": list(tags.get("ids") or []),
        "moves": dict(tags.get("moves") or {}),
        "version": tags.get("version"),
    }


# ─── The games list ─────────────────────────────────────────────────────

# Tags a player sees on their games list. Internal or repeated ones
# (result_, story_, ended_, time_control_, opening families) are left out:
# the row already shows the result, and the title carries the story.
_LIST_TAG = re.compile(r"^(user_|opening_played_|opening_came_out_worse$)")
# Bare facts describe a game without saying how it went, so they would take a
# slot from a tag that teaches (Mohit, 2026-10-27). They stay searchable in
# the Review Queue.
_LIST_BARE_FACT = re.compile(r"^(user_castled_|user_promoted_a_pawn$|user_underpromoted$|"
                             r"user_captured_en_passant$|user_in_time_scramble$|reached_|"
                             r"opposite_side_castling$|queens_traded_early$|long_game$)")
_LIST_LABELS = {
    "user_let_off": "let off by the opponent",
    "user_lost_winning_position": "lost a winning position",
    "user_punished_blunder": "punished a blunder",
    "user_missed_their_blunder": "missed their blunder",
    "user_tactically_active": "tactically active",
    "user_found_critical_move": "found a critical move",
    "user_missed_mate": "missed a mate",
    "user_hung_piece": "left a piece undefended",
    "user_moved_piece_to_unsafe_square": "moved a piece to an unsafe square",
    "user_lost_material_to_tactic": "lost material to a tactic",
    "user_ignored_king_attack": "missed a threat to the king",
    "opening_came_out_worse": "worse out of the opening",
    "opening_played_well": "played the opening well",
    "opening_played_perfectly": "played the opening perfectly",
}
LIST_TAG_LIMIT = 3
_counts_cache: Dict[str, Any] = {"at": 0.0, "counts": {}}


_MATE_LABEL = {"back_rank_mate": "back rank mate", "smothered_mate": "smothered mate",
               "double_check_mate": "mate with a double check"}


def list_tag_label(tag: str) -> str:
    if tag in _LIST_LABELS:
        return _LIST_LABELS[tag]
    m = re.match(r"^user_won_trapped_(\w+)$", tag)
    if m:
        return f"trapped and won their {m.group(1)}"
    m = re.match(r"^user_trapped_opponent_(\w+)$", tag)
    if m:
        return f"shut in their {m.group(1)}"
    m = re.match(r"^user_(delivered|suffered)_(\w+_mate)$", tag)
    if m:
        who, kind = m.groups()
        if kind in _MATE_LABEL:
            return f"{_MATE_LABEL[kind]} {'for you' if who == 'delivered' else 'against you'}"
        piece = kind.replace("_mate", "")
        return f"mated with the {piece}" if who == "delivered" else f"mated by their {piece}"
    text = re.sub(r"^user_", "", tag).replace("_", " ")
    return text.replace(" opponent missed", ", opponent missed") \
               .replace(" opponent punished", ", opponent punished")


async def _global_tag_counts(db) -> Dict[str, int]:
    """How many games carry each tag, refreshed every ten minutes, from the
    slim records (0.3 s), so the rarest tags can be shown first."""
    import time

    if time.time() - _counts_cache["at"] < 600 and _counts_cache["counts"]:
        return _counts_cache["counts"]
    rows = await db[TAG_INDEX_COLLECTION].aggregate([
        {"$project": {"_id": 0, "tags": 1}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "n": {"$sum": 1}}},
    ]).to_list(length=None)
    _counts_cache.update(at=time.time(), counts={r["_id"]: r["n"] for r in rows})
    return _counts_cache["counts"]


async def list_fields_for_games(db, game_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Per game: the saved title and up to three readable tags, rarest first.

    Reads only saved headlines and the slim tag records -- never calls the
    model, so loading a games list costs nothing and stays fast.
    """
    ids = [g for g in game_ids if g]
    if not ids:
        return {}
    from services.game_headline import COLLECTION as HEADLINES

    out: Dict[str, Dict[str, Any]] = {g: {"story_title": None, "story_tags": []} for g in ids}
    async for h in db[HEADLINES].find({"game_id": {"$in": ids}}, {"_id": 0, "game_id": 1, "title": 1}):
        out[h["game_id"]]["story_title"] = h.get("title")
    counts = await _global_tag_counts(db)
    async for t in db[TAG_INDEX_COLLECTION].find({"game_id": {"$in": ids}}, {"_id": 0, "game_id": 1, "tags": 1}):
        tags = set(t.get("tags") or [])
        # "trapped and won their knight" already says "shut in their knight".
        for tag in list(tags):
            m = re.match(r"^user_won_trapped_(\w+)$", tag)
            if m:
                tags.discard(f"user_trapped_opponent_{m.group(1)}")
        shown = sorted((tag for tag in tags if _LIST_TAG.match(tag) and not _LIST_BARE_FACT.match(tag)),
                       key=lambda tag: (counts.get(tag, 0), tag))[:LIST_TAG_LIMIT]
        out[t["game_id"]]["story_tags"] = [{"id": tag, "label": list_tag_label(tag)} for tag in shown]
    return out


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
