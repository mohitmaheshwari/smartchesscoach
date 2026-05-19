"""
Per-user teaching-memory index — the storage layer for cross-game recall.

Phase 2.0 (Mohit signoff 2026-05-19). The "chess memory system" foundation.
This service writes/reads the `user_teaching_memory` collection, which
catalogs every teaching-gold moment in a player's history with the
richer geometric / behavioral / identity-level hooks that future
recall layers (2.6+) will populate.

The collection is the persistent backbone for:
  Level 1 — principle recall ("you've missed this pin idea before")
  Level 2 — geometry recall ("bishop-on-f7 pressure keeps appearing")
  Level 3 — behavior recall ("you trust pinned pieces when uncastled")
  Level 4 — identity recall ("you favor material over king safety")

V1 (this commit) populates Level 1 fields and reserves Level 2-4 fields
empty so future layers can fill in without a schema migration.

Document shape (one row per gold-class teaching moment per user-game-ply):
{
  "user_id":              str,
  "game_id":              str,
  "move_number":          int,
  "ply":                  int,
  "occurred_at":          datetime,
  "user_color":           "white" | "black",
  "user_rating_at_time":  int | None,
  "opponent":             str | None,
  "time_control":         str | None,     # blitz / rapid / daily — for similarity matching
  "result":               str,            # 1-0 / 0-1 / 1/2-1/2

  # Layer 1 — principle keys
  "principle_id":         str | None,
  "shape_pattern_id":     str | None,
  "source":               "v5" | "trap",  # which detector wrote this
  "gold_class":           str,            # gold / lucky / warning / celebration

  # Layer 2 hooks — geometry recall (populated NOW where we have it)
  "state_key":            list | None,    # the V5 state_key (tuple stored as list for BSON)
  "focal_squares":        list[str],      # squares the lesson is about
  "fen_before":           str,
  "fen_after":            str | None,
  "best_move_san":        str | None,
  "played_san":           str | None,
  "cp_loss":              int,

  # Layer 3 hooks — behavior recall (empty in V1, schema reserved)
  "move_time_seconds":    int | None,
  "alternatives_considered": list,
  "time_pressure_flag":   bool,

  # Layer 4 hooks — identity recall (derived later via clustering)
  "behavioral_tags":      list[str],

  # The "what could have happened" — emotional anchor for recall voice
  "best_move_consequence": str | None,    # e.g. "wins queen" / "mate in 2"
  "narrative":            str | None,     # the V5 narrative if present
  "anchor_name":          str | None,     # e.g. "Loose piece on the board"

  # Indexing aids
  "memory_version":       int,
}

Indexes:
  - (user_id, occurred_at desc)         — recency queries
  - (user_id, principle_id, occurred_at desc)  — principle recall
  - (user_id, gold_class)               — bucket queries
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Bump when the schema or what we extract changes.
TEACHING_MEMORY_VERSION = 1


def _extract_focal_squares(move_record: Dict[str, Any]) -> List[str]:
    """Pull the focal squares from a V5 move record.

    Prefers explicit shape_pattern_targets when present (most precise),
    falls back to the played_san destination square (last 2 chars of
    SAN ignoring annotations).
    """
    out: List[str] = []
    targets = move_record.get("shape_pattern_targets") or []
    if isinstance(targets, list):
        for t in targets:
            if isinstance(t, str) and len(t) == 2 and t[0] in "abcdefgh" and t[1] in "12345678":
                out.append(t)
    if not out:
        san = (move_record.get("move_san") or "").rstrip("+#?!")
        # Last 2 chars typically the destination square for normal moves
        if len(san) >= 2 and san[-2] in "abcdefgh" and san[-1] in "12345678":
            out.append(san[-2:])
    return out


def _state_key_to_list(state_key: Any) -> Optional[List]:
    """BSON can't store tuples — convert state_key (tuple of tuples) to
    a nested list. Returns None when not present."""
    if state_key is None:
        return None
    if isinstance(state_key, (list, tuple)):
        return [
            _state_key_to_list(x) if isinstance(x, (list, tuple)) else x
            for x in state_key
        ]
    return state_key


def _user_rating_at_time(
    user_doc: Optional[Dict[str, Any]],
    game_doc: Optional[Dict[str, Any]],
) -> Optional[int]:
    """Best-effort: prefer rating stored on the game (Chess.com headers
    captured it at game time), fall back to user's current rating."""
    if game_doc:
        r = game_doc.get("user_rating") or game_doc.get("user_rating_at_time")
        if isinstance(r, int) and r > 0:
            return r
    if user_doc:
        r = user_doc.get("rating") or user_doc.get("current_rating")
        if isinstance(r, int) and r > 0:
            return r
    return None


def _opponent_for_user_color(game_doc: Dict[str, Any]) -> Optional[str]:
    """Return the opponent's name. Used for index queries, NOT for voice
    rendering — recall voice strips opponent names per privacy rule."""
    if not game_doc:
        return None
    return (
        game_doc.get("opponent_username")
        or game_doc.get("opponent")
        or None
    )


def _build_memory_doc_from_v5_move(
    *,
    user_id: str,
    game_id: str,
    user_color: str,
    move_record: Dict[str, Any],
    gold_class: str,
    user_rating_at_time: Optional[int],
    opponent: Optional[str],
    time_control: Optional[str],
    result: Optional[str],
    occurred_at: datetime,
) -> Dict[str, Any]:
    """Compose one user_teaching_memory document from a V5 decryption move.

    `gold_class` is the caller's classification — V5 doesn't tag fires
    directly. The caller filters and labels (see backfill script).
    """
    return {
        "user_id": user_id,
        "game_id": game_id,
        "move_number": move_record.get("move_number"),
        "ply": move_record.get("ply"),
        "occurred_at": occurred_at,
        "user_color": user_color,
        "user_rating_at_time": user_rating_at_time,
        "opponent": opponent,
        "time_control": time_control,
        "result": result,

        # Layer 1
        "principle_id": move_record.get("principle_id_used") or move_record.get("principle_id"),
        "shape_pattern_id": move_record.get("shape_pattern_id"),
        "source": "v5",
        "gold_class": gold_class,

        # Layer 2 hooks
        "state_key": _state_key_to_list(move_record.get("state_key")),
        "focal_squares": _extract_focal_squares(move_record),
        "fen_before": move_record.get("fen_before") or "",
        "fen_after": move_record.get("fen_after"),
        "best_move_san": move_record.get("best_move_san"),
        "played_san": move_record.get("move_san"),
        "cp_loss": int(move_record.get("cp_loss") or 0),

        # Layer 3 hooks (reserved, empty in V1)
        "move_time_seconds": None,
        "alternatives_considered": [],
        "time_pressure_flag": False,

        # Layer 4 hooks (reserved, derived later)
        "behavioral_tags": [],

        # Voice / emotional anchor inputs
        "best_move_consequence": _consequence_from_narrative(
            move_record.get("narrative") or ""
        ),
        "narrative": (move_record.get("narrative") or "")[:280],
        "anchor_name": move_record.get("anchor_name"),

        "memory_version": TEACHING_MEMORY_VERSION,
    }


def _build_memory_doc_from_trap_fire(
    *,
    user_id: str,
    game_id: str,
    trap_fire: Dict[str, Any],
    user_rating_at_time: Optional[int],
    opponent: Optional[str],
    time_control: Optional[str],
    result: Optional[str],
    occurred_at: datetime,
) -> Dict[str, Any]:
    """Compose one user_teaching_memory document from a trap_fires entry."""
    return {
        "user_id": user_id,
        "game_id": game_id,
        "move_number": None,                  # trap_fires are setup-keyed, not ply-keyed
        "ply": trap_fire.get("setup_reached_ply"),
        "occurred_at": occurred_at,
        "user_color": trap_fire.get("user_color"),
        "user_rating_at_time": user_rating_at_time,
        "opponent": opponent,
        "time_control": time_control,
        "result": result,

        # Layer 1 — traps don't have V5 principle_id; use a synthetic
        # principle_id prefixed with TRAP: for joinability.
        "principle_id": f"TRAP:{trap_fire.get('trap_name', 'unknown')}",
        "shape_pattern_id": None,
        "source": "trap",
        "gold_class": trap_fire.get("gold_class") or "none",

        # Layer 2
        "state_key": None,
        "focal_squares": [],
        "fen_before": "",                    # trap_fires don't carry FEN
        "fen_after": None,
        "best_move_san": None,
        "played_san": None,
        "cp_loss": 0,

        # Layer 3 / 4 reserved
        "move_time_seconds": None,
        "alternatives_considered": [],
        "time_pressure_flag": False,
        "behavioral_tags": [],

        # Voice anchor
        "best_move_consequence": trap_fire.get("description") or None,
        "narrative": trap_fire.get("description") or None,
        "anchor_name": trap_fire.get("trap_name"),

        "memory_version": TEACHING_MEMORY_VERSION,
    }


def _consequence_from_narrative(narrative: str) -> Optional[str]:
    """Extract a short "what could have happened" phrase from a V5
    narrative. Looks for phrases like 'wins the queen', 'mate in 2',
    'wins a piece', etc. Returns None if no clear consequence found.

    This is intentionally string-heuristic for V1; later layers should
    have a structured field on the move record itself.
    """
    if not narrative:
        return None
    s = narrative.lower()
    keywords = [
        "wins the queen", "wins a queen", "wins the rook", "wins a rook",
        "wins the bishop", "wins a bishop", "wins the knight", "wins a knight",
        "wins a piece", "wins material", "wins a pawn",
        "mate in 1", "mate in 2", "mate in 3", "forces mate",
        "wins the exchange",
    ]
    for k in keywords:
        if k in s:
            return k
    return None


def _gold_classify_v5_move(move_record: Dict[str, Any], user_color: str) -> str:
    """Classify a V5 move record into gold/celebration/lucky/warning/none.

    Mirrors the logic from rank_teaching_gold.py but at single-move
    granularity:
      GOLD        — fire on user's move, user didn't play best, cp_loss >= 80
      CELEBRATION — fire on user's move, user played best
      LUCKY       — fire on opp's move, opp didn't play best, cp_loss >= 150
      WARNING     — fire on opp's move, opp played best (or close)
    """
    has_fire = bool(
        move_record.get("principle_id_used")
        or move_record.get("principle_id")
        or move_record.get("shape_pattern_id")
    )
    if not has_fire:
        return "none"

    is_user_move = bool(move_record.get("is_user_move"))
    move_san = (move_record.get("move_san") or "").rstrip("+#?!")
    best_san = (move_record.get("best_move_san") or "").rstrip("+#?!")
    played_best = bool(best_san) and (move_san == best_san)

    cp_loss = int(move_record.get("cp_loss") or 0)
    if cp_loss > 2000:  # mate-score artifact
        cp_loss = 0

    if is_user_move:
        if not played_best and cp_loss >= 80:
            return "gold"
        return "celebration"
    else:
        if not played_best and cp_loss >= 150:
            return "lucky"
        return "warning"


async def ensure_indexes(db) -> None:
    """Create the recommended indexes on user_teaching_memory.

    Idempotent — Mongo only creates if missing.
    """
    try:
        await db.user_teaching_memory.create_index([("user_id", 1), ("occurred_at", -1)])
        await db.user_teaching_memory.create_index(
            [("user_id", 1), ("principle_id", 1), ("occurred_at", -1)]
        )
        await db.user_teaching_memory.create_index([("user_id", 1), ("gold_class", 1)])
        # Dedup guard: (user_id, game_id, ply, source) — for idempotent backfills
        await db.user_teaching_memory.create_index(
            [("user_id", 1), ("game_id", 1), ("ply", 1), ("source", 1)],
            unique=False,  # not unique because trap fires share ply with v5 fires
        )
    except Exception as e:
        logger.warning(f"[teaching_memory_index] index creation failed (non-fatal): {e}")


async def upsert_memory_entry(db, doc: Dict[str, Any]) -> bool:
    """Idempotent write. Key: (user_id, game_id, ply, source, principle_id)."""
    try:
        await db.user_teaching_memory.update_one(
            {
                "user_id": doc["user_id"],
                "game_id": doc["game_id"],
                "ply": doc.get("ply"),
                "source": doc["source"],
                "principle_id": doc.get("principle_id"),
            },
            {"$set": doc},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.warning(f"[teaching_memory_index] upsert failed for {doc.get('game_id')}: {e}")
        return False


async def index_game_v5_data(
    db,
    *,
    user_id: str,
    game_id: str,
    user_color: str,
    user_rating_at_time: Optional[int],
    opponent: Optional[str],
    time_control: Optional[str],
    result: Optional[str],
    occurred_at: datetime,
    decryption_v5_data: List[Dict[str, Any]],
) -> int:
    """Walk the V5 move list and upsert one memory entry per gold-class
    fire. Returns count of entries written."""
    count = 0
    for m in decryption_v5_data or []:
        gold_class = _gold_classify_v5_move(m, user_color)
        if gold_class in ("none", "warning"):
            # warning = opp played principle correctly against user;
            # interesting for review but lower-value for recall MVP.
            # (Leave warning OUT of V1 memory index; can revisit if
            # playtest signal says users WANT to be reminded of how
            # opponents beat them with named ideas.)
            continue
        doc = _build_memory_doc_from_v5_move(
            user_id=user_id,
            game_id=game_id,
            user_color=user_color,
            move_record=m,
            gold_class=gold_class,
            user_rating_at_time=user_rating_at_time,
            opponent=opponent,
            time_control=time_control,
            result=result,
            occurred_at=occurred_at,
        )
        if doc["principle_id"] or doc["shape_pattern_id"]:
            ok = await upsert_memory_entry(db, doc)
            if ok:
                count += 1
    return count


async def index_game_trap_fires(
    db,
    *,
    user_id: str,
    game_id: str,
    user_rating_at_time: Optional[int],
    opponent: Optional[str],
    time_control: Optional[str],
    result: Optional[str],
    occurred_at: datetime,
    trap_fires: List[Dict[str, Any]],
) -> int:
    """Walk the trap_fires list and upsert one memory entry per gold or
    lucky fire. Returns count of entries written."""
    count = 0
    for t in trap_fires or []:
        gc = t.get("gold_class")
        if gc not in ("gold", "lucky"):
            continue
        doc = _build_memory_doc_from_trap_fire(
            user_id=user_id,
            game_id=game_id,
            trap_fire=t,
            user_rating_at_time=user_rating_at_time,
            opponent=opponent,
            time_control=time_control,
            result=result,
            occurred_at=occurred_at,
        )
        ok = await upsert_memory_entry(db, doc)
        if ok:
            count += 1
    return count
