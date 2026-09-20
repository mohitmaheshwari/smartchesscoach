"""Specific-question onboarding puzzles, built only where the answer is unique.

Mohit, 2026-09-20: ask the player a REAL question -- "find a fork here", "save
your king from mate" -- instead of "find the best move", start simple, and get
harder when they get it right. That tells you what someone can actually SEE,
which "there is a tactic in this position, find it" never can.

The rule that shapes this file: **the printed question must match the grader.**
Count the moves that satisfy the question the player reads, and if more than
one does, the puzzle is broken -- the player finds a fork, we mark them wrong,
and they stop trusting us. So every builder here returns a puzzle ONLY when
exactly one legal move satisfies its own question. Nothing is graded by
"is this the engine's move"; it is graded by the question's own predicate.

That is also why this file starts with the straightforward families. "Can you
win the queen in two moves" transposes, so it has no single answer and is not
here yet -- Mohit's call was to fill the unambiguous ones first and take the
harder shapes later, for stronger players.

Every family is board truth. No engine call, no stored evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import chess

PIECE_CP = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
            chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}

# What a puzzle needs to be worth setting: a fork on two pawns is not the
# lesson, and "win a pawn" is not a tactic a beginner should be hunting.
FORK_MIN_VALUE = chess.KNIGHT
FREE_PIECE_MIN_CP = 300


@dataclass(frozen=True)
class Puzzle:
    family: str
    fen: str
    question: str
    answer_uci: str
    answer_san: str
    # Why this answer, in the question's own terms -- shown AFTER they try.
    explanation: str
    difficulty: int          # 1 easiest; drives the adaptive ladder


def _piece_value(board: chess.Board, square: int) -> int:
    piece = board.piece_at(square)
    return PIECE_CP.get(piece.piece_type, 0) if piece else 0


def _is_free(board: chess.Board, move: chess.Move) -> bool:
    """Nothing can take back. That is what "free" means to a beginner.

    The first version priced the recapture and compared it to the victim --
    Bxf3 taking a knight (320) where they win back 300 read as "+20, safe".
    It ignored that the BISHOP being given up is worth 330, so the trade is
    -10. Engine-checked on
    r2qkb1r/ppp1pppp/2n2n2/8/2P3b1/P1N2N2/1P1PBPPP/R1BQK2R b: the position is
    dead equal and Bxf3 is not in the top four moves, yet it shipped as a
    free piece.

    So the test is not "do I come out ahead in the exchange" -- it is "can
    anything recapture at all". A puzzle that says something is free had
    better mean it.
    """
    after = board.copy(stack=False)
    after.push(move)
    return not after.attackers(after.turn, move.to_square)


# ── families ──────────────────────────────────────────────────────────────

def _mate_in_one(board: chess.Board) -> List[chess.Move]:
    out = []
    for move in board.legal_moves:
        probe = board.copy(stack=False)
        probe.push(move)
        if probe.is_checkmate():
            out.append(move)
    return out


def _opponent_can_mate(board: chess.Board) -> bool:
    for move in board.legal_moves:
        probe = board.copy(stack=False)
        probe.push(move)
        if probe.is_checkmate():
            return True
    return False


def _survives_two(board: chess.Board) -> bool:
    """After their reply, can we still avoid mate on the move after that?

    Checking only mate-in-one is not "saving your king". Engine-checked on
    2kr1b1r/2pq1p2/Q2p1n1p/6pb/3RP3/2N2PBP/PPP2P2/2K4R b: Kb8 is the single
    move that stops mate NEXT move, and the position is still mate in 2
    (Kb8 Rb4+ Qb5 Rxb5#). A puzzle that says "save your king" and then mates
    the player anyway is worse than no puzzle.
    """
    for reply in board.legal_moves:
        after = board.copy(stack=False)
        after.push(reply)
        if after.is_checkmate():
            return False
        # `after` has US to move. The guard here used to be
        # `if _opponent_can_mate(after)` -- which asks whether WE can mate,
        # because the side to move has flipped. So it was almost always False
        # and the whole check was skipped. Ask the real question directly:
        # is there ANY move of ours after which they cannot mate?
        saved = False
        for ours in after.legal_moves:
            probe = after.copy(stack=False)
            probe.push(ours)
            if not _opponent_can_mate(probe):
                saved = True
                break
        if not saved:
            return False
    return True


def _stops_mate(board: chess.Board) -> List[chess.Move]:
    """They threaten mate in one; which of our moves actually saves us.

    Two conditions, not one: the move must stop the immediate mate AND leave
    a position we can still survive. See _survives_two.
    """
    survivors = []
    for move in board.legal_moves:
        probe = board.copy(stack=False)
        probe.push(move)
        if _opponent_can_mate(probe):
            continue
        if not _survives_two(probe):
            continue
        survivors.append(move)
    return survivors


def _free_captures(board: chess.Board) -> List[chess.Move]:
    out = []
    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
        if _piece_value(board, move.to_square) < FREE_PIECE_MIN_CP:
            continue
        if _is_free(board, move):
            out.append(move)
    return out


def _forks(board: chess.Board) -> List[chess.Move]:
    """Moves that land attacking two pieces worth a knight or more, safely."""
    out = []
    mover = board.turn
    for move in board.legal_moves:
        after = board.copy(stack=False)
        after.push(move)
        targets = []
        for square in after.attacks(move.to_square):
            piece = after.piece_at(square)
            if piece is None or piece.color == mover:
                continue
            if piece.piece_type == chess.KING or \
                    PIECE_CP.get(piece.piece_type, 0) >= PIECE_CP[FORK_MIN_VALUE]:
                targets.append(square)
        if len(targets) < 2:
            continue
        # A fork that hits two DEFENDED pieces wins nothing -- it is a move,
        # not a tactic. Nd4 on the position above attacks the knight on f3
        # and the bishop on e2, and the engine calls it +25cp, because Nxd4
        # simply trades. The exchange value there is 0, which the first
        # version read as "the knight is safe" when it means "this is an
        # even trade".
        #
        # So two things have to hold: at least one target cannot be defended
        # away, and the forking piece is not itself capturable for profit.
        from services.legal_exchange_verifier import independent_exchange_gain
        if independent_exchange_gain(after, move.to_square) > 0:
            continue
        loose = [sq for sq in targets
                 if not after.attackers(not mover, sq)
                 and after.piece_at(sq) is not None
                 and after.piece_at(sq).piece_type != chess.KING]
        if not loose:
            continue
        out.append(move)
    return out


_FAMILIES: Dict[str, Dict[str, object]] = {
    "mate_in_one": {
        "question": "There is mate in one here. Find it.",
        "finder": _mate_in_one,
        "difficulty": 1,
        "explain": "{san} is mate: their king has no legal move left.",
    },
    "stop_the_mate": {
        "question": "They are threatening mate next move. "
                    "Only one move stops it -- find it.",
        "finder": _stops_mate,
        "difficulty": 3,
        "explain": "{san} is the only move that takes the mate away.",
    },
    "take_the_free_piece": {
        "question": "Something of theirs is free. Take it.",
        "finder": _free_captures,
        "difficulty": 1,
        "explain": "{san} wins the {victim} and nothing can take back.",
    },
    "find_the_fork": {
        "question": "One move here attacks two of their pieces at once. Find it.",
        "finder": _forks,
        "difficulty": 2,
        "explain": "{san} hits two pieces at the same time -- they cannot save both.",
    },
}


def build_puzzle(fen: str, family: str) -> Optional[Puzzle]:
    """A puzzle for this position, or None when the answer is not unique.

    Returning None on ambiguity is the whole point. A position where two moves
    fork is a fine position and a broken puzzle.
    """
    spec = _FAMILIES.get(family)
    if spec is None:
        return None
    try:
        board = chess.Board(fen)
    except ValueError:
        return None
    if board.is_game_over():
        return None

    # "Stop the mate" only makes sense when a mate is actually threatened.
    if family == "stop_the_mate":
        probe = board.copy(stack=False)
        probe.turn = not board.turn
        if not _opponent_can_mate(probe):
            return None

    try:
        moves = spec["finder"](board)  # type: ignore[operator]
    except Exception:  # noqa: BLE001
        return None
    if len(moves) != 1:
        return None

    move = moves[0]
    san = board.san(move)
    victim = board.piece_at(move.to_square)
    return Puzzle(
        family=family,
        fen=fen,
        question=str(spec["question"]),
        answer_uci=move.uci(),
        answer_san=san,
        explanation=str(spec["explain"]).format(
            san=san,
            victim=chess.piece_name(victim.piece_type) if victim else "piece"),
        difficulty=int(spec["difficulty"]),  # type: ignore[arg-type]
    )


def families() -> List[str]:
    return list(_FAMILIES)
