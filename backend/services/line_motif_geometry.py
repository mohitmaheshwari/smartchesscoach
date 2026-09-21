"""Shared line geometry for the three line motifs.

clearance, xRayAttack and interference are all statements about one ray and
what sits on it:

  clearance     a FRIENDLY piece is on the ray and steps off it, so a friendly
                move that was blocked only by that piece becomes possible.
  xRayAttack    an ENEMY piece is on the ray, and the friendly slider behind it
                later lands on the square beyond it.
  interference  a piece ARRIVES on the ray between an enemy defender and what
                it was defending, and the defence dies.

So the three proofs share exactly two things and nothing else: the ray algebra
(delegated to python-chess so no second geometry source exists in the repo) and
one replay of the stored line that hands every proof the same ply-by-ply board
states. Both live here.

Geometry is `chess.between` / `chess.ray`, never a hand-rolled step walker:
`discovered_attack_puzzle_proof` already carries a private `_ray_step`/`_between`
pair and a third copy would be the "same info in N places" disease.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple

import chess

from services.caption_facts import PIECE_VALUE_CP
from services.stored_line_verifier import (
    replay_stored_line,
    settled_material_gain_cp,
    StoredLineReplay,
)


LINE_MOTIF_GEOMETRY_VERSION = "line_motif_geometry.v1"

#: A stored line that settles below this is not a payoff, it is noise.
MIN_LINE_PAYOFF_CP = PIECE_VALUE_CP[chess.PAWN]

#: `settled_material_gain_cp` scores mate as this, in initiator perspective.
MATERIAL_MATE_SCORE_CP = 100_000

_SLIDERS = (chess.BISHOP, chess.ROOK, chess.QUEEN)


def is_slider(piece_type: Optional[int]) -> bool:
    return piece_type in _SLIDERS


def squares_between(origin: int, target: int) -> Optional[Tuple[int, ...]]:
    """Squares strictly between two aligned squares, or None if not aligned.

    `chess.between` returns an empty set both for adjacent aligned squares and
    for unaligned ones, so alignment is asked separately via `chess.ray`. Both
    hand back a raw bitboard on this python-chess build, hence the SquareSet.
    """
    if origin == target:
        return None
    if not chess.ray(origin, target):
        return None
    return tuple(chess.SquareSet(chess.between(origin, target)))


def slider_travels(piece_type: int, origin: int, target: int) -> bool:
    """Whether this piece type's move pattern can run origin -> target."""
    if not is_slider(piece_type):
        return False
    if origin == target or not chess.ray(origin, target):
        return False
    file_delta = chess.square_file(target) - chess.square_file(origin)
    rank_delta = chess.square_rank(target) - chess.square_rank(origin)
    diagonal = abs(file_delta) == abs(rank_delta)
    straight = file_delta == 0 or rank_delta == 0
    if piece_type == chess.BISHOP:
        return diagonal
    if piece_type == chess.ROOK:
        return straight
    return diagonal or straight


def same_piece(a: Optional[chess.Piece], b: Optional[chess.Piece]) -> bool:
    if a is None or b is None:
        return False
    return a.piece_type == b.piece_type and a.color == b.color


@dataclass(frozen=True)
class LineWalk:
    """Every board state of one stored line, indexed by ply.

    `positions[i]` is the board BEFORE `moves[i]`, so `positions[i].turn` says
    whose move it is. A proof that needs "was this true earlier in the line?"
    reads `positions`; a proof that needs "did we do this later?" reads `moves`.
    """

    initiator: chess.Color
    positions: Tuple[chess.Board, ...]
    moves: Tuple[chess.Move, ...]
    replay: StoredLineReplay
    final: chess.Board

    def __len__(self) -> int:
        return len(self.moves)

    def initiator_plies(self) -> Tuple[int, ...]:
        return tuple(
            index
            for index, board in enumerate(self.positions)
            if board.turn == self.initiator
        )


def walk_line(
    board_before: chess.Board,
    leading_move: chess.Move,
    continuation: Sequence[Any],
) -> Optional[LineWalk]:
    """Replay the stored line once and keep every intermediate position.

    Returns None unless the whole stored line replays legally. A half-replayed
    line cannot prove a motif: the payoff is usually on the plies that failed.
    """
    replay = replay_stored_line(
        board_before,
        leading_move,
        continuation,
        resolve_ambiguous_continuation=True,
    )
    if not replay.complete or not replay.replayed_uci:
        return None
    board = board_before.copy(stack=False)
    positions = []
    moves = []
    for uci in replay.replayed_uci:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return None
        if move not in board.legal_moves:
            return None
        positions.append(board.copy(stack=False))
        moves.append(move)
        board.push(move)
    return LineWalk(
        initiator=board_before.turn,
        positions=tuple(positions),
        moves=tuple(moves),
        replay=replay,
        final=board,
    )


def line_payoff_cp(walk: LineWalk) -> Optional[int]:
    """Settled material for the initiator, or None when the line pays nothing.

    Mate scores `MATERIAL_MATE_SCORE_CP`. The settlement matters: a stored line
    routinely stops mid-exchange, and raw `net_material_gain_cp` then measures
    where the line was cut rather than what the motif won. That exact bug was
    ruled false on the discovered-attack detector on 2026-09-19.
    """
    settled = settled_material_gain_cp(walk.replay)
    if settled is None:
        return None
    if settled < MIN_LINE_PAYOFF_CP:
        return None
    return int(settled)


def blockers_between(
    board: chess.Board, origin: int, target: int
) -> Optional[Tuple[Tuple[int, ...], Tuple[int, ...]]]:
    """(friendly-to-origin blockers, enemy-to-origin blockers) on the ray.

    None when the squares are not aligned. Colour is read relative to the piece
    standing on `origin`, which is what every one of the three motifs asks.
    """
    between = squares_between(origin, target)
    if between is None:
        return None
    mover = board.piece_at(origin)
    if mover is None:
        return None
    friendly = []
    enemy = []
    for square in between:
        piece = board.piece_at(square)
        if piece is None:
            continue
        (friendly if piece.color == mover.color else enemy).append(square)
    return tuple(friendly), tuple(enemy)
