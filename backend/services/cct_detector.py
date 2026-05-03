"""
CCT Detector — Checks, Captures, Threats (and Trades).

Tags every USER move in a game with whether it was a forcing move,
whether forcing options were available, and whether the engine's best
move was forcing. These tags drive:

  - "Held the initiative after a miss" pattern detection (phase 3)
  - CCT-discipline score per game (phase 2)
  - Coach voice that recognizes forcing-move discipline as a strength,
    not just penalizes the missed killer (phase 4-6)

The detector is a pure function — takes a board state and a move,
returns tags. No I/O, no MongoDB, no LLM. Cheap enough to run on
every move during analysis (sub-millisecond per move).

Usage:

    from services.cct_detector import classify_move_cct, tag_moves_with_cct

    # Per-move (during analysis loop):
    tags = classify_move_cct(board_before, move, best_move=best_move)
    # → {"is_check": True, "is_capture": False, "creates_threat": False,
    #    "forcing": True, "had_forcing_options": True,
    #    "best_was_forcing": True, "played_forcing_when_best_was_forcing": True}

    # Whole-game (post-stockfish):
    tagged_moves = tag_moves_with_cct(pgn_string, user_color, best_moves_san)
"""

from __future__ import annotations

import io
from typing import Dict, List, Optional

import chess
import chess.pgn


# Piece values used for "threat" detection (in pawn units)
_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,  # never the target of a "threat" — handled by check detection
}


def _is_check_move(board_before: chess.Board, move: chess.Move) -> bool:
    """Does this move give check?"""
    sim = board_before.copy(stack=False)
    sim.push(move)
    return sim.is_check()


def _is_capture_move(board_before: chess.Board, move: chess.Move) -> bool:
    """Does this move capture a piece (incl. en passant)?"""
    return board_before.is_capture(move)


def _creates_immediate_threat(
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> bool:
    """Does the move create a position where the user can win material
    on the next turn even if the opponent does nothing useful?

    Mechanism: apply the move, then "give the opponent a null move"
    (flip turn back to user without any reply), and check whether any
    enemy piece (worth >= 1 pawn) is now attacked by the user with
    either no defenders OR the cheapest attacker is worth less than
    the victim. That's a winning capture available next turn.

    This catches:
      - Hung-piece attacks created by the move
      - Forks (one piece hits two; one is winning)
      - Discovered attacks
      - Pin setups where the pinned piece is now winnable

    Misses:
      - Long-term positional threats (these aren't really CCT anyway)
      - Mate threats (CHECK is handled separately by _is_check_move
        on the move itself; mate-threats-without-check are rare and
        usually paired with a captureable piece anyway)

    A check move is NOT also tagged as "threat" — they're orthogonal
    categories in the CCT framework.
    """
    sim = board_before.copy(stack=False)
    sim.push(move)
    if sim.is_check():
        # Check is its own category — don't double-count
        return False

    # Null-move: pretend it's the user's turn again
    sim.turn = user_color

    for sq, piece in sim.piece_map().items():
        if piece.color == user_color or piece.piece_type == chess.KING:
            continue

        if not sim.is_attacked_by(user_color, sq):
            continue

        attackers = sim.attackers(user_color, sq)
        defenders = sim.attackers(not user_color, sq)
        victim_value = _PIECE_VALUES.get(piece.piece_type, 0)
        if victim_value <= 0:
            continue

        if not defenders:
            return True

        cheapest_attacker = min(
            _PIECE_VALUES.get(sim.piece_at(a).piece_type, 99)
            for a in attackers
            if sim.piece_at(a)
        )
        if cheapest_attacker < victim_value:
            return True

    return False


def _had_forcing_options(board_before: chess.Board) -> bool:
    """Were any check or capture moves legally available before this move?

    Skips the threat-detection pass for speed — checks + captures
    cover the vast majority of "forcing options exist" cases. A
    pure-threat-only situation with no checks or captures available
    is rare enough to ignore at this layer.
    """
    for m in board_before.legal_moves:
        if board_before.is_capture(m):
            return True
        sim = board_before.copy(stack=False)
        sim.push(m)
        if sim.is_check():
            return True
    return False


def _best_was_forcing(
    board_before: chess.Board,
    best_move: Optional[chess.Move],
    user_color: chess.Color,
) -> bool:
    """Was the engine's preferred move a forcing move?

    A forcing move = check, capture, OR creates immediate threat. We
    care because if best was forcing, then "played forcing" is the
    right CCT decision (whether or not the user found THE best).
    """
    if best_move is None:
        return False
    if board_before.is_capture(best_move):
        return True
    sim = board_before.copy(stack=False)
    sim.push(best_move)
    if sim.is_check():
        return True
    # For best-was-forcing, also include threat — we want every
    # forcing-shaped engine recommendation to count.
    return _creates_immediate_threat(board_before, best_move, user_color)


def classify_move_cct(
    board_before: chess.Board,
    move: chess.Move,
    *,
    best_move: Optional[chess.Move] = None,
    user_color: Optional[chess.Color] = None,
) -> Dict:
    """Classify a single move along the CCT axes.

    Args:
        board_before: position before the move (board.turn is the
            moving player).
        move: the move that was played.
        best_move: engine's top choice in this position (optional).
            When provided, enables `best_was_forcing` and
            `played_forcing_when_best_was_forcing` tags — the core
            inputs for CCT-discipline scoring.
        user_color: the moving player's color. Defaults to
            board_before.turn — only override for analysis where
            we want CCT discipline measured for one specific side
            regardless of whose turn it is.

    Returns:
        Dict of bool tags. Always includes `is_check`, `is_capture`,
        `creates_threat`, `forcing`, `had_forcing_options`. When
        best_move is provided, also `best_was_forcing` and
        `played_forcing_when_best_was_forcing`.
    """
    if user_color is None:
        user_color = board_before.turn

    is_check = _is_check_move(board_before, move)
    is_capture = _is_capture_move(board_before, move)
    creates_threat = _creates_immediate_threat(board_before, move, user_color)
    forcing = is_check or is_capture or creates_threat

    tags = {
        "is_check": is_check,
        "is_capture": is_capture,
        "creates_threat": creates_threat,
        "forcing": forcing,
        "had_forcing_options": _had_forcing_options(board_before),
    }

    if best_move is not None:
        best_forcing = _best_was_forcing(board_before, best_move, user_color)
        tags["best_was_forcing"] = best_forcing
        # The CCT-decision quality bit: when best was forcing and we
        # also played a forcing move (even a different one), we held
        # the discipline. That's the signal to reward.
        tags["played_forcing_when_best_was_forcing"] = bool(best_forcing and forcing)

    return tags


def tag_moves_with_cct(
    pgn_string: str,
    user_color: str = "white",
    best_moves_san: Optional[List[str]] = None,
) -> List[Dict]:
    """Run CCT classification across every USER move in a game.

    Used as a post-Stockfish pass: pgn + best moves come from the
    main analysis run; we replay the game move-by-move and emit
    tags for every move the user played.

    Args:
        pgn_string: full PGN of the game.
        user_color: which color is the user ('white' or 'black').
        best_moves_san: parallel list of engine best moves in SAN,
            indexed by ply. When None, best-was-forcing tags are
            omitted. List length should equal the number of plies
            in the game; missing/None entries are tolerated.

    Returns:
        List of dicts, one per USER move (opponent moves are not
        included). Each dict contains:
            ply: int (0-indexed; what ply this user move sits at)
            move_san: the user's move
            best_move_san: engine's best (may be None)
            ...all CCT tag bools from classify_move_cct
    """
    user_color_bool = chess.WHITE if user_color == "white" else chess.BLACK

    pgn_io = io.StringIO(pgn_string)
    game = chess.pgn.read_game(pgn_io)
    if not game:
        return []

    out: List[Dict] = []
    board = game.board()
    ply = 0

    for node in game.mainline():
        move = node.move
        is_user_move = board.turn == user_color_bool

        if is_user_move:
            move_san = board.san(move)
            best_san = (
                best_moves_san[ply]
                if best_moves_san and ply < len(best_moves_san)
                else None
            )
            best_move_obj = None
            if best_san:
                try:
                    best_move_obj = board.parse_san(best_san)
                except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
                    best_move_obj = None

            tags = classify_move_cct(
                board, move, best_move=best_move_obj, user_color=user_color_bool
            )
            tags.update({
                "ply": ply,
                "move_san": move_san,
                "best_move_san": best_san,
            })
            out.append(tags)

        board.push(move)
        ply += 1

    return out


# ─── Phase 2: per-game CCT aggregate ──────────────────────────────────


def compute_cct_aggregate(tagged_moves: List[Dict]) -> Dict:
    """Roll up tagged moves into per-game CCT discipline metrics.

    Args:
        tagged_moves: output of tag_moves_with_cct (user moves only).

    Returns:
        {
          "cct_decisions": int,        # moves where best was forcing
          "cct_correct": int,          # of those, how many played forcing
          "cct_score": float,          # cct_correct / cct_decisions, 0..1
          "cct_max_streak": int,       # longest run of correct CCT decisions
          "forcing_moves_played": int, # absolute count of forcing user moves
          "user_moves_total": int,
        }
    """
    decisions = 0
    correct = 0
    streak = 0
    max_streak = 0
    forcing_played = 0

    for m in tagged_moves:
        if m.get("forcing"):
            forcing_played += 1

        # CCT discipline only measured when the engine's recommendation
        # was forcing (we have a clear "should have considered forcing"
        # moment). Quiet positions don't count for or against.
        if m.get("best_was_forcing"):
            decisions += 1
            if m.get("played_forcing_when_best_was_forcing"):
                correct += 1
                streak += 1
                if streak > max_streak:
                    max_streak = streak
            else:
                streak = 0

    score = (correct / decisions) if decisions > 0 else None

    return {
        "cct_decisions": decisions,
        "cct_correct": correct,
        "cct_score": round(score, 3) if score is not None else None,
        "cct_max_streak": max_streak,
        "forcing_moves_played": forcing_played,
        "user_moves_total": len(tagged_moves),
    }
