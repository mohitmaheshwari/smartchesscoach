"""
Golden Rule Service
====================

Injects phase-specific chess wisdom into move coaching.
Not generic advice — specific to the position type and opening/endgame.

Sources:
  OPENING  → opening_theory_tree_service + position_teaching_service
  MIDDLE   → position_reader + piece_metrics (board-specific)
  ENDGAME  → endgame_teaching + pawn_structure_service

Each golden rule is:
  - One sentence a player can remember
  - Specific to THIS position or opening, not generic
  - Actionable ("do this") not descriptive ("this happened")
"""

import chess
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


def get_golden_rule(
    board: chess.Board,
    move: chess.Move,
    phase: str,
    severity: str,
    cp_loss: int,
    eco_code: str = None,
    opening_name: str = None,
    best_move_san: str = None,
    concept_type: str = None,
) -> Optional[Dict]:
    """
    Get a golden rule for a mistake move based on game phase.

    Returns:
    {
        "rule": "In the Italian, push d4 while you can — it controls the center.",
        "source": "opening_theory",
        "category": "opening" | "tactical" | "positional" | "endgame",
    }
    """
    if severity not in ("inaccuracy", "mistake", "blunder"):
        return None

    if phase == "opening":
        return _get_opening_rule(board, move, eco_code, opening_name, best_move_san, cp_loss)
    elif phase == "endgame":
        return _get_endgame_rule(board, move, best_move_san, cp_loss)
    else:
        return _get_middlegame_rule(board, move, best_move_san, cp_loss, concept_type)


def _get_opening_rule(board, move, eco_code, opening_name, best_move, cp_loss) -> Optional[Dict]:
    """Pull golden rule from opening theory."""

    # Try opening theory tree first
    try:
        from services.opening_theory_tree_service import get_mistake_from_theory
        move_san = board.san(move)
        theory = get_mistake_from_theory(eco_code, move_san, board.fen())
        if theory and theory.get("learning"):
            return {
                "rule": theory["learning"],
                "source": "opening_theory",
                "category": "opening",
            }
    except Exception:
        pass

    # Try position teaching service
    try:
        from services.position_teaching_service import OPENING_EXPLANATIONS
        if opening_name:
            for key, data in OPENING_EXPLANATIONS.items():
                if key.lower() in opening_name.lower() or opening_name.lower() in key.lower():
                    if data.get("strategic_idea"):
                        return {
                            "rule": data["strategic_idea"],
                            "source": "opening_teaching",
                            "category": "opening",
                        }
    except Exception:
        pass

    # General opening principles based on what went wrong
    move_san = board.san(move)
    piece = board.piece_at(move.from_square)

    # Detect common opening mistakes
    move_number = board.fullmove_number

    # Moving same piece twice in opening
    if piece and move_number <= 10:
        # Check if this piece already moved
        # (approximation: if it's not on a starting square, it moved before)
        STARTING = {
            chess.KNIGHT: {chess.B1, chess.G1, chess.B8, chess.G8},
            chess.BISHOP: {chess.C1, chess.F1, chess.C8, chess.F8},
            chess.QUEEN: {chess.D1, chess.D8},
        }
        starts = STARTING.get(piece.piece_type, set())
        if piece.piece_type == chess.QUEEN and move_number <= 6:
            return {
                "rule": "Don't bring your queen out early — it becomes a target and wastes time.",
                "source": "opening_principle",
                "category": "opening",
            }

    # Not castled by move 10
    user_color = board.turn
    if move_number >= 8 and not _is_castled(board, user_color):
        if piece and piece.piece_type != chess.KING:
            return {
                "rule": "Castle early to protect your king. Every move you delay is a risk.",
                "source": "opening_principle",
                "category": "opening",
            }

    # Pawn move on the side instead of center
    if piece and piece.piece_type == chess.PAWN:
        to_file = chess.square_file(move.to_square)
        if to_file in (0, 1, 6, 7) and move_number <= 8:
            return {
                "rule": "In the opening, fight for the center first. Side pawn moves can wait.",
                "source": "opening_principle",
                "category": "opening",
            }

    # Generic opening fallback
    if move_number <= 12:
        return {
            "rule": "Opening priority: develop pieces, control the center, castle. In that order.",
            "source": "opening_principle",
            "category": "opening",
        }

    return None


def _get_middlegame_rule(board, move, best_move, cp_loss, concept_type) -> Optional[Dict]:
    """Pull golden rule from board reading."""

    piece = board.piece_at(move.from_square)
    if not piece:
        return None

    move_san = board.san(move)
    user_color = board.turn
    NAMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
             chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}

    # Detect WHAT went wrong based on position features

    # 1. Piece moved to a bad square (rim, passive)
    to_file = chess.square_file(move.to_square)
    to_rank = chess.square_rank(move.to_square)
    if piece.piece_type == chess.KNIGHT and (to_file in (0, 7) or to_rank in (0, 7)):
        return {
            "rule": "Knights are strongest in the center. On the edge, they control half the squares.",
            "source": "positional",
            "category": "positional",
        }

    # 2. Left a piece undefended
    sim = board.copy()
    sim.push(move)
    for sq in chess.SQUARES:
        p = sim.piece_at(sq)
        if p and p.color == user_color and p.piece_type not in (chess.PAWN, chess.KING):
            attackers = list(sim.attackers(not user_color, sq))
            defenders = list(sim.attackers(user_color, sq))
            if attackers and not defenders:
                pname = NAMES.get(p.piece_type, "piece")
                return {
                    "rule": f"After every move, check: did I leave a piece undefended? Your {pname} is hanging.",
                    "source": "piece_safety",
                    "category": "tactical",
                }

    # 3. King safety issue
    king_sq = board.king(user_color)
    if king_sq:
        king_attackers = len(list(sim.attackers(not user_color, king_sq)))
        if king_attackers >= 2:
            return {
                "rule": "Your king is under attack. Defend it before doing anything else.",
                "source": "king_safety",
                "category": "tactical",
            }

    # 4. Missed a capture/tactic
    if best_move:
        try:
            best_obj = board.parse_san(best_move)
            if board.is_capture(best_obj) and not board.is_capture(move):
                captured = board.piece_at(best_obj.to_square)
                if captured:
                    return {
                        "rule": "Before choosing your move, always check: is there a capture that wins material?",
                        "source": "tactical",
                        "category": "tactical",
                    }
        except Exception:
            pass

    # 5. Concept-type based rules
    CONCEPT_RULES = {
        "tactical": "Before every move: check captures, checks, and threats — in that order.",
        "positional": "Ask yourself: which of my pieces is doing the least? Improve that piece.",
        "opening": "In the opening: develop, control center, castle.",
    }
    if concept_type and concept_type in CONCEPT_RULES:
        return {
            "rule": CONCEPT_RULES[concept_type],
            "source": "concept",
            "category": concept_type,
        }

    # Generic middlegame
    if cp_loss >= 200:
        return {
            "rule": "Before every move, ask: what can my opponent do after this?",
            "source": "calculation",
            "category": "tactical",
        }

    return None


def _get_endgame_rule(board, move, best_move, cp_loss) -> Optional[Dict]:
    """Pull golden rule from endgame principles."""

    piece = board.piece_at(move.from_square)
    user_color = board.turn

    # Try endgame teaching service
    try:
        from services.endgame_teaching import get_endgame_principles
        principles = get_endgame_principles()
        if principles:
            # Match based on piece types remaining
            pieces_on_board = {}
            for sq in chess.SQUARES:
                p = board.piece_at(sq)
                if p and p.piece_type != chess.KING:
                    key = ("w" if p.color == chess.WHITE else "b") + chess.piece_name(p.piece_type)
                    pieces_on_board[key] = pieces_on_board.get(key, 0) + 1

            for principle in principles:
                if principle.get("rule"):
                    return {
                        "rule": principle["rule"],
                        "source": "endgame_teaching",
                        "category": "endgame",
                    }
    except Exception:
        pass

    # King activity
    king_sq = board.king(user_color)
    if king_sq:
        king_file = chess.square_file(king_sq)
        king_rank = chess.square_rank(king_sq)
        # King still on back rank in endgame
        back_rank = 0 if user_color == chess.WHITE else 7
        if king_rank == back_rank:
            return {
                "rule": "In the endgame, your king is a fighting piece. Walk it toward the center.",
                "source": "endgame_principle",
                "category": "endgame",
            }

    # Passed pawn not being pushed
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == user_color and p.piece_type == chess.PAWN:
            if _is_passed_pawn(board, sq, user_color):
                return {
                    "rule": "You have a passed pawn. Push it! Passed pawns must be pushed — they become queens.",
                    "source": "endgame_principle",
                    "category": "endgame",
                }

    # Rook endgame
    rook_count = sum(1 for sq in chess.SQUARES if board.piece_at(sq) and board.piece_at(sq).piece_type == chess.ROOK)
    if rook_count >= 2:
        return {
            "rule": "In rook endgames, keep your rook active. Rooks belong behind passed pawns — yours or theirs.",
            "source": "endgame_principle",
            "category": "endgame",
        }

    # Generic endgame
    return {
        "rule": "Endgame priority: activate your king, create a passed pawn, push it forward.",
        "source": "endgame_principle",
        "category": "endgame",
    }


def _is_castled(board, color):
    king_sq = board.king(color)
    if not king_sq:
        return False
    file_idx = chess.square_file(king_sq)
    rank_idx = chess.square_rank(king_sq)
    expected_rank = 0 if color == chess.WHITE else 7
    if rank_idx != expected_rank:
        return False
    return file_idx in (2, 6)  # c1/g1 or c8/g8


def _is_passed_pawn(board, sq, color):
    file_idx = chess.square_file(sq)
    rank_idx = chess.square_rank(sq)
    direction = 1 if color == chess.WHITE else -1
    for check_rank in range(rank_idx + direction, 8 if direction == 1 else -1, direction):
        for check_file in [file_idx - 1, file_idx, file_idx + 1]:
            if 0 <= check_file <= 7:
                check_sq = chess.square(check_file, check_rank)
                p = board.piece_at(check_sq)
                if p and p.piece_type == chess.PAWN and p.color != color:
                    return False
    return True
