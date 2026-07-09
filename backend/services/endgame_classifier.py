"""
Endgame position classifier — identify position type and key features.

Classifies positions into endgame categories and extracts features
needed for principle-based coaching (rule of square, critical pieces, threats).

Examples:
  - K+R vs K+P: King+Rook vs King+Pawn
  - R+P vs R: Rook+Pawn vs Rook
  - K+P vs K: King+Pawn vs King (opposition matters)
"""

import chess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class EndgameInfo:
    """Classification result"""
    position_type: str  # e.g., "K+R vs K+P", "R+P vs R", "K+P vs K"
    material_white: List[str]  # Pieces White has
    material_black: List[str]  # Pieces Black has
    white_pawns: List[str]  # Pawn positions (e.g., ["e4", "h4"])
    black_pawns: List[str]
    white_king: str  # e.g., "d6"
    black_king: str
    white_rooks: List[str]
    black_rooks: List[str]
    threats: List[str]  # ["black_pawn_a5_can_promote", "white_rook_vulnerable", ...]
    critical_pieces: Dict[str, str]  # {"white_rook": "only_defender", "black_pawn": "promotion_threat"}
    phase: str  # "endgame", "late_middlegame"
    is_theoretical_endgame: bool  # True if matches known endgame pattern


def classify_position(board: chess.Board) -> EndgameInfo:
    """
    Classify position and extract endgame features.

    Returns:
      EndgameInfo with position type, material, threats, critical pieces
    """

    # Count material
    white_material = {
        'queen': len(board.pieces(chess.QUEEN, chess.WHITE)),
        'rook': len(board.pieces(chess.ROOK, chess.WHITE)),
        'bishop': len(board.pieces(chess.BISHOP, chess.WHITE)),
        'knight': len(board.pieces(chess.KNIGHT, chess.WHITE)),
        'pawn': len(board.pieces(chess.PAWN, chess.WHITE)),
    }

    black_material = {
        'queen': len(board.pieces(chess.QUEEN, chess.BLACK)),
        'rook': len(board.pieces(chess.ROOK, chess.BLACK)),
        'bishop': len(board.pieces(chess.BISHOP, chess.BLACK)),
        'knight': len(board.pieces(chess.KNIGHT, chess.BLACK)),
        'pawn': len(board.pieces(chess.PAWN, chess.BLACK)),
    }

    # Get piece positions
    white_king = chess.square_name(board.king(chess.WHITE))
    black_king = chess.square_name(board.king(chess.BLACK))

    white_rooks = [chess.square_name(sq) for sq in board.pieces(chess.ROOK, chess.WHITE)]
    black_rooks = [chess.square_name(sq) for sq in board.pieces(chess.ROOK, chess.BLACK)]

    white_pawns = [chess.square_name(sq) for sq in board.pieces(chess.PAWN, chess.WHITE)]
    black_pawns = [chess.square_name(sq) for sq in board.pieces(chess.PAWN, chess.BLACK)]

    # Classify position type
    position_type = _classify_position_type(white_material, black_material)

    # Extract threats
    threats = _detect_threats(board, white_material, black_material, white_pawns, black_pawns)

    # Identify critical pieces
    critical_pieces = _identify_critical_pieces(
        position_type, white_material, black_material,
        white_pawns, black_pawns, white_rooks, black_rooks, threats
    )

    # Check if it's a theoretical endgame
    is_theoretical = position_type in [
        "K+R vs K+P",
        "R+P vs R",
        "K+P vs K",
        "K+Q vs K",
        "K+R vs K",
        "K+N+B vs K",
    ]

    # Determine phase
    total_pieces = sum(white_material.values()) + sum(black_material.values())
    phase = "endgame" if total_pieces <= 10 else "late_middlegame"

    material_white = []
    if white_material['queen'] > 0:
        material_white.extend(['Q'] * white_material['queen'])
    if white_material['rook'] > 0:
        material_white.extend(['R'] * white_material['rook'])
    if white_material['bishop'] > 0:
        material_white.extend(['B'] * white_material['bishop'])
    if white_material['knight'] > 0:
        material_white.extend(['N'] * white_material['knight'])
    if white_material['pawn'] > 0:
        material_white.extend(['P'] * white_material['pawn'])

    material_black = []
    if black_material['queen'] > 0:
        material_black.extend(['Q'] * black_material['queen'])
    if black_material['rook'] > 0:
        material_black.extend(['R'] * black_material['rook'])
    if black_material['bishop'] > 0:
        material_black.extend(['B'] * black_material['bishop'])
    if black_material['knight'] > 0:
        material_black.extend(['N'] * black_material['knight'])
    if black_material['pawn'] > 0:
        material_black.extend(['P'] * black_material['pawn'])

    return EndgameInfo(
        position_type=position_type,
        material_white=material_white,
        material_black=material_black,
        white_pawns=white_pawns,
        black_pawns=black_pawns,
        white_king=white_king,
        black_king=black_king,
        white_rooks=white_rooks,
        black_rooks=black_rooks,
        threats=threats,
        critical_pieces=critical_pieces,
        phase=phase,
        is_theoretical_endgame=is_theoretical,
    )


def _classify_position_type(white_material: Dict, black_material: Dict) -> str:
    """Classify into endgame category"""
    wq, wr, wb, wn, wp = white_material['queen'], white_material['rook'], white_material['bishop'], white_material['knight'], white_material['pawn']
    bq, br, bb, bn, bp = black_material['queen'], black_material['rook'], black_material['bishop'], black_material['knight'], black_material['pawn']

    # K+R vs K+P
    if wr == 1 and wq == 0 and bq == 0 and br == 0 and bp >= 1:
        return "K+R vs K+P"
    if br == 1 and bq == 0 and wq == 0 and wr == 0 and wp >= 1:
        return "K+R vs K+P"

    # R+P vs R
    if wr >= 1 and wp >= 1 and bq == 0 and br >= 1 and bp == 0:
        return "R+P vs R"
    if br >= 1 and bp >= 1 and wq == 0 and wr >= 1 and wp == 0:
        return "R+P vs R"

    # K+P vs K
    if wq == 0 and wr == 0 and wb == 0 and wn == 0 and wp >= 1 and bq == 0 and br == 0 and bb == 0 and bn == 0 and bp == 0:
        return "K+P vs K"
    if bq == 0 and br == 0 and bb == 0 and bn == 0 and bp >= 1 and wq == 0 and wr == 0 and wb == 0 and wn == 0 and wp == 0:
        return "K+P vs K"

    # K+Q vs K
    if wq >= 1 and wr == 0 and wp == 0 and bq == 0 and br == 0 and bp == 0:
        return "K+Q vs K"
    if bq >= 1 and br == 0 and bp == 0 and wq == 0 and wr == 0 and wp == 0:
        return "K+Q vs K"

    # K+R vs K
    if wr >= 1 and wq == 0 and wp == 0 and bq == 0 and br == 0 and bp == 0:
        return "K+R vs K"
    if br >= 1 and bq == 0 and bp == 0 and wq == 0 and wr == 0 and wp == 0:
        return "K+R vs K"

    # K+N+B vs K (Mate patterns)
    if (wn == 1 and wb == 1) or (bn == 1 and bb == 1):
        return "K+N+B vs K"

    # General endgame
    if wp + wq + wr + wb + wn <= 2 or bp + bq + br + bb + bn <= 2:
        return "theoretical_endgame"

    return "complex_position"


def _detect_threats(board: chess.Board, white_material: Dict, black_material: Dict,
                    white_pawns: List[str], black_pawns: List[str]) -> List[str]:
    """Identify tactical and strategic threats"""
    threats = []

    # Black pawn promotion threats
    for pawn_sq in black_pawns:
        rank = int(pawn_sq[1])
        if rank >= 6:  # Pawn is close to promoting
            threats.append(f"black_pawn_{pawn_sq}_close_to_promotion")

    # White pawn promotion threats
    for pawn_sq in white_pawns:
        rank = int(pawn_sq[1])
        if rank <= 3:  # Pawn is close to promoting
            threats.append(f"white_pawn_{pawn_sq}_close_to_promotion")

    # Check if rooks are attacked
    for rook_sq in board.pieces(chess.ROOK, chess.WHITE):
        if board.is_attacked_by(chess.BLACK, rook_sq):
            threats.append(f"white_rook_{chess.square_name(rook_sq)}_attacked")

    for rook_sq in board.pieces(chess.ROOK, chess.BLACK):
        if board.is_attacked_by(chess.WHITE, rook_sq):
            threats.append(f"black_rook_{chess.square_name(rook_sq)}_attacked")

    return threats


def _identify_critical_pieces(position_type: str, white_material: Dict, black_material: Dict,
                              white_pawns: List[str], black_pawns: List[str],
                              white_rooks: List[str], black_rooks: List[str],
                              threats: List[str]) -> Dict[str, str]:
    """Identify which pieces are critical to the position"""
    critical = {}

    # In K+R vs K+P, rook is critical for stopping pawn
    if position_type == "K+R vs K+P":
        if white_rooks:
            critical["white_rook"] = "only_defender_of_promotion_threat"
        if black_rooks:
            critical["black_rook"] = "only_defender_of_promotion_threat"

        # Identify threatening pawn
        if black_pawns:
            critical["black_pawn"] = "promotion_threat"
        if white_pawns:
            critical["white_pawn"] = "promotion_threat"

    # In R+P vs R, pawn is critical
    if position_type == "R+P vs R":
        if white_pawns:
            critical["white_pawn"] = "promotion_threat"
        if black_pawns:
            critical["black_pawn"] = "promotion_threat"

    # In K+P vs K, pawn is only attacker
    if position_type == "K+P vs K":
        if white_pawns:
            critical["white_pawn"] = "only_attacker"
        if black_pawns:
            critical["black_pawn"] = "only_attacker"

    return critical
