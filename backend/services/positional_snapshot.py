"""Positional state of a position, as numbers, for ONE side.

Why this exists
---------------
Mohit, 2026-09-22, on being shown a "positional ability" score assembled from
detector fires: *"why would you ever want to know that you didn't put the
knight on the rim?"*

He is right, and it killed the earlier design. Detector events answer "did
you spot this", so a score built from them ends up crediting a player for NOT
blundering. Positional play is not a list of opportunities taken. It is the
CONDITION of the position, on every move, whether or not anything was spotted.

The second finding is why this file is persistence and not chess. Every fact
below is already computed somewhere in this repo -- `pawn_structure_service`
has doubled, isolated and backward; `caption_facts` has bishop quality and
trade quality; `board_state_describer` has worst-piece. All of it is derived
to write a caption and discarded milliseconds later. Across 528,786 stored
move records, not one carries a single positional fact.

That is the entire reason `positional_sense` reads exactly 60.0 for every
player in production: not weak detectors, not missing chess, just nothing
written down. So this module computes cheap, board-only state that can be
stored on every move and summed over a player's games.

Scope, from Mohit's seven principles (docs/player_understanding_scope.md 4b):

    1 improve your worst piece  -> worst_piece_mobility, total_mobility
    2 control the centre        -> center_control
    3 pawn structure            -> doubled / isolated / backward / islands
    4 good knight vs bad bishop -> bad_bishop_pawns
    5 space advantage           -> space
    7 trading the right pieces  -> handled at capture time, not here

Principle 6, prophylaxis, is deliberately NOT here. It needs the opponent's
INTENTION, and intention is not in the position. It gets its own
investigation rather than a guess.

LOAD-BEARING: everything here reads the board and nothing else. No engine, no
database, no LLM, no detector. It must stay cheap enough to run on every move
of every game, because that is the whole point.
"""
from __future__ import annotations

from typing import Any, Dict, List

import chess

#: The four squares every book means by "the centre".
CENTER_SQUARES = (chess.D4, chess.E4, chess.D5, chess.E5)

#: A piece with this many legal moves or fewer is doing nothing. Deliberately
#: not tuned yet -- it is reported as a raw count so a threshold can be read
#: off the distribution later rather than guessed now.
_PIECE_TYPES = (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)


def _pawn_files(board: chess.Board, color: chess.Color) -> Dict[int, int]:
    """file index -> how many pawns of `color` stand on it."""
    counts: Dict[int, int] = {}
    for square in board.pieces(chess.PAWN, color):
        f = chess.square_file(square)
        counts[f] = counts.get(f, 0) + 1
    return counts


def _doubled(files: Dict[int, int]) -> int:
    """Pawns standing behind a friend on the same file.

    Two pawns on one file counts as one doubled pawn, three counts as two --
    the count is "how many pawns are surplus on their file", which is what
    actually hurts.
    """
    return sum(n - 1 for n in files.values() if n > 1)


def _isolated(files: Dict[int, int]) -> int:
    """Pawns with no friendly pawn on either neighbouring file."""
    total = 0
    for f, n in files.items():
        if files.get(f - 1) or files.get(f + 1):
            continue
        total += n
    return total


def _islands(files: Dict[int, int]) -> int:
    """Groups of pawns separated by an empty file. Fewer is healthier."""
    occupied = sorted(files)
    if not occupied:
        return 0
    islands = 1
    for prev, nxt in zip(occupied, occupied[1:]):
        if nxt - prev > 1:
            islands += 1
    return islands


def _backward(board: chess.Board, color: chess.Color, files: Dict[int, int]) -> int:
    """Pawns behind both neighbours, whose advance square is pawn-controlled.

    The classic definition: it cannot advance safely and no friendly pawn can
    ever defend it, so it stays a target.
    """
    forward = 1 if color == chess.WHITE else -1
    total = 0
    for square in board.pieces(chess.PAWN, color):
        f, r = chess.square_file(square), chess.square_rank(square)
        neighbours = [
            chess.square_rank(s)
            for nf in (f - 1, f + 1)
            if 0 <= nf <= 7
            for s in board.pieces(chess.PAWN, color)
            if chess.square_file(s) == nf
        ]
        if not neighbours:
            continue
        # Behind every neighbour (further from promotion).
        if color == chess.WHITE and any(nr <= r for nr in neighbours):
            continue
        if color == chess.BLACK and any(nr >= r for nr in neighbours):
            continue
        ahead_rank = r + forward
        if not 0 <= ahead_rank <= 7:
            continue
        ahead = chess.square(f, ahead_rank)
        if board.attackers(not color, ahead) & board.pieces(chess.PAWN, not color):
            total += 1
    return total


def _mobility(board: chess.Board, color: chess.Color) -> Dict[str, int]:
    """How many squares this side's pieces can reach, and the worst piece.

    Principle 1 in numbers. `worst_piece_mobility` is the smallest count among
    the side's real pieces -- the piece a positional player would be looking
    to improve. Pawns and the king are excluded: a pawn's mobility says
    nothing about whether it is well placed, and the king's says more about
    danger than activity.

    Mobility is counted from a board where it is this side's turn, so it
    measures what the pieces could do, not whose move it happens to be.
    """
    probe = board.copy(stack=False)
    probe.turn = color
    probe.clear_stack()
    counts = []
    for piece_type in _PIECE_TYPES:
        for square in probe.pieces(piece_type, color):
            n = sum(1 for m in probe.legal_moves if m.from_square == square)
            counts.append(n)
    if not counts:
        return {"total_mobility": 0, "worst_piece_mobility": None, "pieces": 0}
    return {
        "total_mobility": sum(counts),
        "worst_piece_mobility": min(counts),
        "pieces": len(counts),
    }


HOME_BISHOP_SQUARES = {
    chess.WHITE: frozenset((chess.C1, chess.F1)),
    chess.BLACK: frozenset((chess.C8, chess.F8)),
}


def bishop_details(board: chess.Board, color: chess.Color) -> List[Dict[str, Any]]:
    """Per-bishop measurements behind `bad_bishop_pawns`. Measurement only.

    Returns one entry per bishop of `color` with the raw numbers and no
    verdict: which square it stands on, how many of its own pawns sit on its
    colour, how many squares it can move to, and whether it is still on its
    starting square.

    Deliberately threshold-free. "How many pawns block it" is a property of
    the board; "how many is too many" is a coaching judgement that belongs to
    whoever is grading, not here. Callers that want a yes/no bad-bishop
    verdict apply their own cut-offs to these numbers, so the measurement has
    exactly one definition even when the verdicts differ.
    """
    own = int(board.occupied_co[color])
    pawns = int(board.pieces(chess.PAWN, color))
    out: List[Dict[str, Any]] = []
    for square in board.pieces(chess.BISHOP, color):
        light = bool(chess.BB_LIGHT_SQUARES & chess.BB_SQUARES[square])
        mask = chess.BB_LIGHT_SQUARES if light else chess.BB_DARK_SQUARES
        out.append({
            "square": chess.square_name(square),
            "on_light_squares": light,
            "same_colour_pawns": chess.popcount(pawns & int(mask)),
            "mobility": chess.popcount(int(board.attacks(square)) & ~own),
            "undeveloped": square in HOME_BISHOP_SQUARES[color],
        })
    return out


def _bad_bishop_pawns(board: chess.Board, color: chess.Color) -> int:
    """Own pawns standing on the same colour squares as your own bishops.

    Principle 4, in its classic form: a bishop hemmed in by its own pawns is
    a bad bishop. Counted per bishop and summed, so a side with two bishops
    on the same colour is charged for both.
    """
    return sum(b["same_colour_pawns"] for b in bishop_details(board, color))


def _center_control(board: chess.Board, color: chess.Color) -> int:
    """How many of d4/e4/d5/e5 this side attacks. Principle 2."""
    return sum(1 for sq in CENTER_SQUARES if board.attackers(color, sq))


def _space(board: chess.Board, color: chess.Color) -> int:
    """Squares this side attacks on the opponent's half of the board.

    Principle 5. Space is "how far into their position can I operate", so it
    counts attacked squares beyond the midline rather than every square.
    """
    ranks = range(4, 8) if color == chess.WHITE else range(0, 4)
    total = 0
    for rank in ranks:
        for f in range(8):
            if board.attackers(color, chess.square(f, rank)):
                total += 1
    return total


def _undefended(board: chess.Board, color: chess.Color) -> int:
    """This side's pieces that nothing of its own is defending.

    Mohit's first answer when asked what positional play means for a player:
    "how well does he keep his pieces undefended". The king is excluded (it
    cannot be defended) and so are pawns, which are routinely and correctly
    left loose.
    """
    total = 0
    for piece_type in _PIECE_TYPES:
        for square in board.pieces(piece_type, color):
            if not board.attackers(color, square):
                total += 1
    return total


def positional_snapshot(board: chess.Board, color: chess.Color) -> Dict[str, Any]:
    """The positional condition of `board` for `color`, as plain numbers.

    Board-only and cheap: no engine, no database, no detector. Intended to be
    stored on every move record so positional ability can be summed over a
    player's games instead of read off a hardcoded 60.0.
    """
    files = _pawn_files(board, color)
    snapshot: Dict[str, Any] = {
        "doubled_pawns": _doubled(files),
        "isolated_pawns": _isolated(files),
        "backward_pawns": _backward(board, color, files),
        "pawn_islands": _islands(files),
        "undefended_pieces": _undefended(board, color),
        "bad_bishop_pawns": _bad_bishop_pawns(board, color),
        "center_control": _center_control(board, color),
        "space": _space(board, color),
    }
    snapshot.update(_mobility(board, color))
    return snapshot
