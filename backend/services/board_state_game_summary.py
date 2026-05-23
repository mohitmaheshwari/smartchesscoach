"""Game-wide board-state trends (P5 — Mohit 2026-05-23).

The per-move board_state_describer surfaces 1-3 geometric facts about
the CURRENT position when no concrete detector fires. That's
narrow-focus coaching — useful at the move, but invisible across the
game.

This module runs the same metrics across every user position in a
finished game and aggregates the results into trend-level insights
the player CANNOT see by looking at any single position:

  - "Opponent had pieces aimed at your king for 8 of 25 user moves"
  - "Your pieces stayed on your side of the board across 12 positions"
  - "You were behind in development through the entire opening"

These are TRENDS, not snapshots. They earn their own UI section in
Review because each one summarizes structural game flow that
per-move captions necessarily fragment.

Pure function: takes decryption_v5_data + user_color, returns a
dict. No DB, no LLM, no Stockfish. Trivial CPU (11 metrics ×
~25 user positions = ms).

Output shape:
  {
    "user_move_count": int,            # total user moves analyzed
    "trends": [                         # ranked by impact_score desc
      {
        "fact_id": "bs_passive_pieces_count",
        "category": "activity",
        "occurrence_count": 12,         # how many user moves this fact fired in
        "move_numbers": [5, 6, 7, ...], # the full-move numbers it fired at
        "total_severity": 120,          # sum of severity across firings
        "label": "Your pieces stayed on your side of the board across 12 moves.",
      },
      ...
    ],
  }

Threshold: a trend must fire in >= MIN_OCCURRENCES user moves to
surface. Set high enough that we don't pad the UI with noise
(1-2 occurrences is per-move territory, not a trend).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from services.board_state_describer import describe_board_state


# A fact must fire in at least this many distinct user moves to count
# as a "game-wide trend." Single occurrences are per-move material,
# already surfaced by the existing R12 fallback path.
MIN_OCCURRENCES = 3


# Trend label templates, keyed by fact_id. {N} is the occurrence count.
# Phrased for the 1200-rated audience (no jargon per
# [[caption-voice-avoid-chess-jargon]]). Mohit will tune voice — these
# are the v1 starter phrasings.
_TREND_LABELS: Dict[str, str] = {
    "bs_isolated_attacker":
        "You pushed a piece alone into opponent territory in {N} positions.",
    "bs_worst_placed_piece":
        "You had a piece with almost nowhere to go in {N} positions.",
    "bs_development_gap":
        "You were behind in development for {N} opening moves.",
    "bs_pieces_on_back_rank":
        "Your minor pieces stayed on the back rank across {N} opening moves.",
    "bs_king_shield_broken":
        "Your king sat without its pawn shelter for {N} moves.",
    "bs_king_attackers":
        "Opponent had pieces aimed at your king across {N} moves.",
    "bs_central_control_gap":
        "Opponent dominated the center across {N} positions.",
    "bs_open_file_owned_by_opp":
        "Opponent owned an open file across {N} positions.",
    "bs_queen_alone_active":
        "Only your queen was doing anything in {N} positions.",
    "bs_connected_rooks_only_opp":
        "Opponent had connected rooks while yours weren't in {N} positions.",
    "bs_passive_pieces_count":
        "Your pieces stayed on your side of the board across {N} moves.",
}


def _label_for(fact_id: str, occurrences: int) -> Optional[str]:
    template = _TREND_LABELS.get(fact_id)
    if not template:
        return None
    return template.format(N=occurrences)


def compute_game_summary(
    decryption_v5_data: List[Dict],
    user_color: str,
) -> Dict:
    """Aggregate per-move board-state facts into game-level trends.

    Args:
      decryption_v5_data: list of move dicts (the V5 output). Must
        carry `fen_after`, `is_user_move`, and `move_number`.
      user_color: "white" or "black".

    Returns:
      Dict with keys `user_move_count` (int) and `trends` (list).
      Trends are sorted by total_severity desc, then occurrence_count
      desc. Returns empty trends list when no fact fires
      ≥ MIN_OCCURRENCES times.
    """
    if not decryption_v5_data:
        return {"user_move_count": 0, "trends": []}

    # Per fact_id: aggregate occurrences across user moves.
    per_fact: Dict[str, Dict] = {}
    user_move_count = 0

    for move in decryption_v5_data:
        if not move.get("is_user_move"):
            continue
        fen_after = move.get("fen_after") or ""
        move_number = move.get("move_number") or 0
        if not fen_after or not move_number:
            continue
        user_move_count += 1
        try:
            facts = describe_board_state(
                fen_after=fen_after,
                user_color=user_color,
                move_number=move_number,
            )
        except Exception:
            facts = []
        # De-dup per move: each fact_id counts at most once per move.
        seen_this_move = set()
        for fact in facts:
            if fact.fact_id in seen_this_move:
                continue
            seen_this_move.add(fact.fact_id)
            entry = per_fact.setdefault(fact.fact_id, {
                "fact_id": fact.fact_id,
                "category": fact.category,
                "move_numbers": [],
                "total_severity": 0,
            })
            entry["move_numbers"].append(move_number)
            entry["total_severity"] += fact.severity

    # Filter by threshold + build trend records.
    trends: List[Dict] = []
    for fact_id, entry in per_fact.items():
        occurrence_count = len(entry["move_numbers"])
        if occurrence_count < MIN_OCCURRENCES:
            continue
        label = _label_for(fact_id, occurrence_count)
        if not label:
            continue
        trends.append({
            "fact_id": fact_id,
            "category": entry["category"],
            "occurrence_count": occurrence_count,
            "move_numbers": entry["move_numbers"],
            "total_severity": entry["total_severity"],
            "label": label,
        })

    # Rank by total_severity (the metric weighting already encodes
    # how impactful each one is); break ties on occurrence_count.
    trends.sort(key=lambda t: (t["total_severity"], t["occurrence_count"]), reverse=True)

    return {
        "user_move_count": user_move_count,
        "trends": trends,
    }
