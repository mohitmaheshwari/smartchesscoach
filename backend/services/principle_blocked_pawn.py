"""Blocked-own-pawn-advance detector — names an opening principle the
user just violated.

Mohit 2026-05-21 driver: positions like
r1bqk2r/1pppnpbp/p1n1p1p1/4P3/2BP4/5N2/PPP2PPP/RNBQ1RK1 w - - 0 7,
where the engine's best move is c3 (pawn) but the user plays Nc3 (knight).
The user just blocked their own c-pawn from supporting d4. cp_loss is
only ~60, so R12_blunder doesn't fire — basic_mistake catches it,
but currently just says "Nc3 is a mistake. c3 was better." — no why.

This detector produces the why: name the principle ("blocks the c-pawn"),
and when the pawn would have supported a real central pawn, name that
too ("c3 would have supported your d4 pawn").

Geometric only — no engine, no LLM. The detector's claim is verifiable:
the played move's to_square equals the engine's best move's to_square,
and the engine's best move was a pawn move.

Generalizes across positions:
  - Nbc3 vs c3 supporting d4 (Pirc / Modern)
  - Nbd2 vs d3 supporting e4
  - Nge2 vs e3 supporting d4 (Caro-Kann reverse)
  - Bd3 vs d4 (less common, but same family)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess


# Only fires in the opening / very-early middlegame. Beyond move 15,
# central pawn structure is usually committed and the principle isn't
# the lesson.
_MAX_MOVE_NUMBER = 15

# Skip moves that aren't real losses. cp_loss < 30 means it's a
# preference, not a mistake — don't lecture the user about principles
# when they didn't actually lose ground.
_MIN_CP_LOSS = 30


_FILE_NAMES = "abcdefgh"


def detect_blocked_pawn(
    fen_before: str,
    played_san: str,
    best_move_san: str,
    move_number: int,
    cp_loss: int,
) -> Optional[Dict[str, Any]]:
    """Return evidence when the user played a non-pawn piece move to a
    square the engine's best move (a pawn) wanted to occupy.

    Args:
      fen_before: position FEN before the user's move was played.
      played_san: the user's actual move (SAN).
      best_move_san: engine's preferred move (SAN).
      move_number: 1-indexed full move number.
      cp_loss: centipawn loss of the played move (already engine-verified).

    Returns:
      {"pawn_file": "c",
       "blocked_square": "c3",
       "pawn_san": "c3",
       "would_support": ["d4"],   # existing user pawns the block would defend
       "would_prepare": ["d4"]}   # user pawns positioned to push to that square next
      or None when no blocked-pawn pattern detected.

    `would_prepare` is the Parth fb_6e38c6a6f53e fix: when the d-pawn is
    still on d3 (not d4), the c3 pawn push isn't "supporting d4" — it's
    PREPARING the d4 break. That is the actual teaching for the most
    common case in Italian/Pirc-family centers.
    """
    if move_number > _MAX_MOVE_NUMBER:
        return None
    if cp_loss < _MIN_CP_LOSS:
        return None
    if not fen_before or not played_san or not best_move_san:
        return None
    if played_san == best_move_san:
        return None

    try:
        board = chess.Board(fen_before)
        played_move = board.parse_san(played_san)
        best_move = board.parse_san(best_move_san)
    except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError):
        return None

    # Engine's best must be a pawn move.
    best_piece = board.piece_at(best_move.from_square)
    if best_piece is None or best_piece.piece_type != chess.PAWN:
        return None

    # User's move must be a non-pawn piece move.
    played_piece = board.piece_at(played_move.from_square)
    if played_piece is None or played_piece.piece_type == chess.PAWN:
        return None

    # Same color (sanity — both moves are by the user).
    if best_piece.color != played_piece.color:
        return None

    # Critical condition: both moves land on the same square. That's
    # the "you blocked the pawn's destination" signal.
    if best_move.to_square != played_move.to_square:
        return None

    user_color = best_piece.color
    target_sq = best_move.to_square
    pawn_from_sq = best_move.from_square
    pawn_file_idx = chess.square_file(pawn_from_sq)
    target_file_idx = chess.square_file(target_sq)
    target_rank = chess.square_rank(target_sq)

    # Sanity: the pawn moved straight up its file (one-square push or
    # two-square initial push). If it was a capture (different file)
    # the "blocking the pawn" framing is wrong — it'd be "blocking the
    # capture," a different teaching.
    if pawn_file_idx != target_file_idx:
        return None

    # Identify any *user's own* pawns that would have been supported
    # diagonally by the pawn on the target square. A pawn on c3
    # supports b4 and d4 (one rank forward, ±1 file). Only count pawns
    # in central squares (files c-f, ranks 4-5) — those are the pawns
    # whose support genuinely matters for opening structure.
    forward_rank = target_rank + (1 if user_color == chess.WHITE else -1)
    central_files = {2, 3, 4, 5}  # c, d, e, f
    central_ranks = {3, 4}        # rank 4 and 5 (0-indexed)
    would_support: List[str] = []
    if 0 <= forward_rank < 8:
        for df in (-1, 1):
            f = target_file_idx + df
            if not (0 <= f < 8):
                continue
            if f not in central_files:
                continue
            if forward_rank not in central_ranks:
                continue
            sq = chess.square(f, forward_rank)
            p = board.piece_at(sq)
            if p and p.piece_type == chess.PAWN and p.color == user_color:
                would_support.append(chess.square_name(sq))

    # ── would_prepare: the d4-break case (Parth fb_6e38c6a6f53e). When
    # the diagonal-forward central square is EMPTY but a user pawn on
    # the same file is one push away from reaching it, the blocked push
    # was PREPARING that future break (c3 prepares d4, e3 prepares d4
    # or f4, etc.). One-step push from rank target-1, OR two-step from
    # the starting rank when the intermediate square is clear.
    would_prepare: List[str] = []
    if 0 <= forward_rank < 8 and forward_rank in central_ranks:
        for df in (-1, 1):
            f = target_file_idx + df
            if not (0 <= f < 8) or f not in central_files:
                continue
            cand_sq = chess.square(f, forward_rank)
            if board.piece_at(cand_sq) is not None:
                continue  # already a piece there — would_support handles it
            if user_color == chess.WHITE:
                one_step_rank = forward_rank - 1
                two_step_rank = 1                       # rank 2 (0-indexed)
                two_step_valid = forward_rank == 3      # target = rank 4
            else:
                one_step_rank = forward_rank + 1
                two_step_rank = 6                       # rank 7 (0-indexed)
                two_step_valid = forward_rank == 4      # target = rank 5
            check_ranks = [one_step_rank]
            if two_step_valid:
                check_ranks.append(two_step_rank)
            for r in check_ranks:
                if not (0 <= r < 8):
                    continue
                p = board.piece_at(chess.square(f, r))
                if p is None or p.piece_type != chess.PAWN or p.color != user_color:
                    continue
                # Two-step from starting rank requires the intermediate
                # square to be empty (otherwise the pawn can't double-push).
                if r == two_step_rank and two_step_valid:
                    if board.piece_at(chess.square(f, one_step_rank)) is not None:
                        continue
                would_prepare.append(chess.square_name(cand_sq))
                break  # one match per file is enough

    # Filter: require the pawn to either be supporting a central pawn,
    # preparing one, OR be itself a central-file pawn (c/d/e/f). Otherwise
    # the teaching is too niche.
    pawn_is_central_file = pawn_file_idx in central_files
    if not would_support and not would_prepare and not pawn_is_central_file:
        return None

    return {
        "pawn_file": _FILE_NAMES[pawn_file_idx],
        "blocked_square": chess.square_name(target_sq),
        "pawn_san": best_move_san,
        "would_support": would_support,
        "would_prepare": would_prepare,
    }
