"""Concept mastery tracker — Engine 2 Phase 1.

Closes the "knows what the user knows" feedback loop. Today's state
(2026-06-04): 1474 user_concept_understanding rows across 78 users,
99.7% with acknowledged=False, shown_count climbing without bound
(2223 for a single concept on Mohit's account). No code path increments
acknowledged based on demonstrated mastery — the only writer is a
button click ("/coach/decryption/acknowledge") that almost nobody uses.

This service auto-detects mastery from gameplay:

  - After each game is analyzed, walk the user's moves.
  - For every concept the user has been shown (rows in
    user_concept_understanding), check whether THIS GAME contained a
    violation of that concept.
  - Concept tracked as VIOLATED when any user mistake/blunder/serious
    move surfaces that concept in any of three signal fields:
      * principle_id_used                       (central pipeline)
      * plan.concept_id                         (V5 review plan)
      * caption_facts_principles_violated[].principle_id  (full list)
  - Streak logic:
      * Game violated concept → streak_clean reset to 0, acknowledged
        forced back to False (un-master on regression).
      * Game DIDN'T violate concept → streak_clean += 1.
      * When streak_clean ≥ streak_required (default 3) → mark
        acknowledged=True, set mastered_at timestamp.
  - Idempotent via last_evaluated_game_id — re-running the tracker on a
    game it already processed is a no-op.

Designed by Mohit 2026-06-04 as the foundation for Phases 2-4 (PWC
mastery gate, opening curriculum personalization, A/B rollout).
This is Phase 1: WRITE the mastery signal. Phase 2 reads it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

logger = logging.getLogger(__name__)


# ─── Configuration ──────────────────────────────────────────────────
# Default consecutive clean games to consider a concept mastered.
# Per-concept override via streak_required field on the user_concept_understanding doc.
DEFAULT_STREAK_REQUIRED = 3

# Severities counted as "violation". opp_* severities never count — those
# are opponent moves and don't reflect user understanding.
VIOLATING_SEVERITIES = {"mistake", "blunder", "serious"}


# ─── Pure helpers (testable without DB) ─────────────────────────────


def _concepts_referenced_on_move(rec: Dict[str, Any]) -> Set[str]:
    """All concepts/principles mentioned by any source on this move record,
    regardless of severity. This is the RELEVANCE signal."""
    if not isinstance(rec, dict):
        return set()
    out: Set[str] = set()
    pid = rec.get("principle_id_used")
    if pid:
        out.add(pid)
    plan = rec.get("plan") or {}
    if isinstance(plan, dict):
        cid = plan.get("concept_id")
        if cid:
            out.add(cid)
    for p in rec.get("caption_facts_principles_violated") or []:
        if isinstance(p, dict):
            ppid = p.get("principle_id")
            if ppid:
                out.add(ppid)
    return out


def extract_concepts_from_move(rec: Dict[str, Any]) -> Set[str]:
    """Pick up concepts on a user move with a mistake/blunder/serious severity.
    These are the VIOLATING fires — the move went wrong with respect to the concept.
    """
    if not isinstance(rec, dict):
        return set()
    if not rec.get("is_user_move"):
        return set()
    sev = rec.get("severity")
    if sev not in VIOLATING_SEVERITIES:
        return set()
    return _concepts_referenced_on_move(rec)


def extract_concepts_present_in_game(v5_data: Iterable[Dict[str, Any]]) -> Set[str]:
    """All concepts that appeared in any move's analysis (the user FACED them).
    Includes good moves where the concept fired with engine_endorsement=best,
    and opponent-mistake moves where the concept was the principle in play.

    A user move counts when the move is the user's. Opponent-move concepts
    are excluded — they reflect what the opponent did, not what the user
    demonstrated understanding of.
    """
    present: Set[str] = set()
    for rec in v5_data or ():
        if not isinstance(rec, dict):
            continue
        if not rec.get("is_user_move"):
            continue
        present |= _concepts_referenced_on_move(rec)
    return present


def extract_concepts_violated_in_game(v5_data: Iterable[Dict[str, Any]]) -> Set[str]:
    """Walk every user move and collect concepts that fired on a mistake/blunder.
    Subset of extract_concepts_present_in_game().
    """
    violated: Set[str] = set()
    for rec in v5_data or ():
        violated |= extract_concepts_from_move(rec)
    return violated


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── DB-bound updater ───────────────────────────────────────────────


def _concept_type_from_id(concept_id: str) -> str:
    """Map principle_id prefix to a concept_type bucket.

    Central pipeline emits TAC_/OP_/MID_/END_/DEF_/STR_ prefixed IDs.
    Older V5 plan namespace uses lowercase snake-case (piece_without_purpose,
    knight_fork). Default to 'general' for unknown prefixes.
    """
    if not concept_id:
        return "general"
    prefix_map = {
        "TAC_": "tactical",
        "OP_":  "opening",
        "MID_": "middlegame",
        "END_": "endgame",
        "DEF_": "defense",
        "STR_": "strategy",
    }
    for k, v in prefix_map.items():
        if concept_id.startswith(k):
            return v
    return "general"


async def _ensure_concept_rows_exist(
    db,
    user_id: str,
    concept_ids: Set[str],
    source_position: str,
    when: str,
) -> int:
    """Upsert user_concept_understanding rows for any concept_id that
    fired in this game but doesn't have a row yet. Returns count of new
    rows created.

    Solves the namespace mismatch (2026-06-04): the existing producer
    only emits the V5 plan namespace, but the central caption pipeline
    fires principle_id_used in TAC_/OP_/MID_ namespace. Without
    auto-create, mastery tracking has nothing to update.
    """
    if not concept_ids:
        return 0
    existing = set(await db.user_concept_understanding.distinct(
        "concept_id", {"user_id": user_id, "concept_id": {"$in": list(concept_ids)}}
    ))
    missing = concept_ids - existing
    if not missing:
        return 0
    docs = []
    for cid in missing:
        docs.append({
            "user_id": user_id,
            "concept_id": cid,
            "concept_type": _concept_type_from_id(cid),
            "concept_text": "",   # populated later when R-rule text is wired
            "shown_count": 0,
            "acknowledged": False,
            "source_position": source_position,
            "created_at": when,
            "updated_at": when,
        })
    try:
        await db.user_concept_understanding.insert_many(docs, ordered=False)
    except Exception as e:
        # ordered=False + race with the producer can yield dup-key errors
        # on parallel writes; that's fine, just continue.
        logger.info(f"[mastery] auto-create insert had dups (ok): {e}")
    return len(docs)


async def update_user_mastery_for_game(
    db,
    user_id: str,
    game_id: str,
    *,
    streak_required_default: int = DEFAULT_STREAK_REQUIRED,
) -> Dict[str, int]:
    """Apply per-concept streak updates after a single game.

    Idempotent: if the user_concept_understanding row already has
    last_evaluated_game_id == game_id, that concept is skipped.

    Returns a summary dict: {violated_count, clean_count, mastered_count,
    skipped_idempotent, no_concept_signal, autocreated}.
    """
    summary = {
        "violated_count": 0,
        "clean_count": 0,
        "mastered_count": 0,
        "skipped_idempotent": 0,
        "no_concept_signal": 0,
        "autocreated": 0,
    }

    ga = await db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "decryption_v5_data": 1, "analyzed_at": 1},
    )
    if not ga or not isinstance(ga.get("decryption_v5_data"), list):
        # No v5 data — nothing to evaluate. Caller is expected to run
        # this only after analysis completes and v5 renders.
        return summary

    v5 = ga["decryption_v5_data"]
    concepts_present = extract_concepts_present_in_game(v5)
    concepts_violated = extract_concepts_violated_in_game(v5)

    # Auto-create rows for any concept that fired but the user has no
    # row for yet (closes the namespace gap between plan.concept_id and
    # central-pipeline principle_id_used).
    now = _iso_now()
    if concepts_present:
        first_fen = ""
        for rec in v5:
            if isinstance(rec, dict) and rec.get("is_user_move"):
                first_fen = rec.get("fen_before") or ""
                break
        summary["autocreated"] = await _ensure_concept_rows_exist(
            db, user_id, concepts_present, first_fen, now,
        )

    # Walk every concept this user has on file.
    # - If the concept was NOT present in this game (the user never
    #   faced a situation where it applied), do nothing. Absence is NOT
    #   demonstration. This is the 2026-06-04 algorithm fix — original
    #   pass auto-mastered concepts that simply hadn't come up.
    # - If present + violated: streak=0, acknowledged=False.
    # - If present + clean: streak+=1; mastery fires at threshold.
    cursor = db.user_concept_understanding.find(
        {"user_id": user_id},
        {"_id": 1, "concept_id": 1, "streak_clean": 1, "streak_required": 1,
         "acknowledged": 1, "last_evaluated_game_id": 1, "clean_games_total": 1,
         "violations_total": 1},
    )
    now = _iso_now()
    async for cu in cursor:
        cid = cu.get("concept_id")
        if not cid:
            summary["no_concept_signal"] += 1
            continue
        if cu.get("last_evaluated_game_id") == game_id:
            summary["skipped_idempotent"] += 1
            continue
        # Hard skip when the concept didn't surface this game at all.
        if cid not in concepts_present:
            continue
        required = cu.get("streak_required") or streak_required_default
        if cid in concepts_violated:
            await db.user_concept_understanding.update_one(
                {"_id": cu["_id"]},
                {
                    "$set": {
                        "streak_clean": 0,
                        "acknowledged": False,
                        "last_violation_at": now,
                        "last_evaluated_game_id": game_id,
                        "updated_at": now,
                    },
                    "$inc": {"violations_total": 1},
                },
            )
            summary["violated_count"] += 1
        else:
            new_streak = (cu.get("streak_clean") or 0) + 1
            update_set: Dict[str, Any] = {
                "streak_clean": new_streak,
                "last_clean_game_at": now,
                "last_evaluated_game_id": game_id,
                "updated_at": now,
            }
            mastered_now = (
                new_streak >= required and not cu.get("acknowledged")
            )
            if mastered_now:
                update_set["acknowledged"] = True
                update_set["mastered_at"] = now
            await db.user_concept_understanding.update_one(
                {"_id": cu["_id"]},
                {"$set": update_set, "$inc": {"clean_games_total": 1}},
            )
            summary["clean_count"] += 1
            if mastered_now:
                summary["mastered_count"] += 1

    return summary


async def update_user_mastery_for_recent_games(
    db,
    user_id: str,
    *,
    max_games: int = 100,
) -> Dict[str, Any]:
    """Re-evaluate the user's most recent analyzed games in order.

    Replays streak math forward in time so backfilling produces the same
    state lazy per-game evaluation would. Used by
    backfill_concept_mastery.py and by the prod hook on first-time
    deployment.
    """
    # Pull recent analyzed games for this user, oldest first so streaks
    # accumulate correctly.
    cursor = db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "imported_at": 1, "date_played": 1},
    ).sort([("date_played", 1), ("imported_at", 1)]).limit(max_games)
    games = await cursor.to_list(max_games)

    totals = {
        "games_processed": 0,
        "violated_count": 0,
        "clean_count": 0,
        "mastered_count": 0,
        "skipped_idempotent": 0,
    }
    for g in games:
        gid = g.get("game_id")
        if not gid:
            continue
        s = await update_user_mastery_for_game(db, user_id, gid)
        totals["games_processed"] += 1
        for k in ("violated_count", "clean_count", "mastered_count", "skipped_idempotent"):
            totals[k] += s.get(k, 0)
    return totals
