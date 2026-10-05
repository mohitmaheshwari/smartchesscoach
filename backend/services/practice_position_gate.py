"""Does the answer a practice position accepts actually work?

Mohit, 2026-10-05, on a drill headed "Let's Practise Piece Safety":

    "we are not talking about the knight on e7, it is attacked twice and it is
     gone now, so how come we are keeping piece safety"

On `r1bk1r2/ppp1n2N/3p4/6B1/8/1B1P4/PPP3PP/4R1K1 b - - 0 20` the card's text is
true in every word -- Bxf7 is real, f7 is undefended, Rf5 is safe. It is still
the wrong card. The knight on e7 is attacked by Re1 and Bg5 and defended only
by the king, so it is lost before the student touches anything. Rf7, the move
we call the mistake, is the one that DEFENDS it; Rf5, the move we call safer,
abandons it. A student who applies our method exactly ends a piece down, which
does not teach the habit -- it discredits it.

THE RULE IS NOT "the student must end up safe". That would throw away every
damage-control drill, where playing the least-bad move IS the lesson. The
complaint is narrower: we taught the smaller loss and left a bigger one
untouched. So:

    Reject when, after the answer we accept, the opponent wins material on a
    square where they could ALREADY have won it before the student moved.

"Already" is what separates a pre-existing problem the drill ignores from a
consequence of the move being drilled. Measured over all 91,009 admitted
positions: keeps 72.6%, rejects 27.4%. The e7 card is rejected; back-rank mate
stays at 100% kept. See docs/practice_position_safety_gate_scope.md.

Board arithmetic only -- no engine call, no stored verdict taken on trust.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import chess

from services.caption_facts import static_exchange_eval

#: Below a pawn is noise, not a lesson the student can be held to.
MATERIAL_FLOOR_CP = 100


@dataclass(frozen=True)
class GateVerdict:
    """Why a position was kept or rejected, in terms a human can check."""

    keep: bool
    reason: str
    #: Square (e.g. "e7") carrying the untouched loss, when rejected.
    square: Optional[str] = None
    #: Centipawns the opponent wins there.
    gain_cp: int = 0

    def as_dict(self) -> Dict[str, object]:
        return {"keep": self.keep, "reason": self.reason,
                "square": self.square, "gain_cp": self.gain_cp}


def _winnable(board: chess.Board, mover: chess.Color) -> Dict[int, int]:
    """{square: centipawns} the given side wins by force on that square now.

    The side to move is forced to `mover` so the same question can be asked
    before and after the student's move. Only captures are considered: this
    answers "what material is hanging", not "what is the best move".
    """
    out: Dict[int, int] = {}
    probe = board.copy(stack=False)
    probe.turn = mover
    for move in probe.legal_moves:
        if not probe.is_capture(move):
            continue
        gain = static_exchange_eval(probe, move.to_square, mover) or 0
        if gain >= MATERIAL_FLOOR_CP:
            out[move.to_square] = max(out.get(move.to_square, 0), gain)
    return out


def evaluate_position(fen: str, accepted_move_uci: str) -> GateVerdict:
    """Decide whether this position is worth putting in front of a student."""
    try:
        board = chess.Board(fen)
    except ValueError:
        return GateVerdict(False, "unreadable fen")

    try:
        move = chess.Move.from_uci(str(accepted_move_uci or ""))
    except ValueError:
        return GateVerdict(False, "unreadable answer")

    if move not in board.legal_moves:
        # Not a judgement about the lesson -- the drill cannot be played at all.
        return GateVerdict(False, "accepted answer is not legal here")

    opponent = not board.turn
    before = _winnable(board, opponent)

    after_board = board.copy(stack=False)
    after_board.push(move)
    after = _winnable(after_board, opponent)

    # A loss that was already available and is no smaller once the answer is
    # played. The answer did not address it, so the drill is teaching past it.
    stale = {sq: cp for sq, cp in after.items()
             if sq in before and cp >= before[sq]}
    if stale:
        square = max(stale, key=lambda s: stale[s])
        return GateVerdict(
            False,
            "the answer leaves a loss that was already on the board",
            chess.square_name(square),
            stale[square],
        )

    return GateVerdict(True, "the answer resolves what this position is about")


def keeps(fen: str, accepted_move_uci: str) -> bool:
    """Convenience predicate for callers that only need the decision."""
    return evaluate_position(fen, accepted_move_uci).keep
