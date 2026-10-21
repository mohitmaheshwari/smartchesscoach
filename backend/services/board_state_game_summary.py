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

import collections
from typing import Any, Dict, List, Optional

from services.board_state_describer import describe_board_state


# A fact must fire in at least this many distinct user moves to count
# as a "game-wide trend." Single occurrences are per-move material,
# already surfaced by the existing R12 fallback path.
MIN_OCCURRENCES = 3


# Trend label templates, keyed by fact_id. {N} is the occurrence count.
# Phrased for the 1200-rated audience (no jargon per
# [[caption-voice-avoid-chess-jargon]]). Mohit will tune voice — these
# are the v1 starter phrasings.
# Player-facing text, so it follows Mohit's standing rules rather than the
# shape of the data: short, one idea, common words, undramatic -- and NO
# counts. The previous versions all ended "across {N} moves", which is a
# number in something a player reads, and "compute ruthlessly, speak
# qualitatively" is his rule, not a preference. The counts are still in the
# record for ranking; they just stop being said out loud.
#
# {PIECE} and {SQUARE} are filled from the trend's recurring subject when it
# has one, so "a piece with almost nowhere to go" becomes "your rook on f1".
# Mohit, 2026-10-21: "the story connects tags not the peices". A label using
# them MUST have a fallback for when no single subject recurs.
_TREND_LABELS: Dict[str, str] = {
    "bs_isolated_attacker":
        "You sent a piece forward on its own.",
    "bs_worst_placed_piece":
        "Your {PIECE} on {SQUARE} had almost nowhere to go.",
    "bs_development_gap":
        "You were slower than your opponent getting pieces out.",
    "bs_pieces_on_back_rank":
        "Your knights and bishops stayed at home early on.",
    "bs_king_shield_broken":
        "Your king sat without its pawn cover.",
    "bs_king_attackers":
        "Your opponent kept pieces aimed at your king.",
    "bs_central_control_gap":
        "Your opponent held the middle of the board.",
    "bs_open_file_owned_by_opp":
        "Your opponent owned an open file and you did not.",
    "bs_queen_alone_active":
        "Your queen was doing the work on her own.",
    "bs_connected_rooks_only_opp":
        "Their rooks worked together and yours did not.",
    "bs_passive_pieces_count":
        "Your pieces stayed on your own side of the board.",
}

# Used when a label wants a subject and the trend has none.
_SUBJECT_FALLBACK = {"PIECE": "piece", "SQUARE": "its square"}


def _subject_of(placeholders: Dict[str, Any]) -> Optional[tuple]:
    """The piece and square a fact is about, when it names one.

    Only some metrics have a single subject -- "opponent dominated the centre"
    is about the board, not a piece. Those return None rather than a guess.
    """
    piece = placeholders.get("bs_piece")
    square = placeholders.get("bs_square")
    if piece and square:
        return (str(piece), str(square))
    return None


def _label_for(
    fact_id: str,
    occurrences: int,
    subject: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    template = _TREND_LABELS.get(fact_id)
    if not template:
        return None
    values = dict(_SUBJECT_FALLBACK)
    values["N"] = occurrences
    if subject:
        if subject.get("piece"):
            values["PIECE"] = str(subject["piece"])
        if subject.get("square"):
            values["SQUARE"] = str(subject["square"])
    try:
        return template.format(**values)
    except (KeyError, IndexError):
        # A template naming a placeholder nobody supplies would otherwise
        # raise here and silently cost the whole trend. Returning None drops
        # one label rather than the game's story.
        return None


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
                "subjects": collections.Counter(),
            })
            entry["move_numbers"].append(move_number)
            entry["total_severity"] += fact.severity
            # Keep WHICH piece on WHICH square, not just how often something
            # happened. Mohit, 2026-10-21: "the story connects tags not the
            # peices". `bs_worst_placed_piece` already carries bs_piece
            # "bishop" and bs_square "c1"; this aggregation read fact_id and
            # severity and dropped `placeholders` entirely, so a trend that
            # knew "your bishop on c1 had one move" could only say "a piece".
            #
            # Counted rather than kept as a list, because the useful subject
            # is the one that recurs: if the c1 bishop was the worst piece in
            # seven of ten positions, that is the bishop worth naming.
            subject = _subject_of(fact.placeholders)
            if subject:
                entry["subjects"][subject] += 1

    # Filter by threshold + build trend records.
    trends: List[Dict] = []
    for fact_id, entry in per_fact.items():
        occurrence_count = len(entry["move_numbers"])
        if occurrence_count < MIN_OCCURRENCES:
            continue
        subject, subject_count = None, 0
        if entry["subjects"]:
            subject, subject_count = entry["subjects"].most_common(1)[0]
        subject_payload = (
            {"piece": subject[0], "square": subject[1],
             "positions": subject_count} if subject else None
        )
        label = _label_for(fact_id, occurrence_count, subject_payload)
        if not label:
            continue
        trends.append({
            "fact_id": fact_id,
            "category": entry["category"],
            "occurrence_count": occurrence_count,
            "move_numbers": entry["move_numbers"],
            "total_severity": entry["total_severity"],
            "label": label,
            # The recurring subject, kept as structured data too so a caller
            # can compose its own wording instead of parsing the label.
            "subject": subject_payload,
        })

    # Rank by total_severity (the metric weighting already encodes
    # how impactful each one is); break ties on occurrence_count.
    trends.sort(key=lambda t: (t["total_severity"], t["occurrence_count"]), reverse=True)

    return {
        "user_move_count": user_move_count,
        "trends": trends,
    }
