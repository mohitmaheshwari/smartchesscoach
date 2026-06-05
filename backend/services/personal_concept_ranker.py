"""Personal concept ranker — UnifiedProgress v2 (Path A).

Built 2026-06-05. Backs the "Currently working on" enrichment on the
Progress page: per-user, per-weakness-bucket, surface the dominant
concept under Formula C with recurrence + most-recent-game metadata so
the page can render a pattern-led narrative + Review-game CTA.

Formula C was locked via bake-off across 10 stratified users
(docs/unified_progress_v2_scope.md Q1 LOCKED 2026-06-05).

  score(concept) = decay_sum × max(median_cp, p75_cp / 2)

  decay_sum   = Σ  0.85 ^ (games_back_for_this_violation)
  median_cp   = median cp_loss across violation events
  p75_cp      = 75th percentile cp_loss across violation events
  cp_loss     = capped at 1000 (mate-score cap)

Eligibility (Combo 6):  recurrence ≥ 5  AND  (median_cp ≥ 150  OR  p75_cp ≥ 300)
Family cap:             one card per TAC_/OP_/MID_/END_/DEF_/STR_/legacy

V1 known follow-ups (documented in scope §6, deferred to V1.1):
  - Family cap is the bottleneck for 4 of 10 users — soften when only
    one family has eligible concepts
  - p75=1000 mate-cap creates an artifact — V1.1 will clip p75 to 700
"""
from __future__ import annotations

import logging
import statistics
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ─── Formula C constants ────────────────────────────────────────────

DECAY_RATE = 0.85           # matches pattern_decay_service
CP_LOSS_CAP = 1000          # mate-score cap

# Eligibility filter (Combo 6)
ELIGIBILITY_MIN_RECURRENCE = 5
ELIGIBILITY_MIN_MEDIAN_CP = 150
ELIGIBILITY_MIN_P75_CP = 300

# Default lookback for violation events (games)
DEFAULT_LOOKBACK_GAMES = 50

# Family prefixes — central pipeline namespace + legacy fallback
FAMILY_PREFIXES = ("TAC_", "OP_", "MID_", "END_", "DEF_", "STR_")


# ─── Concept_id → family bucket ─────────────────────────────────────


def family_for_concept(concept_id: str) -> str:
    """Map a concept_id to a family bucket. Anything that doesn't carry
    a known prefix is bucketed under 'legacy'. Family cap uses this.
    """
    if not concept_id:
        return "legacy"
    for prefix in FAMILY_PREFIXES:
        if concept_id.startswith(prefix):
            return prefix.rstrip("_").lower()
    return "legacy"


# ─── Per-game concept event extraction ──────────────────────────────


def _violation_events_for_game(v5_data: List[Dict[str, Any]]) -> List[Tuple[str, int]]:
    """Walk a single game's v5_data and return (concept_id, cp_loss)
    pairs for each user-side violation (mistake/blunder/serious).
    cp_loss is capped at CP_LOSS_CAP.
    """
    events: List[Tuple[str, int]] = []
    VIOLATING = {"mistake", "blunder", "serious"}
    for rec in v5_data or ():
        if not isinstance(rec, dict):
            continue
        if not rec.get("is_user_move"):
            continue
        if rec.get("severity") not in VIOLATING:
            continue
        cp = int(rec.get("cp_loss") or 0)
        if cp <= 0:
            continue
        cp = min(cp, CP_LOSS_CAP)
        # Pull every concept identifier carried by this move record.
        # principle_id_used wins when present; plan.concept_id and
        # caption_facts_principles_violated[].principle_id are fallbacks.
        seen_on_move: Set[str] = set()
        pid = rec.get("principle_id_used")
        if pid:
            seen_on_move.add(pid)
        plan = rec.get("plan") or {}
        if isinstance(plan, dict):
            cid = plan.get("concept_id")
            if cid:
                seen_on_move.add(cid)
        for p in rec.get("caption_facts_principles_violated") or []:
            if isinstance(p, dict):
                ppid = p.get("principle_id")
                if ppid:
                    seen_on_move.add(ppid)
        for cid in seen_on_move:
            events.append((cid, cp))
    return events


# ─── Formula C scoring ──────────────────────────────────────────────


def _score_formula_c(events: List[int], games_back: List[int]) -> float:
    """Formula C: decay_sum × max(median_cp, p75_cp / 2).

    Args:
        events: list of cp_loss values (one per violation), capped at
            CP_LOSS_CAP by the caller.
        games_back: parallel list — how many games back the violation
            occurred (most-recent game = 0).

    The two lists must be the same length. cp_loss values are unsorted;
    we compute the order statistics here.
    """
    if not events or not games_back or len(events) != len(games_back):
        return 0.0
    decay_sum = sum(DECAY_RATE ** gb for gb in games_back)
    sorted_cp = sorted(events)
    median_cp = statistics.median(sorted_cp)
    # statistics.quantiles requires n>=2; for n=1 use the value itself.
    if len(sorted_cp) >= 2:
        # 75th percentile via the "exclusive" method matches numpy default.
        q = statistics.quantiles(sorted_cp, n=4, method="exclusive")
        p75_cp = q[-1]
    else:
        p75_cp = sorted_cp[0]
    severity = max(median_cp, p75_cp / 2.0)
    return decay_sum * severity


def _passes_eligibility(events: List[int]) -> bool:
    """Combo 6: rec >= 5 AND (median >= 150 OR p75 >= 300)."""
    if len(events) < ELIGIBILITY_MIN_RECURRENCE:
        return False
    sorted_cp = sorted(events)
    median_cp = statistics.median(sorted_cp)
    if len(sorted_cp) >= 2:
        q = statistics.quantiles(sorted_cp, n=4, method="exclusive")
        p75_cp = q[-1]
    else:
        p75_cp = sorted_cp[0]
    return median_cp >= ELIGIBILITY_MIN_MEDIAN_CP or p75_cp >= ELIGIBILITY_MIN_P75_CP


# ─── DB-bound entry point ───────────────────────────────────────────


async def rank_top_concept_for_user(
    db,
    user_id: str,
    *,
    lookback_games: int = DEFAULT_LOOKBACK_GAMES,
    family_filter: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Pull the user's recent analyzed games, compute Formula C per
    concept, return the top eligible concept WITHIN the requested family
    (or globally if family_filter is None) with metadata for the card.

    Returns:
        None when no concept passes eligibility, OR a dict:
        {
            "concept_id": str,
            "family": str,             # "tac" / "op" / ... / "legacy"
            "score": float,
            "recurrence": int,         # count of violation events
            "median_cp": float,
            "p75_cp": float,
            "most_recent_game_id": Optional[str],
            "most_recent_imported_at": Optional[str],
            "earlier_game_ids": List[str],  # up to 5 prior games
        }
    """
    cursor = db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "imported_at": 1},
    ).sort("imported_at", -1).limit(lookback_games)
    recent_games = await cursor.to_list(lookback_games)
    if not recent_games:
        return None

    # games_back: most-recent game = 0
    game_index_by_id = {g["game_id"]: i for i, g in enumerate(recent_games)}

    # Accumulate events per concept_id
    events_by_concept: Dict[str, List[int]] = {}
    games_back_by_concept: Dict[str, List[int]] = {}
    games_seen_by_concept: Dict[str, List[str]] = {}

    for g in recent_games:
        gid = g["game_id"]
        ga = await db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, "decryption_v5_data": 1},
        )
        if not ga:
            continue
        v5 = ga.get("decryption_v5_data") or []
        if not isinstance(v5, list):
            continue
        events = _violation_events_for_game(v5)
        if not events:
            continue
        gb = game_index_by_id[gid]
        # Track unique concepts per game so games_seen is per-game, not per-event
        seen_this_game: Set[str] = set()
        for concept_id, cp in events:
            events_by_concept.setdefault(concept_id, []).append(cp)
            games_back_by_concept.setdefault(concept_id, []).append(gb)
            if concept_id not in seen_this_game:
                games_seen_by_concept.setdefault(concept_id, []).append(gid)
                seen_this_game.add(concept_id)

    # Filter to family if requested
    candidates = []
    for cid, evs in events_by_concept.items():
        fam = family_for_concept(cid)
        if family_filter is not None and fam != family_filter:
            continue
        if not _passes_eligibility(evs):
            continue
        score = _score_formula_c(evs, games_back_by_concept[cid])
        sorted_cp = sorted(evs)
        median_cp = statistics.median(sorted_cp)
        if len(sorted_cp) >= 2:
            q = statistics.quantiles(sorted_cp, n=4, method="exclusive")
            p75_cp = q[-1]
        else:
            p75_cp = sorted_cp[0]
        games_for_concept = games_seen_by_concept.get(cid, [])
        candidates.append({
            "concept_id": cid,
            "family": fam,
            "score": round(score, 2),
            "recurrence": len(evs),
            "median_cp": round(float(median_cp), 1),
            "p75_cp": round(float(p75_cp), 1),
            "most_recent_game_id": games_for_concept[0] if games_for_concept else None,
            "earlier_game_ids": games_for_concept[1:6],  # up to 5 prior
        })

    if not candidates:
        return None

    candidates.sort(key=lambda c: c["score"], reverse=True)
    top = candidates[0]

    # Hydrate the most-recent imported_at for the response.
    if top["most_recent_game_id"]:
        g = next(
            (rg for rg in recent_games if rg["game_id"] == top["most_recent_game_id"]),
            None,
        )
        top["most_recent_imported_at"] = g.get("imported_at") if g else None
    else:
        top["most_recent_imported_at"] = None

    return top


# ─── Family rollup (returns one card per family, cap-respecting) ───


async def rank_top_concept_per_family(
    db,
    user_id: str,
    *,
    lookback_games: int = DEFAULT_LOOKBACK_GAMES,
    max_families: int = 3,
) -> List[Dict[str, Any]]:
    """Top eligible concept per family, sorted by score, capped at
    max_families. This is the "shelf" the UnifiedProgress page renders
    one entry per weakness bucket.
    """
    out: List[Dict[str, Any]] = []
    for fam_prefix in FAMILY_PREFIXES:
        fam = fam_prefix.rstrip("_").lower()
        top = await rank_top_concept_for_user(
            db, user_id, lookback_games=lookback_games, family_filter=fam,
        )
        if top:
            out.append(top)
    # Also include legacy bucket so older v5-plan-namespace concepts surface
    top_legacy = await rank_top_concept_for_user(
        db, user_id, lookback_games=lookback_games, family_filter="legacy",
    )
    if top_legacy:
        out.append(top_legacy)

    out.sort(key=lambda c: c["score"], reverse=True)
    return out[:max_families]
