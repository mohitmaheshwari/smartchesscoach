"""What a bad move actually DID to the position, in numbers.

Why this exists
---------------
Mohit, 2026-09-22: *"i never want a vocab check or anything like that, you
know? never, it's a maths thing, always maths for every verification, from
chess squares or whatever, never string matching."*

Every fault found in ChessGuru's player intelligence that day was a string
comparison, and not one was a chess problem:

    if "complex" in subcat        -> never matched; branch never ran
    if "positional" in cat        -> never matched; score stuck at 60.0
    if "opening" in subcat        -> never matched; score stuck at 65.0
    BlunderType("king_safety")    -> raised; 867 of Mohit's blunders dropped

The last one is what this module replaces. `blunder_taxonomy.by_type` holds
the cognitive-gap spelling (`king_safety`) while the enum expects
`king_safety_neglect`, so the most common blunder type on the founder's
account is discarded on every load. The fix is NOT to teach the matcher a
second spelling -- that is the same bug with a longer list. The fix is to
stop asking what a move was CALLED and measure what it DID.

So this returns deltas, not categories. Every number is the difference
between the position before the move and after it, computed from the board:

    king_attackers_delta   enemy pieces bearing on the squares around my king
    hanging_value_delta    material of mine left attacked and undefended
    mobility_delta         squares my pieces can reach
    undefended_delta       pieces of mine nothing defends
    doubled_delta          pawns surplus on their file
    worst_piece_delta      how boxed in my worst-placed piece is

No thresholds are applied here and no category is named. Which delta counts
as "the" blunder is a separate ruling that must be read off the distribution
of these numbers, the way PROBLEM_PHASE_SHARE and the +200 winning boundary
were. Naming a category here would smuggle a guess back in.

LOAD-BEARING: board only. No engine, no database, no labels, no enum.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import chess

from services.positional_snapshot import positional_snapshot

#: Standard values, in centipawns. The king is absent on purpose: it cannot
#: be won, so it has no material value to put at risk.
PIECE_VALUE = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 320,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}


def king_zone_attackers(board: chess.Board, color: chess.Color) -> int:
    """How many enemy pieces bear on the squares around `color`'s king.

    This is the maths behind "was the king exposed". The old code asked
    whether a label contained the word `king_safety`; this counts attackers
    on the king's own square and its eight neighbours, which is true or false
    from the position and needs nobody to agree on a spelling.

    Counted per attacking piece per square, so a queen raking three squares
    around the king weighs more than a knight touching one -- which is what
    actually makes a king position dangerous.
    """
    king = board.king(color)
    if king is None:
        return 0
    zone = [king] + list(chess.SquareSet(chess.BB_KING_ATTACKS[king]))
    return sum(len(board.attackers(not color, sq)) for sq in zone)


def hanging_value(board: chess.Board, color: chess.Color) -> int:
    """Centipawns of `color`'s material that is attacked and undefended.

    Deliberately the simple form -- attacked, with nothing of its own
    defending it -- rather than a full exchange evaluation. A defended piece
    can still be lost to a better exchange, but that is a different claim
    needing a different proof, and mixing the two would make this number mean
    two things at once.
    """
    total = 0
    for piece_type, value in PIECE_VALUE.items():
        for square in board.pieces(piece_type, color):
            if not board.attackers(not color, square):
                continue
            if board.attackers(color, square):
                continue
            total += value
    return total


def _measure(board: chess.Board, color: chess.Color) -> Dict[str, Any]:
    snap = positional_snapshot(board, color)
    return {
        "king_attackers": king_zone_attackers(board, color),
        "hanging_value": hanging_value(board, color),
        "mobility": snap.get("total_mobility") or 0,
        "undefended": snap.get("undefended_pieces") or 0,
        "doubled": snap.get("doubled_pawns") or 0,
        "worst_piece_mobility": snap.get("worst_piece_mobility"),
    }


def blunder_anatomy(
    fen_before: str,
    move_uci: str,
    fen_after: Optional[str] = None,
    refutation: Optional[Any] = None,
) -> Dict[str, Any]:
    """What this move did to the mover's own position, as deltas.

    `fen_after` is used when given -- the stored position is authoritative
    over one this function replays -- and otherwise the move is pushed.

    Every value is a change in a counted quantity. Positive means more of
    that thing after the move: `king_attackers_delta: +3` means three more
    enemy pieces bear on the squares around the king than before.

    Returns {} rather than raising on a position it cannot read: a malformed
    stored FEN must not cost the caller, and an absent anatomy is honestly
    absent instead of a row of misleading zeroes.
    """
    try:
        before = chess.Board(fen_before)
        mover = before.turn
        move = chess.Move.from_uci(str(move_uci))
        if move not in before.legal_moves:
            return {}
        if fen_after:
            after = chess.Board(fen_after)
        else:
            after = before.copy(stack=False)
            after.push(move)
    except (ValueError, AssertionError, KeyError, TypeError):
        return {}

    # Measure AFTER THE REFUTATION when one is stored, not after the move.
    #
    # Measured first without this over 848 blunders and 5,300 good moves:
    # every delta had an identical median of 0, and only the worst tenth of
    # blunders separated at all. The reason is the same one Mohit showed with
    # Nbd7 -- most blunders do not leave a piece hanging, they ALLOW
    # something, and the material moves on the OPPONENT'S reply. Measuring
    # the position straight after the player's own move reads the position
    # before anything has happened to it.
    #
    # `refutation` is the engine's line after the move played
    # (`pv_after_played`), so walking it lands on the position the mistake
    # actually produced.
    if refutation:
        walked = after.copy(stack=False)
        for san_or_uci in list(refutation)[:4]:
            token = str(san_or_uci)
            mv = None
            try:
                mv = walked.parse_san(token)
            except Exception:  # noqa: BLE001
                try:
                    candidate = chess.Move.from_uci(token)
                    mv = candidate if candidate in walked.legal_moves else None
                except Exception:  # noqa: BLE001
                    mv = None
            if mv is None:
                break
            walked.push(mv)
        after = walked

    a = _measure(before, mover)
    b = _measure(after, mover)

    worst_delta = None
    if a["worst_piece_mobility"] is not None and b["worst_piece_mobility"] is not None:
        worst_delta = b["worst_piece_mobility"] - a["worst_piece_mobility"]

    return {
        "king_attackers_delta": b["king_attackers"] - a["king_attackers"],
        "hanging_value_delta": b["hanging_value"] - a["hanging_value"],
        "mobility_delta": b["mobility"] - a["mobility"],
        "undefended_delta": b["undefended"] - a["undefended"],
        "doubled_delta": b["doubled"] - a["doubled"],
        "worst_piece_delta": worst_delta,
        # Absolute values after the move, so a caller can tell "left two
        # pieces hanging" from "already had two hanging and added none".
        "king_attackers_after": b["king_attackers"],
        "hanging_value_after": b["hanging_value"],
    }
