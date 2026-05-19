"""
Opening-deviation detection for Lab game review.

Phase-3 Component 2 (locked 2026-05-19). For each analyzed game,
detects the FIRST user-move where the user left book theory.
Surfaces in Lab game review as "you played the Italian Game through
move 6; at move 7 you played Bg5 (the book move was Be3)."

Across multiple games, the aggregator surfaces RECURRING deviation
patterns — "you've deviated to Bg5 in the Italian 4 times now."

Algorithm:
  Walk the game move-by-move. At each USER move, call
  match_opening_for_mover(cumulative_moves, user_color). The first
  ply where the match goes from non-None → None AND the previous
  match had a `next_expected` book move IS the deviation point.

  When the match goes None and `next_expected` was None on the
  previous step, that's book naturally ending — NOT a deviation.

Output schema (stored on game_analyses.opening_deviation):
{
  "user_color": "white" | "black",
  "in_book_through_user_move": int,   # last user-move # still in book
  "deviation": {
    "user_move_number": int,           # user's deviating move number
    "ply": int,                        # 0-indexed game ply
    "played_san": str,                 # what they actually played
    "expected_san": str,               # what book said
    "last_opening_name": str,          # the opening they left
  } | None,                            # None = no deviation (played full book)
  "version": int,
}
"""

from __future__ import annotations

import io
import logging
from typing import Any, Dict, Optional

import chess
import chess.pgn

from services.opening_lookup import match_opening_for_mover

logger = logging.getLogger(__name__)

OPENING_DEVIATION_VERSION = 1


def _user_move_number(ply_index: int, user_color: str) -> int:
    """Convert a 0-indexed game ply into the user's move-number (1-indexed).

    ply 0 = white move 1, ply 1 = black move 1, ply 2 = white move 2, ...
    User's move number = (ply_index // 2) + 1 regardless of color.
    """
    return (ply_index // 2) + 1


def detect_opening_deviation(
    pgn: str,
    user_color: str,
) -> Dict[str, Any]:
    """Walk the game, find the first ply where the user left book.

    Returns the deviation record (schema in module docstring). Always
    returns a dict — `deviation` field is None if the user never
    deviated within the authored opening's setup depth.
    """
    user_color = (user_color or "white").lower()
    if user_color not in ("white", "black"):
        user_color = "white"

    empty_result: Dict[str, Any] = {
        "user_color": user_color,
        "in_book_through_user_move": 0,
        "deviation": None,
        "version": OPENING_DEVIATION_VERSION,
    }

    if not pgn:
        return empty_result

    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return empty_result
    if game is None:
        return empty_result

    board = game.board()
    played_san: list = []
    last_match: Optional[Dict[str, Any]] = None
    last_match_at_user_move: int = 0

    for mv in game.mainline_moves():
        # Track who just moved.
        side_to_move_before = "white" if board.turn == chess.WHITE else "black"
        try:
            san = board.san(mv)
        except Exception:
            break
        played_san.append(san)
        try:
            board.push(mv)
        except Exception:
            break

        # We only test for deviations on the USER's moves.
        if side_to_move_before != user_color:
            continue

        current_match = match_opening_for_mover(played_san, user_color)
        user_move_num = _user_move_number(len(played_san) - 1, user_color)

        if current_match is None:
            # Three cases for None result, distinguished by last_match:
            #   (a) We've never had a match yet — too few user moves to
            #       hit min_matched_steps. Keep scanning, may match later.
            #   (b) We HAD a match and now we don't, AND that last match's
            #       next_expected was a real SAN → real deviation.
            #   (c) We HAD a match, now we don't, AND next_expected was
            #       None → book naturally ended (user followed full
            #       authored setup).
            if last_match is None:
                # (a) Still pre-book. Don't break — the next user move
                # might reach the min_matched_steps threshold.
                continue
            if last_match.get("next_expected"):
                # (b) Real deviation.
                return {
                    "user_color": user_color,
                    "in_book_through_user_move": last_match_at_user_move,
                    "deviation": {
                        "user_move_number": user_move_num,
                        "ply": len(played_san) - 1,
                        "played_san": san,
                        "expected_san": last_match["next_expected"],
                        "last_opening_name": last_match["name"],
                    },
                    "version": OPENING_DEVIATION_VERSION,
                }
            # (c) Book naturally ended. Stop scanning — we won't regain
            # a match on subsequent moves once we've exhausted setup.
            break

        # Match still alive — remember it for the next-iter comparison.
        last_match = current_match
        last_match_at_user_move = user_move_num

    # Reached end of game without deviation. Either played all book moves
    # OR the opening was too short (never reached min_matched_steps).
    return {
        "user_color": user_color,
        "in_book_through_user_move": last_match_at_user_move,
        "deviation": None,
        "version": OPENING_DEVIATION_VERSION,
    }
