"""The move that walked into mate — proven on the board, or not claimed.

`tactical_oversight` was measured on 2026-09-18 to be a mislabelled mate
bucket: 81% of its `generic_oversight` fires are mate swings, which is also
why that bucket averages 7,524cp. The signed-off precedence
(docs/move_classification_from_gold_scope.md §1, amendment 2) routes them to
`king_safety`, and this is the detector that earns the right to say so.

**An evaluation sentinel is not a proof.** Of 3,727 moves whose stored
evaluation was a mate score against the player:

    66.5%  were already lost before the move -- they were in the net already,
           so "you allowed mate" is simply false
    24.3%  the stored line is too short to reach mate (PVs run 4-6 moves)
     9.2%  mate proven by replaying the stored line on a board

So this claims only the last group. It replays `pv_after_played` and requires
an actual `board.is_checkmate()`. The 343 proven cases in that sample ran to a
median of 1 ply and a maximum of 3, which makes the resulting claim about as
checkable as a chess statement gets.

The 24.3% are not denied, they are left UNKNOWN. Extending them needs a fresh
engine search per position; at roughly 5,600 positions corpus-wide and ~1.1s
each that is under two hours of one-off compute, and it is the obvious recall
upgrade. Until it runs, this detector is precise and partial by construction,
which is the caption-grade trade rather than the plan-grade one.

Evidence, not a confidence score: every fire carries the position, the move,
the mating line and the ply count, so the sentence can be rendered from stored
facts and re-checked by anyone.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

import chess

FACT_VERSION = "king_safety.allowed_mate_exact.v1"
QUALITY_ID = "gap:king_safety:allowed_mate_exact"

# A stored evaluation at or beyond this magnitude is the engine reporting mate
# rather than a material assessment.
MATE_SENTINEL_CP = 3000

# Long "mates" are not a coaching claim -- nobody learns from being told they
# allowed mate in fourteen. Every proven case measured came in at 3 plies or
# fewer, so this is a ceiling rather than a filter that does any work today.
MAX_PLIES_TO_MATE = 7


def _user_pov(value: Optional[float], user_color: str) -> Optional[float]:
    if value is None:
        return None
    return float(value) if user_color == "white" else -float(value)


def _plies_to_mate(fen_after: str, line: Sequence[str]) -> Optional[int]:
    """Replay the stored continuation; return plies to mate, or None.

    None means "not proven here", never "no mate". A truncated line is the
    commonest reason and it is not evidence of safety.
    """
    if not fen_after or not line:
        return None
    try:
        board = chess.Board(fen_after)
    except Exception:
        return None
    for index, san in enumerate(line):
        try:
            board.push(board.parse_san(str(san)))
        except Exception:
            return None
        if board.is_checkmate():
            return index + 1
    return None


def detect_allowed_mate(
    move: Mapping[str, Any], user_color: str
) -> Optional[Dict[str, Any]]:
    """Return an evidence record when the move provably walked into mate.

    None means not proven, which covers both "no mate" and "cannot tell from
    what is stored". Those are different, and `reason` says which.
    """
    eval_before = _user_pov(move.get("eval_before"), user_color)
    eval_after = _user_pov(move.get("eval_after"), user_color)

    if eval_after is None or eval_after > -MATE_SENTINEL_CP:
        return None

    # Already lost before they moved. Two thirds of candidates land here, and
    # telling those players they "allowed mate" is the false claim this
    # detector exists to stop.
    if eval_before is not None and eval_before <= -MATE_SENTINEL_CP:
        return None

    line = list(move.get("pv_after_played") or [])
    plies = _plies_to_mate(str(move.get("fen_after") or ""), line)
    if plies is None or plies > MAX_PLIES_TO_MATE:
        return None

    return {
        "fact_version": FACT_VERSION,
        "quality_id": QUALITY_ID,
        "fen_before": move.get("fen_before"),
        "fen_after": move.get("fen_after"),
        "played_san": move.get("move"),
        "played_uci": move.get("move_uci"),
        "move_number": move.get("move_number"),
        # The proof, kept whole so the claim can be re-checked by anyone.
        "mating_line": line[:plies],
        "plies_to_mate": plies,
        "moves_to_mate": (plies + 1) // 2,
        "eval_before": move.get("eval_before"),
        "verified": "replayed_to_checkmate",
    }


def render_claim(evidence: Mapping[str, Any]) -> str:
    """The sentence, built only from what the evidence record proves."""
    moves = evidence.get("moves_to_mate") or 0
    played = evidence.get("played_san") or "that move"
    line = " ".join(str(x) for x in (evidence.get("mating_line") or []))
    if moves <= 1:
        head = f"{played} allows mate in one."
    else:
        head = f"{played} allows mate in {moves}."
    return f"{head} The finish is {line}." if line else head
