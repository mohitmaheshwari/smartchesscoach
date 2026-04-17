"""
Candidate Generator — get safe candidate moves from Stockfish.

Queries engine for top moves, applies soft eval filter.
Does NOT restrict to top 3 — teaching value may be in the 5th or 6th best move.
"""

import chess
import chess.engine
import logging
from typing import List, Optional

from .types import CandidateMove

logger = logging.getLogger(__name__)


def generate_candidates(
    board: chess.Board,
    engine: chess.engine.SimpleEngine,
    max_candidates: int = 8,
    max_eval_drop_cp: int = 150,
    depth: int = 10,
    teaching_mode: bool = False,
) -> List[CandidateMove]:
    """
    Generate candidate moves using Stockfish multipv analysis.

    Args:
        board: Current position
        engine: Running Stockfish engine instance
        max_candidates: How many top moves to consider (default 8)
        max_eval_drop_cp: Soft cap — moves worse than this get generated
                          but will be penalized by the scoring system.
                          Set high (150) so scoring decides, not filtering.
        depth: Engine analysis depth
        teaching_mode: If True, widen the search to find moves that create
                       tactical patterns for the student (15 moves, 250cp range).
                       Perfect moves don't create opportunities — the coach
                       needs to play "good but not perfect" moves sometimes.

    Returns:
        List of CandidateMove sorted by engine evaluation (best first).
        Moves that hang material are excluded entirely.
    """
    if teaching_mode:
        max_candidates = max(max_candidates, 15)
        max_eval_drop_cp = max(max_eval_drop_cp, 250)
    candidates = []

    try:
        result = engine.analyse(
            board,
            chess.engine.Limit(depth=depth),
            multipv=max_candidates,
        )
    except Exception as e:
        logger.error(f"Engine analysis failed: {e}")
        # Fallback: return first few legal moves with no eval data
        for i, move in enumerate(list(board.legal_moves)[:3]):
            candidates.append(CandidateMove(
                move=move,
                san=board.san(move),
                eval_cp=0,
                eval_rank=i + 1,
            ))
        return candidates

    best_eval = None
    MIN_CANDIDATES = 4  # Always keep at least this many for teaching variety

    for i, info in enumerate(result):
        if "pv" not in info or not info["pv"]:
            continue

        move = info["pv"][0]
        pv = info["pv"]

        # Extract eval in centipawns
        score = info.get("score", chess.engine.Cp(0))
        if score.is_mate():
            eval_cp = 10000 if score.relative.score(mate_score=10000) > 0 else -10000
        else:
            eval_cp = score.relative.score(mate_score=10000)

        if best_eval is None:
            best_eval = eval_cp

        # Hard filter: never play a move that hangs a piece
        if _hangs_piece(board, move):
            continue

        # Soft filter: keep moves within max_eval_drop_cp of best
        # BUT always keep at least MIN_CANDIDATES for teaching variety
        eval_drop = best_eval - eval_cp
        if eval_drop > max_eval_drop_cp and len(candidates) >= MIN_CANDIDATES:
            continue

        candidates.append(CandidateMove(
            move=move,
            san=board.san(move),
            eval_cp=eval_cp,
            eval_rank=i + 1,
            pv=pv,
        ))

    return candidates


def _hangs_piece(board: chess.Board, move: chess.Move) -> bool:
    """
    Check if a move leaves our own piece undefended and attacked.
    The coach should NEVER play a move that blunders material.
    """
    board.push(move)
    our_color = not board.turn  # We just moved

    hangs = False
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != our_color:
            continue
        if piece.piece_type in (chess.PAWN, chess.KING):
            continue

        attackers = list(board.attackers(board.turn, sq))
        if not attackers:
            continue
        defenders = list(board.attackers(our_color, sq))

        if len(defenders) == 0:
            # Undefended and attacked
            hangs = True
            break
        elif len(attackers) > len(defenders):
            # More attackers than defenders — may lose material
            cheapest_attacker_val = min(
                (_piece_val(board, a) for a in attackers),
                default=99,
            )
            piece_val = _piece_val_type(piece.piece_type)
            if cheapest_attacker_val < piece_val:
                hangs = True
                break

    board.pop()
    return hangs


def _piece_val(board: chess.Board, sq: int) -> int:
    p = board.piece_at(sq)
    if not p:
        return 99
    return _piece_val_type(p.piece_type)


def _piece_val_type(pt: int) -> int:
    return {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
            chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}.get(pt, 0)
