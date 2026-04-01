"""
Position Reader — Teaches players HOW TO READ A BOARD
======================================================

Looks at a FEN and returns the 2-3 most important things to notice,
adapted to the player's rating.

800-1000: Basic safety — hanging pieces, king safety, development
1000-1200: + Open files, piece activity, center control
1200-1400: + Pawn structure, pins, weak squares
1400-1600: + Prophylaxis, piece coordination, long-term plans

Not what to PLAY — what to SEE.
"""

import chess
import logging
from typing import Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PositionFeature:
    priority: int       # Lower = more important
    category: str       # "king_safety", "tactics", "piece_activity", "pawn_structure", "development"
    title: str          # Short label
    description: str    # What to notice
    min_rating: int     # Don't show below this rating
    actionable: str     # What to do about it


def read_position(fen: str, user_color: str = "white", user_rating: int = 1200) -> Dict:
    """
    Read a position and return the most important features for this player's level.
    """
    try:
        board = chess.Board(fen)
    except Exception:
        return {"features": [], "eval_text": "Invalid position"}

    user_is_white = user_color == "white"
    user_color_bool = chess.WHITE if user_is_white else chess.BLACK
    opp_color_bool = not user_color_bool

    features = []

    # ─── KING SAFETY (all levels) ───
    features.extend(_analyze_king_safety(board, user_color_bool, opp_color_bool))

    # ─── HANGING PIECES (all levels) ───
    features.extend(_analyze_hanging_pieces(board, user_color_bool, opp_color_bool))

    # ─── DEVELOPMENT (800+) ───
    features.extend(_analyze_development(board, user_color_bool))

    # ─── OPEN FILES (1000+) ───
    features.extend(_analyze_open_files(board, user_color_bool))

    # ─── PIECE ACTIVITY (1000+) ───
    features.extend(_analyze_piece_activity(board, user_color_bool, opp_color_bool))

    # ─── CENTER CONTROL (1000+) ───
    features.extend(_analyze_center(board, user_color_bool))

    # ─── PAWN STRUCTURE (1200+) ───
    features.extend(_analyze_pawn_structure(board, user_color_bool))

    # ─── PINS (1200+) ───
    features.extend(_analyze_pins(board, user_color_bool, opp_color_bool))

    # ─── CHECKS AVAILABLE (all levels) ───
    features.extend(_analyze_checks(board, user_color_bool))

    # Filter by rating
    filtered = [f for f in features if f.min_rating <= user_rating]

    # Sort by priority, take top 3
    filtered.sort(key=lambda f: f.priority)
    top = filtered[:3]

    # Who's better (simple material count)
    eval_text = _get_eval_text(board, user_color_bool)

    # Game phase
    phase = _get_phase(board)

    return {
        "features": [
            {
                "category": f.category,
                "title": f.title,
                "description": f.description,
                "actionable": f.actionable,
            }
            for f in top
        ],
        "eval_text": eval_text,
        "phase": phase,
    }


# ─── ANALYZERS ───────────────────────────────────────────────

def _analyze_king_safety(board, user_color, opp_color) -> List[PositionFeature]:
    features = []

    # Opponent's king analysis
    opp_king_sq = board.king(opp_color)
    if opp_king_sq is not None:
        opp_castled = _is_castled(board, opp_color, opp_king_sq)
        opp_pawn_shield = _has_pawn_shield(board, opp_color, opp_king_sq)
        
        if not opp_castled:
            # King in the center — genuinely exposed
            king_name = chess.square_name(opp_king_sq)
            escape_squares = _count_escape_squares(board, opp_color, opp_king_sq, user_color)
            
            if len(escape_squares) <= 1:
                features.append(PositionFeature(
                    priority=1,
                    category="king_safety",
                    title="Opponent's king hasn't castled",
                    description=f"Their king is stuck on {king_name} with {'only 1 escape: ' + escape_squares[0] if escape_squares else 'almost no escape squares'}. It's vulnerable in the center.",
                    min_rating=800,
                    actionable="Open the center! An uncastled king hates open lines. Look for checks.",
                ))
            elif board.fullmove_number >= 8:
                features.append(PositionFeature(
                    priority=3,
                    category="king_safety",
                    title="Opponent still hasn't castled",
                    description=f"Their king is still on {king_name} after {board.fullmove_number} moves. This is a target.",
                    min_rating=800,
                    actionable="Open the center and look for checks. Their king is uncomfortable.",
                ))
        elif opp_castled and not opp_pawn_shield:
            # Castled but pawn shield is broken
            king_name = chess.square_name(opp_king_sq)
            features.append(PositionFeature(
                priority=2,
                category="king_safety",
                title="Opponent's pawn shield is broken",
                description=f"Their king castled but the pawns in front are damaged. This creates attack opportunities.",
                min_rating=1000,
                actionable="Look for ways to open lines toward their king. A broken pawn shield = attacking chances.",
            ))

    # User's own king — only warn if genuinely exposed
    user_king_sq = board.king(user_color)
    if user_king_sq is not None:
        user_castled = _is_castled(board, user_color, user_king_sq)
        
        if not user_castled and board.fullmove_number >= 8:
            features.append(PositionFeature(
                priority=2,
                category="king_safety",
                title="Your king hasn't castled yet",
                description=f"It's move {board.fullmove_number} and your king is still in the center. Castle soon.",
                min_rating=800,
                actionable="Castle as soon as possible. Your king is not safe in the center.",
            ))

    return features


def _is_castled(board, color, king_sq) -> bool:
    """Check if king is in a castled position."""
    file_idx = chess.square_file(king_sq)
    rank_idx = chess.square_rank(king_sq)
    
    expected_rank = 0 if color == chess.WHITE else 7
    if rank_idx != expected_rank:
        return False  # King moved off back rank — could be castled or not
    
    # Kingside castle: king on g1/g8
    if file_idx == 6:
        return True
    # Queenside castle: king on c1/c8
    if file_idx == 2:
        return True
    # King still on e-file: hasn't castled
    if file_idx == 4:
        return False
    # King on h-file (rare but possible after castling + moves)
    if file_idx in [5, 6, 7]:
        return True
    
    return False


def _has_pawn_shield(board, color, king_sq) -> bool:
    """Check if castled king has intact pawn shield."""
    file_idx = chess.square_file(king_sq)
    rank_idx = chess.square_rank(king_sq)
    
    pawn_rank = rank_idx + (1 if color == chess.WHITE else -1)
    if pawn_rank < 0 or pawn_rank > 7:
        return False
    
    # Check pawns on the 3 files around the king
    shield_files = [max(0, file_idx - 1), file_idx, min(7, file_idx + 1)]
    pawns_present = 0
    
    for f in shield_files:
        sq = chess.square(f, pawn_rank)
        piece = board.piece_at(sq)
        if piece and piece.piece_type == chess.PAWN and piece.color == color:
            pawns_present += 1
    
    return pawns_present >= 2  # At least 2 of 3 shield pawns intact


def _count_escape_squares(board, king_color, king_sq, attacker_color) -> List[str]:
    """Count safe escape squares for a king."""
    escapes = []
    for sq in chess.SQUARES:
        if chess.square_distance(king_sq, sq) == 1:
            piece = board.piece_at(sq)
            if piece is None or piece.color != king_color:
                if not board.is_attacked_by(attacker_color, sq):
                    escapes.append(chess.square_name(sq))
    return escapes


def _analyze_hanging_pieces(board, user_color, opp_color) -> List[PositionFeature]:
    features = []

    # Opponent's undefended pieces (opportunities)
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == opp_color and piece.piece_type != chess.KING:
            attacked_by_us = board.is_attacked_by(user_color, sq)
            defended = board.is_attacked_by(opp_color, sq)
            if attacked_by_us and not defended:
                piece_name = chess.piece_name(piece.piece_type)
                sq_name = chess.square_name(sq)
                features.append(PositionFeature(
                    priority=1,
                    category="tactics",
                    title=f"Opponent's {piece_name} is undefended",
                    description=f"Their {piece_name} on {sq_name} has no defender and you're attacking it. Can you take it?",
                    min_rating=800,
                    actionable=f"Look at {sq_name}. Can you capture that {piece_name} safely?",
                ))
                break  # Only show the most important one

    # Your undefended pieces (dangers)
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type != chess.KING:
            attacked = board.is_attacked_by(opp_color, sq)
            defended = board.is_attacked_by(user_color, sq)
            if attacked and not defended:
                piece_name = chess.piece_name(piece.piece_type)
                sq_name = chess.square_name(sq)
                features.append(PositionFeature(
                    priority=2,
                    category="tactics",
                    title=f"Your {piece_name} is hanging",
                    description=f"Your {piece_name} on {sq_name} is attacked and has no defender. Move it or defend it.",
                    min_rating=800,
                    actionable=f"Save your {piece_name} on {sq_name} before doing anything else.",
                ))
                break

    return features


def _analyze_development(board, user_color) -> List[PositionFeature]:
    features = []
    back_rank = 0 if user_color == chess.WHITE else 7

    undeveloped = []
    for sq in chess.SQUARES:
        if chess.square_rank(sq) != back_rank:
            continue
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
            undeveloped.append(chess.piece_name(piece.piece_type) + " on " + chess.square_name(sq))

    if len(undeveloped) >= 2 and board.fullmove_number <= 15:
        features.append(PositionFeature(
            priority=4,
            category="development",
            title=f"{len(undeveloped)} pieces still on back rank",
            description=f"Your {' and '.join(undeveloped[:2])} haven't moved yet. Get them into the game.",
            min_rating=800,
            actionable="Develop a piece. Every piece sitting at home is a piece not helping.",
        ))

    return features


def _analyze_open_files(board, user_color) -> List[PositionFeature]:
    features = []

    for file_idx in range(8):
        has_white_pawn = False
        has_black_pawn = False
        for rank_idx in range(8):
            sq = chess.square(file_idx, rank_idx)
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN:
                if piece.color == chess.WHITE:
                    has_white_pawn = True
                else:
                    has_black_pawn = True

        if not has_white_pawn and not has_black_pawn:
            file_letter = chr(97 + file_idx)
            # Check if our rook is on this file
            our_rook_on_file = False
            for rank_idx in range(8):
                sq = chess.square(file_idx, rank_idx)
                piece = board.piece_at(sq)
                if piece and piece.color == user_color and piece.piece_type == chess.ROOK:
                    our_rook_on_file = True

            if not our_rook_on_file:
                features.append(PositionFeature(
                    priority=6,
                    category="piece_activity",
                    title=f"Open {file_letter}-file — no rook there",
                    description=f"The {file_letter}-file is wide open (no pawns). Your rook should be on it.",
                    min_rating=1000,
                    actionable=f"Put a rook on {file_letter}1 (or {file_letter}8). Rooks love open files.",
                ))
                break  # One is enough

    return features


def _analyze_piece_activity(board, user_color, opp_color) -> List[PositionFeature]:
    features = []

    # Knights on the rim
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type == chess.KNIGHT:
            file_idx = chess.square_file(sq)
            rank_idx = chess.square_rank(sq)
            if file_idx in [0, 7] or rank_idx in [0, 7]:
                features.append(PositionFeature(
                    priority=7,
                    category="piece_activity",
                    title=f"Knight on the rim ({chess.square_name(sq)})",
                    description=f"Your knight on {chess.square_name(sq)} is on the edge. Knights are strongest in the center where they control more squares.",
                    min_rating=800,
                    actionable="Move this knight toward the center. A knight on the rim is dim.",
                ))
                break

    # Opponent's passive pieces
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == opp_color and piece.piece_type == chess.KNIGHT:
            file_idx = chess.square_file(sq)
            rank_idx = chess.square_rank(sq)
            if file_idx in [0, 7] or rank_idx in [0, 7]:
                features.append(PositionFeature(
                    priority=8,
                    category="piece_activity",
                    title=f"Opponent's knight is stuck ({chess.square_name(sq)})",
                    description=f"Their knight on {chess.square_name(sq)} is on the edge and not doing much. You have more active pieces.",
                    min_rating=1000,
                    actionable="Your pieces are better placed. Use that advantage — don't let them reposition.",
                ))
                break

    return features


def _analyze_center(board, user_color) -> List[PositionFeature]:
    features = []
    center_squares = [chess.E4, chess.D4, chess.E5, chess.D5]

    user_center = 0
    opp_center = 0
    for sq in center_squares:
        piece = board.piece_at(sq)
        if piece:
            if piece.color == user_color:
                user_center += 1
            else:
                opp_center += 1

    if user_center >= 2 and opp_center == 0:
        features.append(PositionFeature(
            priority=9,
            category="center",
            title="You control the center",
            description="You have pieces in the center and your opponent doesn't. This gives your pieces more room to move.",
            min_rating=1000,
            actionable="Use your center control. Your pieces can reach both sides of the board faster.",
        ))
    elif opp_center >= 2 and user_center == 0:
        features.append(PositionFeature(
            priority=5,
            category="center",
            title="Opponent controls the center",
            description="They have more presence in the center. Your pieces are cramped.",
            min_rating=1000,
            actionable="Challenge the center with a pawn push (c5, d5, e5, or f5) when possible.",
        ))

    return features


def _analyze_pawn_structure(board, user_color) -> List[PositionFeature]:
    features = []

    # Passed pawns
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type == chess.PAWN:
            file_idx = chess.square_file(sq)
            rank_idx = chess.square_rank(sq)
            is_passed = True
            direction = 1 if user_color == chess.WHITE else -1

            for check_rank in range(rank_idx + direction, 8 if direction == 1 else -1, direction):
                for check_file in [file_idx - 1, file_idx, file_idx + 1]:
                    if 0 <= check_file <= 7:
                        check_sq = chess.square(check_file, check_rank)
                        check_piece = board.piece_at(check_sq)
                        if check_piece and check_piece.piece_type == chess.PAWN and check_piece.color != user_color:
                            is_passed = False
                            break
                if not is_passed:
                    break

            if is_passed and ((user_color == chess.WHITE and rank_idx >= 4) or (user_color == chess.BLACK and rank_idx <= 3)):
                features.append(PositionFeature(
                    priority=5,
                    category="pawn_structure",
                    title=f"Passed pawn on {chess.square_name(sq)}",
                    description=f"Your pawn on {chess.square_name(sq)} has no enemy pawns blocking it. It can march to promotion.",
                    min_rating=1200,
                    actionable="Push this pawn! Passed pawns must be pushed. Support it with your pieces.",
                ))
                break

    return features


def _analyze_pins(board, user_color, opp_color) -> List[PositionFeature]:
    features = []

    # Check if any opponent piece is pinned to their king
    opp_king = board.king(opp_color)
    if opp_king is None:
        return features

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == opp_color and piece.piece_type != chess.KING:
            if board.is_pinned(opp_color, sq):
                piece_name = chess.piece_name(piece.piece_type)
                sq_name = chess.square_name(sq)
                features.append(PositionFeature(
                    priority=3,
                    category="tactics",
                    title=f"Opponent's {piece_name} is pinned",
                    description=f"Their {piece_name} on {sq_name} is pinned to their king. It can't move without exposing the king.",
                    min_rating=1200,
                    actionable=f"A pinned piece is a weak piece. Can you pile up on {sq_name} with another attacker?",
                ))
                break

    return features


def _analyze_checks(board, user_color) -> List[PositionFeature]:
    features = []

    if board.turn != user_color:
        return features

    # Count available checks
    checks = []
    for move in board.legal_moves:
        board.push(move)
        if board.is_check():
            checks.append(move)
        board.pop()

    if len(checks) >= 2:
        check_sans = [board.san(m) for m in checks[:3]]
        features.append(PositionFeature(
            priority=4,
            category="tactics",
            title=f"{len(checks)} checks available",
            description=f"You can give check with: {', '.join(check_sans)}. Always consider checks — they force the opponent to respond.",
            min_rating=800,
            actionable="Check each check: does it lead to something good? A check that wins material or improves position is powerful.",
        ))

    return features


# ─── HELPERS ────────────────────────────────────────────────

def _get_eval_text(board, user_color) -> str:
    """Simple material-based evaluation."""
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    white_material = sum(values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.WHITE)
    black_material = sum(values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.BLACK)

    user_material = white_material if user_color == chess.WHITE else black_material
    opp_material = black_material if user_color == chess.WHITE else white_material
    diff = user_material - opp_material

    if diff >= 5:
        return "You're winning — up significant material."
    elif diff >= 3:
        return "You're up a piece. Convert carefully."
    elif diff >= 1:
        return "You're up a pawn. Small edge."
    elif diff <= -5:
        return "You're down big. Look for tricks."
    elif diff <= -3:
        return "You're down a piece. Need to fight back."
    elif diff <= -1:
        return "You're down a pawn. Stay solid."
    return "Material is equal."


def _get_phase(board) -> str:
    pieces = len(board.piece_map())
    if pieces >= 28:
        return "opening"
    elif pieces >= 14:
        return "middlegame"
    return "endgame"
