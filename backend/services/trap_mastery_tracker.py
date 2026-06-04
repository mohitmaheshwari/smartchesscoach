"""Trap mastery tracker — Engine 2 trap-side counterpart to concept_mastery_tracker.

Today (2026-06-04) `user_opening_mastery` documents have these fields
declared but never populated:
  traps_encountered: []
  traps_fallen_for:  []
  traps_handled:     []

54 traps are defined in data/traps.json across 28 opening contexts, and
trap_scanner.py fires them onto game_analyses.trap_fires. But nothing
threads the user's actual response back into the mastery record. The
result: PWC can't tell whether you've SEEN the Fried Liver and FALLEN
for it or SEEN it and HANDLED it.

This service closes that loop. After each game is analyzed, for every
trap fire on that game:

  - Mark it in user_opening_mastery.traps_encountered (idempotent set).
  - Determine outcome:
      * trap_setter is user, completed_by_user=True → trap landed (handled offensively)
      * trap_setter is user, completed_by_user=False → trap missed (didn't punish opp)
      * trap_setter is opponent, completed_by_user=False (user avoided) → trap_handled
      * trap_setter is opponent, completed_by_user=True (user fell into) → trap_fallen_for

Idempotency via the trap fire's unique signature (trap_name + start_ply).
Re-runs on the same (user, game, trap) are no-ops.

The producer side of trap_scanner.py emits each fire with at least:
  trap_name, role ("setter"/"punisher"), start_ply, completed_by_user (bool)

If completed_by_user isn't set, treat the fire as "encountered" only.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _opening_key_for_trap(trap_fire: Dict[str, Any]) -> Optional[str]:
    """Pull the opening_key the trap belongs to.

    Mohit 2026-06-04: traps.json + trap_scanner emit opening_key with
    DASHES ("italian-game") while user_opening_mastery rows use
    UNDERSCORES ("italian_game"). Normalize to underscores so lookups
    against user_opening_mastery match.
    """
    raw = trap_fire.get("opening_key") or trap_fire.get("opening")
    if not raw:
        return None
    return raw.replace("-", "_")


def _classify_outcome(trap_fire: Dict[str, Any]) -> str:
    """Classify a single trap_fire into: handled / fallen_for / encountered.

    Actual schema (Mohit 2026-06-04, verified against 200 game sample):
      role: "setter" or "victim"
      full_sprung: bool — did the trap fully complete?
      sprung_moves: int — how many moves of the trap_line were played

    Outcomes:
      victim + full_sprung=True             → "fallen_for"
                                                user fully fell into the trap
      victim + full_sprung=False + sprung>0 → "handled"
                                                user started falling, escaped
                                                — demonstrates they know it
      victim + full_sprung=False + sprung=0 → "encountered"
                                                user reached setup position
                                                but trap wasn't initiated
      setter + full_sprung=True             → "handled_offense"
                                                user landed the trap
      setter + full_sprung=False            → "encountered"
                                                user set up but trap didn't
                                                trigger (e.g. opp didn't fall)
    """
    role = trap_fire.get("role")
    full_sprung = bool(trap_fire.get("full_sprung", False))
    sprung_moves = int(trap_fire.get("sprung_moves") or 0)
    if role == "victim":
        if full_sprung:
            return "fallen_for"
        if sprung_moves > 0:
            return "handled"
        return "encountered"
    if role == "setter":
        if full_sprung:
            return "handled_offense"
        return "encountered"
    return "encountered"


async def update_trap_mastery_for_game(
    db,
    user_id: str,
    game_id: str,
) -> Dict[str, int]:
    """Walk game's trap_fires and update user_opening_mastery traps fields.

    Idempotent via trap_fire signature (trap_name + start_ply) tracked in
    each opening_mastery row's `_evaluated_trap_fires` set.
    """
    summary = {
        "fires_seen": 0,
        "newly_encountered": 0,
        "newly_handled": 0,
        "newly_fallen_for": 0,
        "missed": 0,
    }

    ga = await db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "trap_fires": 1},
    )
    fires = (ga or {}).get("trap_fires") or []
    if not fires:
        return summary

    now = _iso_now()
    # Group fires by opening_key — one update per opening row.
    by_opening: Dict[str, List[Dict[str, Any]]] = {}
    for tf in fires:
        if not isinstance(tf, dict):
            continue
        ok = _opening_key_for_trap(tf)
        if not ok:
            continue
        by_opening.setdefault(ok, []).append(tf)

    for opening_key, opening_fires in by_opening.items():
        row = await db.user_opening_mastery.find_one(
            {"user_id": user_id, "opening_key": opening_key},
            {
                "_id": 1,
                "traps_encountered": 1,
                "traps_fallen_for": 1,
                "traps_handled": 1,
                "_evaluated_trap_fires": 1,
            },
        )
        if not row:
            # No opening mastery row yet — auto-create a minimal one so
            # trap mastery isn't silently dropped on users who have
            # traps but haven't yet had the opening_mastery_tracker fire
            # for them. opening_mastery_tracker will fill in
            # accuracy/phase/games_played on its next run.
            insert_doc = {
                "user_id": user_id,
                "opening_key": opening_key,
                "phase": "introduction",
                "games_played": 0,
                "accuracy_history": [],
                "moves_correct": 0,
                "moves_total": 0,
                "traps_encountered": [],
                "traps_fallen_for": [],
                "traps_handled": [],
                "branches_seen": [],
                "_evaluated_trap_fires": [],
                "created_at": now,
                "updated_at": now,
            }
            try:
                result = await db.user_opening_mastery.insert_one(insert_doc)
                row = {**insert_doc, "_id": result.inserted_id}
            except Exception as e:
                logger.info(f"[trap-mastery] auto-create skipped (dup ok): {e}")
                row = await db.user_opening_mastery.find_one(
                    {"user_id": user_id, "opening_key": opening_key},
                    {"_id": 1, "traps_encountered": 1, "traps_fallen_for": 1,
                     "traps_handled": 1, "_evaluated_trap_fires": 1},
                )
                if not row:
                    continue
        evaluated = set(row.get("_evaluated_trap_fires") or [])
        encountered = set(row.get("traps_encountered") or [])
        fallen = set(row.get("traps_fallen_for") or [])
        handled = set(row.get("traps_handled") or [])
        changed = False

        for tf in opening_fires:
            name = tf.get("trap_name") or tf.get("name")
            if not name:
                continue
            sig = f"{name}::{tf.get('start_ply', '?')}::{game_id}"
            if sig in evaluated:
                continue
            evaluated.add(sig)
            summary["fires_seen"] += 1
            outcome = _classify_outcome(tf)
            if name not in encountered:
                encountered.add(name)
                summary["newly_encountered"] += 1
                changed = True
            if outcome == "handled" or outcome == "handled_offense":
                if name not in handled:
                    handled.add(name)
                    summary["newly_handled"] += 1
                    changed = True
                # If handled now after previously falling for it, REMOVE
                # from fallen_for — they've corrected the mistake.
                if name in fallen:
                    fallen.discard(name)
                    changed = True
            elif outcome == "fallen_for":
                if name not in fallen:
                    fallen.add(name)
                    summary["newly_fallen_for"] += 1
                    changed = True
            elif outcome == "missed_punish":
                summary["missed"] += 1

        if changed:
            await db.user_opening_mastery.update_one(
                {"_id": row["_id"]},
                {
                    "$set": {
                        "traps_encountered": sorted(encountered),
                        "traps_fallen_for": sorted(fallen),
                        "traps_handled": sorted(handled),
                        "_evaluated_trap_fires": sorted(evaluated),
                        "updated_at": now,
                    },
                },
            )

    return summary
