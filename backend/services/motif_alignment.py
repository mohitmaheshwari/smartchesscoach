"""Which of the two alignment cards tells the truth about a position.

docs/pin_skewer_drill_scope.md.

TWO DIFFERENT JOBS, AND THEY MUST NOT BE DONE BY ONE FUNCTION.

`opportunity_gate.shape_of_best_move` decides WHETHER a position is an alignment
tactic. It is the authority for that, because it is the function that measured
the weakness this drill trains, and the drill has to train what was measured.

This module decides WHICH SENTENCE to print. The pin card says "the one in front
is worth less" and the skewer card says "the bigger one is in front". Those are
claims about the board, and they are printed to the player.

Measured on 900 gate-tagged positions, 2026-10-03: the gate's name matched the
geometry 895 times and disagreed 5 times, and in zero cases was neither sentence
true. One percent is small and it is still a sentence that lies about the board,
so the two jobs are split -- the gate admits the position, the geometry words the
card -- and then the printed sentence is true by construction rather than by a
99% rate.

The same measurement's negative control: the identical test against a random
legal move finds an alignment 15-20% of the time, against 99% for the engine's
move. The check discriminates; it is not passing everything.
"""
from __future__ import annotations

from typing import Optional

import chess

# The king sits above the queen so that a king IN FRONT reads as a skewer and a
# king BEHIND reads as a pin, which is how both are taught. Using the usual 0 or
# infinity for a king would make every king alignment one single case.
VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
         chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 10}

_STRAIGHT = ((1, 0), (-1, 0), (0, 1), (0, -1))
_DIAGONAL = ((1, 1), (1, -1), (-1, 1), (-1, -1))

# Only line pieces can create one of these. A knight, pawn or king can of course
# win material, but not by putting two enemy pieces on a line it controls, so
# neither card would be honest about what it did.
RAYS = {
    chess.ROOK: _STRAIGHT,
    chess.BISHOP: _DIAGONAL,
    chess.QUEEN: _STRAIGHT + _DIAGONAL,
}


def alignment_after(fen: str, uci: str) -> Optional[str]:
    """"pin", "skewer", or None -- which card is true once this move is played.

    Walks every ray from the square the piece landed on. A ray counts when it
    meets an enemy piece and then, continuing through empty squares, meets a
    second enemy piece. The two piece values decide the wording:

        front worth LESS than back   -> pin
        front worth MORE than back   -> skewer
        equal                        -> neither card is honest; None

    Only the piece that MOVED is considered. A line that already existed, or one
    opened by a different piece, is a different claim and these cards do not
    make it.

    `None` is a refusal, not a failure: the caller must not serve the position
    with either card.
    """
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(str(uci))
    except Exception:
        return None
    if move not in board.legal_moves:
        return None
    board.push(move)
    piece = board.piece_at(move.to_square)
    if piece is None:
        return None            # captured off the board, or a promotion elsewhere
    directions = RAYS.get(piece.piece_type)
    if not directions:
        return None
    mine = piece.color
    pairs = []
    file0 = chess.square_file(move.to_square)
    rank0 = chess.square_rank(move.to_square)
    for dfile, drank in directions:
        front = back = None
        file_, rank_ = file0 + dfile, rank0 + drank
        while 0 <= file_ < 8 and 0 <= rank_ < 8:
            at = board.piece_at(chess.square(file_, rank_))
            if at is not None:
                if at.color == mine:
                    break      # our own piece ends the line
                if front is None:
                    front = at
                else:
                    back = at
                    break
            file_, rank_ = file_ + dfile, rank_ + drank
        if front is not None and back is not None:
            pairs.append((VALUE[front.piece_type], VALUE[back.piece_type]))

    # Pin is checked first so that a move creating both reads as the pin, which
    # is the stronger and more teachable of the two.
    if any(front < back for front, back in pairs):
        return "pin"
    if any(front > back for front, back in pairs):
        return "skewer"
    return None
