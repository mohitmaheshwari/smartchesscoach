"""Material a move wins BY FORCE, proved off the board with no engine line.

Why this exists
---------------
Fork, pin, skewer and discovered attack all have good geometry detectors in
`shape_detectors`, and all four are missing from the opportunity denominator
in `tactic_opportunity`. The reason is not the geometry: it is that every
payoff prover in this codebase walks the material along the ENGINE'S stored
line. On 120 positions `tactic_tags` had already tagged as missed forks, the
geometric sieve found the right move in 96 and `build_fork_proof` refused all
120, because a stored PV is present on only 30.9% of moves and those had none.

A denominator may not depend on the engine having been generous. So the payoff
here is proved the only other way it can be: exhaustively.

    ply 1   the candidate move
    ply 2   EVERY legal answer the opponent has
    ply 3   my best follow-up capture, scored by static exchange

The opponent picks the answer that leaves me with least, so the number this
returns is a FLOOR on the material the move wins -- not a hope, and not an
average. That is what makes it a proof rather than a guess: ply 2 is
exhaustive, so there is no reply left unexamined.

What it is not
--------------
It proves MATERIAL, within three plies. It cannot see a positional payoff, a
mate in four, or material won on ply five. So it under-claims, which is the
right direction for a detector that has to earn a grade: a move it refuses
may still be a fine move, but a move it proves really does win that material
against every defence.

The caller keeps the geometry and the payoff apart on purpose
([[feedback_separate_structure_from_its_effect]]): `shape_detectors` says what
shape is on the board, this says what the shape is worth.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import chess

from services.caption_facts import PIECE_VALUE_CP, static_exchange_eval

TACTIC_PAYOFF_VERSION = "tactic_payoff.v1"

# A mate is not a material score. It is kept far outside the material range so
# a caller can test for it, and so `min()` over replies treats being mated as
# the worst thing that can happen -- which it is.
MATE_GAIN = 1_000_000

# What counts as a payoff worth calling a tactic. A knight is the value the
# rest of this codebase already uses for "material won"
# (caption_facts.TARGET_LINE_MIN_PAYOFF_CP), so the default matches it rather
# than inventing a second convention.
MIN_TACTIC_GAIN_CP = PIECE_VALUE_CP[chess.KNIGHT]

_MATERIAL_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK,
                   chess.QUEEN)


def material_balance(board: chess.Board, me: chess.Color) -> int:
    """My material minus theirs, in centipawns. The king is not material."""
    total = 0
    for piece_type in _MATERIAL_TYPES:
        value = PIECE_VALUE_CP[piece_type]
        total += value * len(board.pieces(piece_type, me))
        total -= value * len(board.pieces(piece_type, not me))
    return total


def best_followup_capture(board: chess.Board, me: chess.Color) -> int:
    """Most material I can add right now with one capture, or 0.

    Scored by static exchange on the target square, so a capture that merely
    invites a recapture is worth what it is actually worth. Never negative:
    declining to capture is always available.
    """
    if board.turn != me:
        return 0
    best = 0
    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
        gain = static_exchange_eval(board, move.to_square, me)
        if gain > best:
            best = gain
    return best


def forced_material_gain(
    board: chess.Board,
    move: chess.Move,
    *,
    give_up_below: Optional[int] = None,
) -> Optional[int]:
    """Centipawns `move` wins against the opponent's BEST defence. Or None.

    None means the move could not be judged at all (not legal here). A
    negative number means the move loses material by force. `give_up_below`
    lets a caller stop as soon as the floor is known to be too low to matter,
    which is what makes an exhaustive ply 2 affordable.
    """
    me = board.turn
    if move not in board.legal_moves:
        return None
    base = material_balance(board, me)

    after_move = board.copy(stack=False)
    after_move.push(move)

    if after_move.is_checkmate():
        return MATE_GAIN
    # Opponent has no move and is not in check: I have stalemated myself out
    # of whatever I was winning. Material is all that is left.
    if not any(after_move.legal_moves):
        return material_balance(after_move, me) - base

    worst: Optional[int] = None
    for reply in after_move.legal_moves:
        after_reply = after_move.copy(stack=False)
        after_reply.push(reply)

        if after_reply.is_checkmate():
            # Their answer mates ME. Whatever the geometry promised, this move
            # is refuted, and nothing below needs checking.
            return -MATE_GAIN

        gain = material_balance(after_reply, me) - base
        if any(after_reply.legal_moves):
            gain += best_followup_capture(after_reply, me)

        if worst is None or gain < worst:
            worst = gain
            if give_up_below is not None and worst < give_up_below:
                return worst
    return worst


def proved_payoff_moves(
    board: chess.Board,
    candidates: List[chess.Move],
    *,
    min_gain: int = MIN_TACTIC_GAIN_CP,
) -> Dict[chess.Move, int]:
    """Of these candidate moves, the ones that force `min_gain` -- and by how much.

    The caller supplies the candidates from a geometry detector; this says
    which of them are worth anything. Order is preserved for determinism.
    """
    proved: Dict[chess.Move, int] = {}
    for move in candidates:
        gain = forced_material_gain(board, move, give_up_below=min_gain)
        if gain is not None and gain >= min_gain:
            proved[move] = gain
    return proved


__all__ = [
    "TACTIC_PAYOFF_VERSION",
    "MATE_GAIN",
    "MIN_TACTIC_GAIN_CP",
    "material_balance",
    "best_followup_capture",
    "forced_material_gain",
    "proved_payoff_moves",
]
