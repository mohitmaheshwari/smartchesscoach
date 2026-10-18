"""Counting the even trades a player was offered, and how many they took.

This is the stored half of the `trade_seeking` trait. The trait itself is a
sum over games; the counting has to happen once, when a game is analysed,
because it needs every board replayed and `/progress/how-you-play` answers a
live request off stored aggregates.

WHAT IS COUNTED, AND WHY EACH CONDITION IS THERE
------------------------------------------------
An OFFER is a position where the player could have made an even trade and
could have done something else instead:

  * a legal capture of theirs, where attacker and victim are worth within a
    pawn of each other -- a queen taking a pawn is not a trade
  * the destination is DEFENDED, so the exchange is an exchange. An
    undefended capture is a free piece and taking it is not a disposition,
    it is just correct
  * more than one legal move exists. No choice, no disposition
  * the position is LEVEL, |eval_before| < 100cp. Trading when ahead is good
    play and trading when behind is bad play, so counting every position
    would measure how often this player was winning -- strength wearing the
    costume of a preference, which is the mistake that killed `aggression`
    and nearly shipped `tilt`

A TAKE is an offer where the move actually played was one of them.

The measure is `taken / offered`. Counting trades MADE would measure how many
were available, which is a property of the games and not of the player.

EVIDENCE: docs/behavioural_measurement_data_inventory.md section 8.
Measured over 20 players with both a fast and a slow sample: stability 0.71,
spread across players 0.156, r +0.14 against error rate and -0.19 against
rating, and a player's own fast/slow rates differ by 0.037 where players
differ from each other by 0.156.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

import chess

# The window in which a trade is a choice rather than technique.
LEVEL_CP = 100
# Within a pawn of each other counts as even.
EVEN_WITHIN = 1
PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


def even_trades_available(board: chess.Board) -> List[chess.Move]:
    """The even, defended captures the side to move could choose right now.

    Empty when there is only one legal move: a forced move says nothing about
    what a player prefers.
    """
    legal = list(board.legal_moves)
    if len(legal) < 2:
        return []
    out: List[chess.Move] = []
    for move in legal:
        if not board.is_capture(move) or board.is_en_passant(move):
            continue
        attacker = board.piece_at(move.from_square)
        victim = board.piece_at(move.to_square)
        if attacker is None or victim is None:
            continue
        a = PIECE_VALUE.get(attacker.piece_type)
        v = PIECE_VALUE.get(victim.piece_type)
        if a is None or v is None or abs(a - v) > EVEN_WITHIN:
            continue
        after = board.copy()
        after.push(move)
        if not after.attackers(not board.turn, move.to_square):
            continue          # undefended: a free piece, not a trade
        out.append(move)
    return out


def count_trade_offers(move_evaluations: Optional[Iterable[Mapping[str, Any]]]) -> Dict[str, int]:
    """`{"offers": n, "taken": n}` for one game, from its stored move rows.

    Pure: no database, no engine. Reads `fen_before`, `move` and
    `eval_before`, all of which sit on 100% of stored rows. Rows for the
    opponent are skipped -- this is about the player's own choices.

    Never raises. A game whose rows cannot be read contributes nothing, which
    is the honest outcome: no evidence rather than a guessed one.
    """
    offers = 0
    taken = 0
    for row in (move_evaluations or []):
        try:
            if row.get("is_opponent_move"):
                continue
            evaluation = row.get("eval_before")
            fen = row.get("fen_before")
            san = row.get("move")
            if evaluation is None or not fen or not san:
                continue
            if abs(evaluation) >= LEVEL_CP:
                continue
            board = chess.Board(fen)
            available = even_trades_available(board)
            if not available:
                continue
            offers += 1
            if board.parse_san(san) in available:
                taken += 1
        except Exception:
            continue
    return {"offers": offers, "taken": taken}
