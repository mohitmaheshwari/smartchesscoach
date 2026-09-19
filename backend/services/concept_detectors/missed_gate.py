"""Shared gate for "you missed this concept" claims.

Every concept detector gates on `stored_best_matches` -- the move played must
BE the engine's move -- so it only ever runs on moves the player already got
right. Measured 2026-09-19 over 400 games and 12,365 moves: 1,644 fires,
1,639 "applied", 5 "wrong". A detector that can only say *you did it right*
cannot find a weakness or drive a lesson.

The symmetric branch asks the same predicate of the engine's move instead of
the player's. This module holds the gates that branch must pass, in one place,
because getting them wrong is how a coach starts scolding people for moves
that were fine.

See docs/missed_concept_scope.md.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import chess

# A real mistake, not an engine preference. Taken from the measured
# distribution of missed-concept candidates rather than chosen: p25 is 124cp
# and p50 is 164cp, so this floor keeps genuine errors and drops rounding.
MIN_MISTAKE_CP = 100

# Above this the position is a mate swing, not a material one. cp_loss on
# missed-development candidates runs to 9,684.
MATE_SCORE_CP = 9000


def missed_is_allowed(
    board_before: chess.Board,
    played_move: chess.Move,
    cp_loss: Optional[Any],
    mate_info: Optional[Dict] = None,
) -> bool:
    """Is a missed-concept claim permitted about this move at all?

    Precedence, the same order every detector fixed this month now obeys: a
    mate on the board outranks a hung piece, which outranks a missed concept.
    Being told "you should have developed" while being mated in two, or while
    a rook hangs, is the coach reading from a script instead of the board.
    """
    if not isinstance(cp_loss, (int, float)) or isinstance(cp_loss, bool):
        return False
    if cp_loss < MIN_MISTAKE_CP:
        return False
    # A mate swing is not a concept lesson.
    if cp_loss >= MATE_SCORE_CP:
        return False
    if mate_info:
        from analysis_interpreter import mate_gate_label
        colour = "white" if board_before.turn == chess.WHITE else "black"
        if mate_gate_label(mate_info, colour):
            return False
    # Something of theirs is hanging as a result: that is the lesson, not the
    # concept the engine's move happened to embody.
    try:
        from services.played_hangs_detector import detect_played_hangs
        if detect_played_hangs(
            board_before.copy(stack=False), played_move, cp_loss,
            mate_in_play=bool(mate_info),
        ):
            return False
    except Exception:  # noqa: BLE001
        # A helper failing must not let a claim through that it would have
        # blocked; fail closed.
        return False
    return True


def engine_move(board_before: chess.Board,
                best_move_san: Optional[str],
                best_move_uci: Optional[str]) -> Optional[chess.Move]:
    """The engine's move as a legal Move, or None if it cannot be trusted.

    Two stored best_move values in production are `O-O-O` in positions with no
    castling rights, so this parses rather than assumes.
    """
    for value, parser in ((best_move_uci, "uci"), (best_move_san, "san")):
        if not value:
            continue
        try:
            mv = (chess.Move.from_uci(str(value)) if parser == "uci"
                  else board_before.parse_san(str(value)))
        except (ValueError, AssertionError):
            continue
        if mv in board_before.legal_moves:
            return mv
    return None
