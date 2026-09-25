"""The piece-safety lesson, rebuilt to show rather than ask.

See docs/show_dont_ask_lesson_scope.md, signed off 2026-09-25.

The old lesson asked the player what he had checked before moving and gave
him three canned thoughts to choose between. Nobody can answer that honestly
-- people do not recall what they checked, they reconstruct a reason that
fits the outcome -- so the answer was noise and we graded it. A coach never
asks. A coach shows what happened and then makes you do it again properly.

Five screens, no multiple choice anywhere:

    1 moment    his own move, played out, punished, with the arrow
    2 cause     one transferable sentence
    3 retry     same position, play anything that cannot be taken
    4 transfer  a DIFFERENT position with the same cause
    5 habit     one sentence, identical every time

WHAT THIS MODULE DOES NOT DECIDE
--------------------------------
Whether a move is safe. `destination_safety_detector.grade_destination_
safety_candidate` already owns that, and it is stricter than anything written
here would be: it runs two independent exchange proofs and refuses to answer
when they disagree. Re-deriving "safe" here would be a second definition of
the concept the lesson is teaching, which is exactly how the same idea ends
up meaning two things in one codebase.

This module computes only what that grader does not return: WHICH enemy piece
does the taking, so the board can draw it.

NO ENGINE. Every fact below is board geometry over a stored position, so a
click costs nothing and the lesson stays fast.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess

# Plain words. The audience is 600-1500 and many are not reading in their
# first language, so no chess term a beginner would have to look up.
PIECE_WORDS = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

# Screen 2. Names the cause, never the move -- moves do not repeat, causes do.
CAUSE_LINE = "The square you moved to was already being watched."

# Screen 5. Identical every time on purpose: a habit is one sentence
# repeated, not a new phrasing each visit.
HABIT_LINE = "Before you let go of a piece: look at the square, ask what watches it."

RETRY_TASK = "Play a move that nothing can take."


def _cheapest_legal_taker(board: chess.Board, square: int) -> Optional[int]:
    """Which enemy piece actually takes on `square`, for the arrow.

    The cheapest one, because that is what a player would really play, and
    legal rather than pseudo-legal: a pinned piece cannot capture, and drawing
    an arrow from one would be showing a threat that does not exist.
    """
    best_square = None
    best_value = None
    for candidate in board.legal_moves:
        if candidate.to_square != square or not board.is_capture(candidate):
            continue
        piece = board.piece_at(candidate.from_square)
        if piece is None:
            continue
        # The king is ranked LAST, not first. Static exchange gives it 0
        # because it cannot be captured back, and taking that convention here
        # made the king the "cheapest" taker on every square it touched -- so
        # a board where a pawn and the king both watch the square drew the
        # king, when a player recaptures with the pawn and keeps the king out
        # of it. The king still gets drawn when it is the only legal taker,
        # which is common after a check.
        value = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                 chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 10}.get(
                     piece.piece_type, 5)
        if best_value is None or value < best_value:
            best_value, best_square = value, candidate.from_square
    return best_square


def grade_attempt(fen: str, move: str) -> Dict[str, Any]:
    """Is this attempt safe, and if not, who takes it?

    Verdict comes from the shared grader. Three of its outcomes mean "do not
    stop the player here":

      pass                 the destination holds
      piece_not_eligible   a pawn or king move -- it cannot hang a PIECE on
                           its square, which is the only thing this lesson
                           teaches. Accepted rather than marked wrong, because
                           failing someone for a sound pawn move while the
                           card says "play a move that nothing can take" would
                           be marking them against a rule we did not print.
      unmeasured           the two exchange proofs disagreed. We do not know,
                           so we do not accuse.
    """
    from services.destination_safety_detector import (
        grade_destination_safety_candidate,
    )

    graded = grade_destination_safety_candidate(fen, move)
    reason = str(graded.get("reason") or "")
    status = str(graded.get("status") or "")

    out: Dict[str, Any] = {
        "accepted": status != "fail",
        "status": status,
        "reason": reason,
        "arrows": [],
        "message": "",
    }
    if status != "fail":
        return out

    # It hangs. Find the taker so the board can show it rather than say it.
    try:
        board = chess.Board(fen)
        try:
            played = chess.Move.from_uci(str(move).strip().lower())
            if played not in board.legal_moves:
                raise ValueError
        except ValueError:
            played = board.parse_san(str(move).strip())
        board.push(played)
    except Exception:  # noqa: BLE001
        return out

    taker = _cheapest_legal_taker(board, played.to_square)
    if taker is None:
        return out
    piece = board.piece_at(taker)
    out["arrows"] = [[chess.square_name(taker),
                      chess.square_name(played.to_square), "red"]]
    out["message"] = "Their %s on %s is watching that square." % (
        PIECE_WORDS.get(piece.piece_type, "piece") if piece else "piece",
        chess.square_name(taker),
    )
    return out


def safe_move_count(fen: str) -> int:
    """How many moves survive the grader. Printed as "N moves work here" so
    the player knows this is not a find-the-one-move puzzle."""
    try:
        board = chess.Board(fen)
    except Exception:  # noqa: BLE001
        return 0
    return sum(1 for mv in board.legal_moves
               if grade_attempt(fen, mv.uci())["accepted"])


def build_moment(fen_before: str, played_san: str) -> Optional[Dict[str, Any]]:
    """Screen 1: his move, and the reply that punished it.

    Returns None when the move was not in fact punished on its square. That
    is not a failure -- it means this stored moment is not an example of this
    lesson, and a lesson must never open by claiming something the board does
    not show.
    """
    try:
        board = chess.Board(fen_before)
        played = board.parse_san(str(played_san).strip())
    except Exception:  # noqa: BLE001
        return None

    graded = grade_attempt(fen_before, played.uci())
    if graded["accepted"]:
        return None

    after = board.copy()
    after.push(played)
    taker = _cheapest_legal_taker(after, played.to_square)
    if taker is None:
        return None
    taker_piece = after.piece_at(taker)
    moved_piece = board.piece_at(played.from_square)
    reply = chess.Move(taker, played.to_square)
    try:
        reply_san = after.san(reply)
    except Exception:  # noqa: BLE001
        reply_san = None

    return {
        "fen_before": fen_before,
        "played_san": played_san,
        "played_uci": played.uci(),
        "reply_san": reply_san,
        "reply_uci": reply.uci(),
        "arrows": [[chess.square_name(taker),
                    chess.square_name(played.to_square), "red"]],
        # Two short sentences, one idea each. The first is what he did, the
        # second is what happened -- no verdict word, because watching it is
        # the verdict.
        "line_one": "You played %s." % played_san,
        "line_two": "Their %s on %s took it straight back." % (
            PIECE_WORDS.get(taker_piece.piece_type, "piece") if taker_piece
            else "piece",
            chess.square_name(taker),
        ),
        "lost_piece": PIECE_WORDS.get(
            moved_piece.piece_type, "piece") if moved_piece else "piece",
    }


def build_lesson(
    moment_fen: str,
    moment_move: str,
    transfer_fen: Optional[str] = None,
    transfer_is_own_game: bool = True,
) -> Optional[Dict[str, Any]]:
    """The whole lesson, or None when the moment does not support one."""
    moment = build_moment(moment_fen, moment_move)
    if moment is None:
        return None

    lesson: Dict[str, Any] = {
        "kind": "show_dont_ask",
        "concept": "piece_safety",
        "moment": moment,
        "cause": CAUSE_LINE,
        "retry": {
            "fen": moment_fen,
            "task": RETRY_TASK,
            "safe_move_count": safe_move_count(moment_fen),
        },
        "habit": HABIT_LINE,
    }
    if transfer_fen:
        lesson["transfer"] = {
            "fen": transfer_fen,
            "task": RETRY_TASK,
            # Honest either way. A stranger's position is never presented as
            # the player's own -- the force of screen 1 is that it really
            # happened to him, and borrowing that would be a small lie.
            "label": ("DIFFERENT GAME · SAME IDEA" if transfer_is_own_game
                      else "SOMEONE ELSE'S GAME · SAME IDEA"),
            "safe_move_count": safe_move_count(transfer_fen),
        }
    return lesson


def transfer_position_is_usable(fen: str, min_unsafe: int = 3) -> bool:
    """Would this board make a fair "play something safe" screen?

    Needs at least one safe move, or the screen cannot be passed, and enough
    unsafe ones that the safe move is a choice rather than the only legal
    option. Measured on 300 production piece-safety puzzles: 296 pass, and
    the 4 that fail have no safe move at all.
    """
    try:
        board = chess.Board(fen)
    except Exception:  # noqa: BLE001
        return False
    safe = unsafe = 0
    for mv in board.legal_moves:
        if grade_attempt(fen, mv.uci())["accepted"]:
            safe += 1
        else:
            unsafe += 1
    return safe >= 1 and unsafe >= min_unsafe
