"""Coach review of real-game lesson evidence: which events are worth a look.

docs/phase1_lesson_evidence_review_scope.md, WS1. The shadow ledger
(services/learning_evidence_ledger.py) records every time a player kept or lost
a piece in a real game after the piece-safety lesson, and marks every event
`evidence_eligible: False`. That invariant stays: nothing here touches
`learning_sessions`. A coach's ruling is a separate record that references an
event by its `idempotency_key`.

Most "kept" events show nothing. On 2026-11-05 the median kept event had a Maia
temptation of 0.007: there was no hanging move anyone would play, so keeping the
piece safe proved nothing. The four rules below (locked in the scope, §9.5) keep
only the events where resisting was a real choice:

  1. stored outcome "applied", and the played move still grades "pass" under
     grade_destination_safety_candidate -- 18% of stored outcomes disagree with
     today's detector, so the label is re-checked, never trusted
  2. temptation >= TEMPTATION_FLOOR: Maia's probability, at the player's rating,
     summed over the legal moves that would hang a piece
  3. the move itself was not a mistake or a blunder
  4. the game has a stored rating, because Maia needs one

Rule 2 needs Maia, which never runs on the server (the box has no memory for
it). So rows are built offline by scripts/seed_lesson_evidence_reviews.py and
this module only holds the pure parts: the rules, the row, and the order a
coach sees them in.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import chess

from services.destination_safety_detector import (
    QUALITY_ID as DESTINATION_SAFETY_QUALITY_ID,
    grade_destination_safety_candidate,
)

REVIEWS = "lesson_evidence_reviews"
RULINGS = "lesson_evidence_rulings"
ROW_VERSION = "lesson_evidence_review.v1"

# Locked 2026-11-05 against 1,475 real hangs: 55% of them happened in a position
# at least this tempting. See the scope, §9.5, for the rejected cutoffs.
TEMPTATION_FLOOR = 0.05
# Inherited from the analyser's own move classification, not a new number.
NOT_A_DEMONSTRATION = frozenset({"mistake", "blunder"})
VERDICTS = frozenset({"yes", "no", "unsure"})
# How many tempting moves the card names.
SHOWN_TEMPTATIONS = 3


def pair_key(user_id: str, skill_id: str) -> str:
    return f"{user_id}|{skill_id}"


def hanging_moves(fen: str) -> List[str]:
    """Every legal move, as uci, that puts a piece where it is lost for free."""
    board = chess.Board(fen)
    return sorted(
        move.uci()
        for move in board.legal_moves
        if grade_destination_safety_candidate(fen, move.uci()).get("status") == "fail"
    )


def candidate_rejection(
    event: Mapping[str, Any],
    observation: Optional[Mapping[str, Any]],
    user_rating: Optional[int],
) -> Optional[str]:
    """Why this event is not a candidate, or None when rules 1, 3 and 4 hold.

    Rule 2 needs Maia and is applied later, by `review_row`.
    """
    result = event.get("lesson_result") or {}
    application = result.get("application") or {}
    if event.get("event_type") != "lesson_result":
        return "not_a_lesson_result"
    if application.get("source_type") != "organic_game":
        return "not_a_real_game"
    if application.get("detector_quality_id") != DESTINATION_SAFETY_QUALITY_ID:
        return "other_concept"
    if application.get("outcome") != "applied":
        return "not_kept"
    if not observation or not observation.get("fen_before") or not observation.get("move_uci"):
        return "no_stored_position"
    if str(observation.get("execution_quality") or "") in NOT_A_DEMONSTRATION:
        return "move_was_a_mistake"
    if not user_rating:
        return "no_rating"
    grade = grade_destination_safety_candidate(observation["fen_before"], observation["move_uci"])
    if grade.get("status") != "pass":
        return "outcome_disagrees_with_detector"
    return None


def review_row(
    event: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    user_id: str,
    user_rating: int,
    opponent_rating: Optional[int],
    probabilities: Mapping[str, float],
    record: Mapping[str, int],
    first_lesson_at: Optional[str],
) -> Optional[Dict[str, Any]]:
    """The row a coach reviews, or None when nothing tempting was resisted."""
    fen = observation["fen_before"]
    board = chess.Board(fen)
    hanging = hanging_moves(fen)
    temptation = round(sum(float(probabilities.get(uci, 0.0)) for uci in hanging), 4)
    if temptation < TEMPTATION_FLOOR:
        return None
    ranked = sorted(hanging, key=lambda uci: (-float(probabilities.get(uci, 0.0)), uci))
    tempting = []
    for uci in ranked[:SHOWN_TEMPTATIONS]:
        move = chess.Move.from_uci(uci)
        grade = grade_destination_safety_candidate(fen, uci)
        tempting.append({
            "uci": uci,
            "san": board.san(move),
            "probability": round(float(probabilities.get(uci, 0.0)), 4),
            "piece": grade.get("moved_piece"),
            "loses_cp": grade.get("net_material_loss_cp"),
        })
    played = chess.Move.from_uci(observation["move_uci"])
    skill_id = str(event.get("skill_id") or "")
    occurred_at = str(event.get("occurred_at") or "")
    return {
        "key": str(event["idempotency_key"]),
        "row_version": ROW_VERSION,
        "pair": pair_key(user_id, skill_id),
        "user_id": user_id,
        "skill_id": skill_id,
        "detector_quality_id": DESTINATION_SAFETY_QUALITY_ID,
        "game_id": observation.get("game_id"),
        "ply": observation.get("ply"),
        "move_number": observation.get("move_number"),
        "fen": fen,
        "side_to_move": "white" if board.turn == chess.WHITE else "black",
        "played_san": board.san(played),
        "played_uci": played.uci(),
        "moved_piece": chess.piece_name(board.piece_at(played.from_square).piece_type),
        "cp_loss": observation.get("cp_loss"),
        "execution_quality": observation.get("execution_quality"),
        "temptation": temptation,
        "tempting_moves": tempting,
        "hanging_move_count": len(hanging),
        "user_rating": int(user_rating),
        "opponent_rating": int(opponent_rating) if opponent_rating else None,
        "occurred_at": occurred_at,
        "first_lesson_at": first_lesson_at,
        "after_first_lesson": bool(first_lesson_at and occurred_at[:10] >= str(first_lesson_at)[:10]),
        "record": {"kept": int(record.get("kept", 0)), "lost": int(record.get("lost", 0))},
    }


def _stable(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def order_queue(
    rows: Iterable[Mapping[str, Any]],
    rulings: Iterable[Mapping[str, Any]],
) -> List[Mapping[str, Any]]:
    """Unruled rows, one player-concept pair at a time.

    The largest pair holds over a thousand events, so corpus order would show a
    coach the same player indefinitely (scope §7.4). Pairs without a "yes"
    come first, because one approval is what mastery needs; then pairs with the
    fewest rulings; ties break on a hash of the pair, never on how much a player
    has played. Within a pair the most tempting position comes first: it is the
    strongest demonstration on offer. Nothing orders by the outcome -- every row
    here is a kept piece.
    """
    rulings = list(rulings)
    ruled = {str(r.get("key")) for r in rulings}
    count: Dict[str, int] = {}
    has_yes: Dict[str, bool] = {}
    for r in rulings:
        pair = str(r.get("pair") or "")
        count[pair] = count.get(pair, 0) + 1
        if r.get("verdict") == "yes":
            has_yes[pair] = True
    waiting = [r for r in rows if str(r.get("key")) not in ruled]
    best: Dict[str, Mapping[str, Any]] = {}
    for r in sorted(waiting, key=lambda r: (-float(r.get("temptation") or 0), str(r.get("key")))):
        best.setdefault(str(r.get("pair")), r)
    pairs = sorted(
        best,
        key=lambda p: (bool(has_yes.get(p)), count.get(p, 0), _stable(p)),
    )
    return [best[p] for p in pairs]


def summarise(
    rows: Sequence[Mapping[str, Any]],
    rulings: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    by_verdict: Dict[str, int] = {}
    approved_pairs = set()
    for r in rulings:
        v = str(r.get("verdict") or "unsure")
        by_verdict[v] = by_verdict.get(v, 0) + 1
        if v == "yes":
            approved_pairs.add(str(r.get("pair")))
    ruled = {str(r.get("key")) for r in rulings}
    return {
        "total": len(rulings),
        "in_set": len(rows),
        "pairs": len({str(r.get("pair")) for r in rows}),
        "pairs_waiting": len({str(r.get("pair")) for r in rows if str(r.get("key")) not in ruled}),
        "pairs_approved": len(approved_pairs),
        "by_verdict": by_verdict,
        # Every "no" is a bug report: a position we called a demonstration
        # that a person says shows nothing.
        "ruled_no": [
            {"key": r.get("key"), "fen": r.get("fen"), "played_san": r.get("played_san"),
             "note": r.get("note"), "reviewer_name": r.get("reviewer_name")}
            for r in rulings if r.get("verdict") == "no"
        ],
    }


def lesson_family(skill_id: str) -> str:
    """The first two words of a skill id: `piece_safety_simple_hang` -> `piece_safety`.

    Display context only, for "first lesson on this" on the card. The lesson
    sessions and the real-game evidence name the same idea differently, which
    is the vocabulary problem WS0 exists to fix; nothing decides on this.
    """
    return "_".join(str(skill_id or "").split("_")[:2])


def first_lesson_dates(sessions: Iterable[Mapping[str, Any]]) -> Dict[Tuple[str, str], str]:
    """(user_id, family) -> earliest completed lesson, from real lesson sessions."""
    out: Dict[Tuple[str, str], str] = {}
    for s in sessions:
        if s.get("lesson_type") != "personalized_curriculum" or not s.get("completed_at"):
            continue
        key = (str(s.get("user_id")), lesson_family(str(s.get("skill_id") or "")))
        at = str(s.get("completed_at"))
        if key not in out or at < out[key]:
            out[key] = at
    return out


__all__ = [
    "NOT_A_DEMONSTRATION",
    "REVIEWS",
    "RULINGS",
    "ROW_VERSION",
    "TEMPTATION_FLOOR",
    "VERDICTS",
    "candidate_rejection",
    "first_lesson_dates",
    "hanging_moves",
    "lesson_family",
    "order_queue",
    "pair_key",
    "review_row",
    "summarise",
]
