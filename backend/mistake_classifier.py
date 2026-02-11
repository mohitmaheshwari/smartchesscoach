"""
Deterministic Chess Mistake Classifier

This module classifies chess mistakes using RULES, not LLM guessing.
GPT should NEVER decide what mistake type is - this code does.

Mistake Types:
- HANGING_PIECE: Piece attacked and not defended
- MATERIAL_BLUNDER: Lost material on next move
- IGNORED_THREAT: Opponent had forcing move, player ignored
- BLUNDER_WHEN_AHEAD: Was winning, threw it away
- MISSED_TACTIC: Had winning move, played something else
- MISSED_FORK: Could have forked but didn't
- MISSED_PIN: Had pin opportunity but missed
- WALKED_INTO_FORK: Moved piece into fork
- WALKED_INTO_PIN: Moved piece into pin
- KING_SAFETY_ERROR: Weakened king position
- FAILED_CONVERSION: Was winning, couldn't convert
- TIME_PRESSURE_BLUNDER: Mistake in late game (proxy for time trouble)
- POSITIONAL_DRIFT: Small eval loss, no immediate tactic

Context Flags (all deterministic):
- phase: opening/middlegame/endgame (by piece count, not move number)
- was_ahead: true/false (eval > +1.5 before move)
- was_behind: true/false (eval < -1.5 before move)
- after_opponent_check: true/false
- after_own_attack: true/false
- material_balance: equal/up/down

Pattern Detection:
- Forks: One piece attacking two+ valuable pieces
- Pins: Piece pinned to more valuable piece behind
- Discovered attacks: Moving piece reveals attack
- Back rank weakness: King trapped on back rank

This is the TRUTH layer. GPT only narrates these tags.
"""

import chess
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MistakeType(Enum):
    """Deterministic mistake categories - NO LLM GUESSING"""
    HANGING_PIECE = "hanging_piece"
    MATERIAL_BLUNDER = "material_blunder"
    IGNORED_THREAT = "ignored_threat"
    BLUNDER_WHEN_AHEAD = "blunder_when_ahead"
    MISSED_WINNING_TACTIC = "missed_winning_tactic"
    MISSED_FORK = "missed_fork"
    MISSED_PIN = "missed_pin"
    WALKED_INTO_FORK = "walked_into_fork"
    WALKED_INTO_PIN = "walked_into_pin"
    KING_SAFETY_ERROR = "king_safety_error"
    FAILED_CONVERSION = "failed_conversion"
    TIME_PRESSURE_BLUNDER = "time_pressure_blunder"
    POSITIONAL_DRIFT = "positional_drift"
    GOOD_MOVE = "good_move"
    EXCELLENT_MOVE = "excellent_move"


class GamePhase(Enum):
    """Determined by piece count, NOT move number"""
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"


@dataclass
class MistakeContext:
    """All context flags - 100% deterministic, no guessing"""
    phase: GamePhase
    was_ahead: bool           # Eval > +1.5 before move
    was_behind: bool          # Eval < -1.5 before move
    was_equal: bool           # Eval between -1.5 and +1.5
    after_opponent_check: bool
    opponent_had_threat: bool
    material_balance: str     # "equal", "up", "down"
    move_number: int
    is_late_game: bool        # Move > 35 (proxy for time pressure)
    user_color: str           # "white" or "black"


@dataclass
class ClassifiedMistake:
    """The output - structured tags that GPT can verbalize"""
    mistake_type: MistakeType
    context: MistakeContext
    eval_before: float        # In pawns (e.g., +1.5)
    eval_after: float
    eval_drop: float          # How much was lost
    move_played: str
    best_move: str
    threat: Optional[str]     # What opponent threatened (if known)
    hanging_piece: Optional[str]  # Which piece was hanging (if applicable)
    pattern_details: Dict     # Additional pattern-specific data


# Piece values for material calculation
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0
}


def get_material_count(board: chess.Board, color: chess.Color) -> int:
    """Count material for a color (excluding king)"""
    total = 0
    for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        total += len(board.pieces(piece_type, color)) * PIECE_VALUES[piece_type]
    return total


def get_total_material(board: chess.Board) -> int:
    """Total material on board (both sides)"""
    return get_material_count(board, chess.WHITE) + get_material_count(board, chess.BLACK)


def determine_phase(board: chess.Board) -> GamePhase:
    """
    Determine game phase by PIECE COUNT, not move number.
    This is more accurate than arbitrary move thresholds.
    """
    total_material = get_total_material(board)
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    
    # Endgame: low material or no queens with limited pieces
    if total_material <= 26:  # Roughly rook + minor vs rook + minor
        return GamePhase.ENDGAME
    
    # Opening: high material and pieces not developed much
    # We check if many pieces are still on starting squares
    if total_material >= 60:  # Most pieces still on board
        # Check if pieces are still on back ranks (rough development check)
        back_rank_pieces = 0
        for sq in [chess.A1, chess.B1, chess.C1, chess.D1, chess.E1, chess.F1, chess.G1, chess.H1,
                   chess.A8, chess.B8, chess.C8, chess.D8, chess.E8, chess.F8, chess.G8, chess.H8]:
            if board.piece_at(sq):
                back_rank_pieces += 1
        if back_rank_pieces >= 10:  # Many pieces still home
            return GamePhase.OPENING
    
    return GamePhase.MIDDLEGAME


def find_hanging_pieces(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Find pieces that are attacked but not defended.
    This is DETERMINISTIC - no guessing.
    """
    hanging = []
    opponent = not color
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color and piece.piece_type != chess.KING:
            attackers = board.attackers(opponent, square)
            defenders = board.attackers(color, square)
            
            if attackers and not defenders:
                hanging.append({
                    "square": chess.square_name(square),
                    "piece": chess.piece_name(piece.piece_type),
                    "value": PIECE_VALUES[piece.piece_type]
                })
    
    # Sort by value (most valuable first)
    hanging.sort(key=lambda x: x["value"], reverse=True)
    return hanging


def find_attacked_pieces(board: chess.Board, color: chess.Color) -> List[Dict]:
    """Find all pieces under attack (whether defended or not)"""
    attacked = []
    opponent = not color
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color and piece.piece_type != chess.KING:
            attackers = board.attackers(opponent, square)
            if attackers:
                defenders = board.attackers(color, square)
                attacked.append({
                    "square": chess.square_name(square),
                    "piece": chess.piece_name(piece.piece_type),
                    "value": PIECE_VALUES[piece.piece_type],
                    "num_attackers": len(attackers),
                    "num_defenders": len(defenders),
                    "is_hanging": len(defenders) == 0
                })
    
    return attacked


def is_in_check(board: chess.Board, color: chess.Color) -> bool:
    """Check if the given color's king is in check"""
    return board.is_attacked_by(not color, board.king(color))


def has_forcing_move(board: chess.Board) -> bool:
    """Check if current side to move has checks or captures"""
    for move in board.legal_moves:
        if board.is_capture(move) or board.gives_check(move):
            return True
    return False


def get_threats(board: chess.Board, color: chess.Color) -> List[str]:
    """
    Find what the opponent is threatening.
    Returns list of threat descriptions.
    """
    threats = []
    opponent = not color
    
    # Simulate opponent's turn to see their threats
    board_copy = board.copy()
    board_copy.turn = opponent
    
    # Check for attacks on valuable pieces
    for square in chess.SQUARES:
        piece = board_copy.piece_at(square)
        if piece and piece.color == color and piece.piece_type != chess.KING:
            attackers = board_copy.attackers(opponent, square)
            defenders = board_copy.attackers(color, square)
            
            if attackers:
                lowest_attacker_value = min(
                    PIECE_VALUES.get(board_copy.piece_at(att).piece_type, 10) 
                    for att in attackers if board_copy.piece_at(att)
                )
                piece_value = PIECE_VALUES[piece.piece_type]
                
                # Threat if attacker is worth less, or piece is undefended
                if lowest_attacker_value < piece_value or not defenders:
                    threats.append(f"capture {chess.piece_name(piece.piece_type)} on {chess.square_name(square)}")
    
    # Check for mate threats (simplified)
    for move in board_copy.legal_moves:
        board_copy.push(move)
        if board_copy.is_checkmate():
            threats.append("checkmate")
            board_copy.pop()
            break
        board_copy.pop()
    
    return threats[:3]  # Return top 3 threats


def find_forks(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Find all fork opportunities for a color.
    A fork is when one piece attacks two or more valuable enemy pieces simultaneously.
    
    Returns list of fork opportunities with details.
    """
    forks = []
    opponent = not color
    
    # Check each of our pieces for forking potential
    for attacker_sq in chess.SQUARES:
        attacker = board.piece_at(attacker_sq)
        if not attacker or attacker.color != color:
            continue
        
        # Find all enemy pieces this attacker is attacking
        attacked_pieces = []
        for target_sq in chess.SQUARES:
            target = board.piece_at(target_sq)
            if not target or target.color != opponent:
                continue
            
            # Check if our piece attacks this square
            if board.is_attacked_by(color, target_sq):
                # Check if this specific piece is doing the attacking
                attackers = board.attackers(color, target_sq)
                if attacker_sq in attackers:
                    attacked_pieces.append({
                        "square": chess.square_name(target_sq),
                        "piece": chess.piece_name(target.piece_type),
                        "value": PIECE_VALUES.get(target.piece_type, 0)
                    })
        
        # It's a fork if attacking 2+ pieces and at least one is valuable
        if len(attacked_pieces) >= 2:
            total_value = sum(p["value"] for p in attacked_pieces)
            # Only count as a fork if total value is significant
            if total_value >= 5:  # At least a rook's worth
                forks.append({
                    "attacker_square": chess.square_name(attacker_sq),
                    "attacker_piece": chess.piece_name(attacker.piece_type),
                    "targets": attacked_pieces,
                    "total_value": total_value
                })
    
    # Sort by value (best forks first)
    forks.sort(key=lambda x: x["total_value"], reverse=True)
    return forks


def find_pins(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Find all pins in the position for a color.
    A pin is when a piece cannot move because it would expose a more valuable piece behind it.
    
    Returns list of pins with details.
    """
    pins = []
    opponent = not color
    
    # For each of our pieces, check if it's pinned
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece or piece.color != color:
            continue
        
        # Check if this piece is pinned (to the king)
        if board.is_pinned(color, square):
            # Find what's pinning it
            king_square = board.king(color)
            if king_square is None:
                continue
                
            # Find the pinner (opponent piece on the pin ray)
            pin_ray = chess.SquareSet.between(king_square, square)
            pin_direction = chess.square_file(square) - chess.square_file(king_square)
            
            # Extend beyond the pinned piece to find the pinner
            pinner_info = None
            for direction_sq in chess.SQUARES:
                pinner = board.piece_at(direction_sq)
                if pinner and pinner.color == opponent:
                    # Check if this piece attacks through the pinned piece
                    if board.is_attacked_by(opponent, square):
                        attackers = board.attackers(opponent, square)
                        if direction_sq in attackers:
                            # Verify it's a sliding piece that could pin
                            if pinner.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                                pinner_info = {
                                    "pinner_square": chess.square_name(direction_sq),
                                    "pinner_piece": chess.piece_name(pinner.piece_type)
                                }
                                break
            
            pins.append({
                "pinned_square": chess.square_name(square),
                "pinned_piece": chess.piece_name(piece.piece_type),
                "pinned_value": PIECE_VALUES.get(piece.piece_type, 0),
                "pinned_to": "king",
                "pinner": pinner_info
            })
    
    return pins


def find_discovered_attack_potential(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Find positions where a piece can move to reveal an attack from a piece behind it.
    (Discovered attacks, discovered checks)
    
    Returns list of potential discovered attacks.
    """
    discovered = []
    opponent = not color
    
    # Look for pieces that are blocking our sliding pieces
    for blocker_sq in chess.SQUARES:
        blocker = board.piece_at(blocker_sq)
        if not blocker or blocker.color != color:
            continue
        
        # Check what's behind this piece (along diagonals and lines)
        directions = [
            (chess.BB_FILE_A, 8),   # Up
            (chess.BB_FILE_A, -8),  # Down  
            (chess.BB_RANK_1, 1),   # Right
            (chess.BB_RANK_1, -1),  # Left
            (chess.BB_ALL, 9),      # Diagonal up-right
            (chess.BB_ALL, -9),     # Diagonal down-left
            (chess.BB_ALL, 7),      # Diagonal up-left
            (chess.BB_ALL, -7),     # Diagonal down-right
        ]
        
        for _, direction in directions:
            # Look behind the blocker
            behind_sq = blocker_sq - direction
            if not 0 <= behind_sq <= 63:
                continue
                
            behind_piece = board.piece_at(behind_sq)
            if not behind_piece or behind_piece.color != color:
                continue
            
            # Check if it's a sliding piece that could attack through
            if behind_piece.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                continue
            
            # Look forward (where the attack would go if blocker moves)
            check_sq = blocker_sq + direction
            while 0 <= check_sq <= 63:
                target = board.piece_at(check_sq)
                if target:
                    if target.color == opponent:
                        # Found a potential discovered attack!
                        discovered.append({
                            "blocker_square": chess.square_name(blocker_sq),
                            "blocker_piece": chess.piece_name(blocker.piece_type),
                            "attacker_square": chess.square_name(behind_sq),
                            "attacker_piece": chess.piece_name(behind_piece.piece_type),
                            "target_square": chess.square_name(check_sq),
                            "target_piece": chess.piece_name(target.piece_type),
                            "target_value": PIECE_VALUES.get(target.piece_type, 0),
                            "is_check": target.piece_type == chess.KING
                        })
                    break  # Blocked by a piece
                check_sq += direction
    
    # Sort by value (best discovered attacks first, prioritize checks)
    discovered.sort(key=lambda x: (x["is_check"], x["target_value"]), reverse=True)
    return discovered


def detect_walked_into_fork(board_before: chess.Board, board_after: chess.Board, 
                           user_color: chess.Color) -> Optional[Dict]:
    """
    Detect if user's move walked into a fork.
    Compare forks available to opponent before and after the move.
    """
    opponent = not user_color
    
    # Check for forks by opponent AFTER user's move
    forks_after = find_forks(board_after, opponent)
    
    if forks_after:
        # Return the most valuable fork
        return forks_after[0]
    
    return None


def detect_walked_into_pin(board_before: chess.Board, board_after: chess.Board,
                          user_color: chess.Color) -> Optional[Dict]:
    """
    Detect if user's move created a pin against themselves.
    """
    pins_before = find_pins(board_before, user_color)
    pins_after = find_pins(board_after, user_color)
    
    # Check if a new pin was created
    if len(pins_after) > len(pins_before):
        # Return the new pin
        for pin in pins_after:
            is_new = True
            for old_pin in pins_before:
                if pin["pinned_square"] == old_pin["pinned_square"]:
                    is_new = False
                    break
            if is_new:
                return pin
    
    return None


def detect_missed_fork(board_before: chess.Board, best_move: str, 
                       user_color: chess.Color) -> Optional[Dict]:
    """
    Detect if the best move would have created a fork.
    """
    try:
        board_copy = board_before.copy()
        board_copy.push_san(best_move)
        
        # Check for forks after best move
        forks = find_forks(board_copy, user_color)
        if forks:
            return forks[0]
    except:
        pass
    
    return None


def detect_missed_pin(board_before: chess.Board, best_move: str,
                     user_color: chess.Color) -> Optional[Dict]:
    """
    Detect if the best move would have created a pin.
    """
    opponent = not user_color
    
    try:
        board_copy = board_before.copy()
        board_copy.push_san(best_move)
        
        # Check for pins on opponent after best move
        pins = find_pins(board_copy, opponent)
        if pins:
            return pins[0]
    except:
        pass
    
    return None


def classify_mistake(
    fen_before: str,
    fen_after: str,
    move_played: str,
    best_move: str,
    eval_before: float,  # In centipawns
    eval_after: float,   # In centipawns
    user_color: str,
    move_number: int,
    threat: Optional[str] = None
) -> ClassifiedMistake:
    """
    DETERMINISTIC mistake classification.
    
    This function uses RULES to classify mistakes.
    It does NOT use LLM. It does NOT guess.
    
    GPT will ONLY verbalize the output of this function.
    """
    
    try:
        board_before = chess.Board(fen_before)
        board_after = chess.Board(fen_after)
    except Exception as e:
        logger.error(f"Invalid FEN: {e}")
        # Return a safe default
        return ClassifiedMistake(
            mistake_type=MistakeType.POSITIONAL_DRIFT,
            context=MistakeContext(
                phase=GamePhase.MIDDLEGAME,
                was_ahead=False, was_behind=False, was_equal=True,
                after_opponent_check=False, opponent_had_threat=False,
                material_balance="equal", move_number=move_number,
                is_late_game=move_number > 35, user_color=user_color
            ),
            eval_before=eval_before/100, eval_after=eval_after/100,
            eval_drop=abs(eval_before - eval_after)/100,
            move_played=move_played, best_move=best_move,
            threat=threat, hanging_piece=None, pattern_details={}
        )
    
    # Convert centipawns to pawns
    eval_before_pawns = eval_before / 100
    eval_after_pawns = eval_after / 100
    
    # Adjust for user color (positive = good for user)
    if user_color.lower() == "black":
        eval_before_pawns = -eval_before_pawns
        eval_after_pawns = -eval_after_pawns
    
    eval_drop = eval_before_pawns - eval_after_pawns  # Positive = player lost advantage
    
    user_chess_color = chess.WHITE if user_color.lower() == "white" else chess.BLACK
    opponent_color = not user_chess_color
    
    # === DETERMINE CONTEXT (100% deterministic) ===
    
    phase = determine_phase(board_before)
    
    was_ahead = eval_before_pawns > 1.5
    was_behind = eval_before_pawns < -1.5
    was_equal = not was_ahead and not was_behind
    
    # Check if opponent had check before the move
    after_opponent_check = is_in_check(board_before, user_chess_color)
    
    # Check if opponent had threats
    threats = get_threats(board_before, user_chess_color)
    opponent_had_threat = len(threats) > 0
    
    # Material balance
    user_material = get_material_count(board_before, user_chess_color)
    opp_material = get_material_count(board_before, opponent_color)
    if user_material > opp_material + 2:
        material_balance = "up"
    elif user_material < opp_material - 2:
        material_balance = "down"
    else:
        material_balance = "equal"
    
    is_late_game = move_number > 35
    
    context = MistakeContext(
        phase=phase,
        was_ahead=was_ahead,
        was_behind=was_behind,
        was_equal=was_equal,
        after_opponent_check=after_opponent_check,
        opponent_had_threat=opponent_had_threat,
        material_balance=material_balance,
        move_number=move_number,
        is_late_game=is_late_game,
        user_color=user_color
    )
    
    # === CLASSIFY MISTAKE TYPE (RULE-BASED) ===
    
    pattern_details = {}
    hanging_piece = None
    mistake_type = MistakeType.POSITIONAL_DRIFT  # Default
    
    # Check for hanging pieces AFTER the move
    hanging_after = find_hanging_pieces(board_after, user_chess_color)
    if hanging_after:
        hanging_piece = f"{hanging_after[0]['piece']} on {hanging_after[0]['square']}"
        pattern_details["hanging_pieces"] = hanging_after
    
    # Check material change
    material_before = get_material_count(board_before, user_chess_color)
    material_after = get_material_count(board_after, user_chess_color)
    material_lost = material_before - material_after
    
    # Check for fork/pin patterns (NEW)
    walked_into_fork = detect_walked_into_fork(board_before, board_after, user_chess_color)
    walked_into_pin = detect_walked_into_pin(board_before, board_after, user_chess_color)
    missed_fork = detect_missed_fork(board_before, best_move, user_chess_color) if best_move else None
    missed_pin = detect_missed_pin(board_before, best_move, user_chess_color) if best_move else None
    
    # === RULE-BASED CLASSIFICATION ===
    
    # Rule 1: Good/Excellent move (small or no eval drop)
    if eval_drop <= 0.1:
        mistake_type = MistakeType.EXCELLENT_MOVE
    elif eval_drop <= 0.3:
        mistake_type = MistakeType.GOOD_MOVE
    
    # Rule 2: WALKED_INTO_FORK - moved into a fork
    elif walked_into_fork and eval_drop > 1.0:
        mistake_type = MistakeType.WALKED_INTO_FORK
        pattern_details["fork"] = walked_into_fork
        pattern_details["reason"] = f"Opponent can now fork your pieces with {walked_into_fork['attacker_piece']}"
    
    # Rule 3: WALKED_INTO_PIN - created a pin against yourself  
    elif walked_into_pin and eval_drop > 0.5:
        mistake_type = MistakeType.WALKED_INTO_PIN
        pattern_details["pin"] = walked_into_pin
        pattern_details["reason"] = f"Your {walked_into_pin['pinned_piece']} is now pinned"
    
    # Rule 4: MISSED_FORK - could have forked but didn't
    elif missed_fork and eval_drop > 1.5:
        mistake_type = MistakeType.MISSED_FORK
        pattern_details["missed_fork"] = missed_fork
        pattern_details["reason"] = f"You could have forked with {best_move}"
    
    # Rule 5: MISSED_PIN - could have pinned but didn't
    elif missed_pin and eval_drop > 1.0:
        mistake_type = MistakeType.MISSED_PIN
        pattern_details["missed_pin"] = missed_pin
        pattern_details["reason"] = f"You could have created a pin with {best_move}"
    
    # Rule 6: HANGING_PIECE - piece left undefended and eval dropped significantly
    elif hanging_after and eval_drop > 0.5:
        mistake_type = MistakeType.HANGING_PIECE
        pattern_details["reason"] = f"Left {hanging_piece} undefended"
    
    # Rule 7: MATERIAL_BLUNDER - lost material immediately
    elif material_lost >= 2 and eval_drop > 1.0:  # Lost at least a minor piece worth
        mistake_type = MistakeType.MATERIAL_BLUNDER
        pattern_details["material_lost"] = material_lost
    
    # Rule 8: BLUNDER_WHEN_AHEAD - was winning, now not
    elif was_ahead and eval_after_pawns < 1.0 and eval_drop > 1.5:
        mistake_type = MistakeType.BLUNDER_WHEN_AHEAD
        pattern_details["threw_away"] = f"Was +{eval_before_pawns:.1f}, now +{eval_after_pawns:.1f}"
    
    # Rule 9: IGNORED_THREAT - opponent had threat, player didn't address it
    elif opponent_had_threat and eval_drop > 1.0:
        mistake_type = MistakeType.IGNORED_THREAT
        pattern_details["threats_ignored"] = threats
    
    # Rule 10: FAILED_CONVERSION - was significantly ahead, couldn't increase/maintain
    elif was_ahead and eval_drop > 0.5 and eval_after_pawns > 0:
        mistake_type = MistakeType.FAILED_CONVERSION
    
    # Rule 11: MISSED_WINNING_TACTIC - eval swing shows missed opportunity
    elif eval_drop > 2.0 and not was_behind:
        mistake_type = MistakeType.MISSED_WINNING_TACTIC
        pattern_details["missed_advantage"] = eval_drop
    
    # Rule 12: TIME_PRESSURE_BLUNDER - late game blunder (proxy)
    elif is_late_game and eval_drop > 1.5:
        mistake_type = MistakeType.TIME_PRESSURE_BLUNDER
    
    # Rule 13: KING_SAFETY_ERROR - if king becomes exposed (simplified check)
    # This would need more sophisticated king safety evaluation
    
    # Rule 14: Default - small positional error
    elif eval_drop > 0.3:
        mistake_type = MistakeType.POSITIONAL_DRIFT
    
    return ClassifiedMistake(
        mistake_type=mistake_type,
        context=context,
        eval_before=eval_before_pawns,
        eval_after=eval_after_pawns,
        eval_drop=eval_drop,
        move_played=move_played,
        best_move=best_move,
        threat=threat if threat else (threats[0] if threats else None),
        hanging_piece=hanging_piece,
        pattern_details=pattern_details
    )


def get_verbalization_template(mistake: ClassifiedMistake) -> str:
    """
    Returns a TEMPLATE for GPT to verbalize.
    GPT cannot change the facts - only the wording.
    """
    
    templates = {
        MistakeType.HANGING_PIECE: (
            f"You left your {mistake.hanging_piece} undefended. "
            f"Opponent can capture it for free. "
            f"Before moving, always check: is my piece safe?"
        ),
        
        MistakeType.MATERIAL_BLUNDER: (
            f"This move lost material ({mistake.pattern_details.get('material_lost', '?')} points). "
            f"You went from {'+' if mistake.eval_before > 0 else ''}{mistake.eval_before:.1f} to "
            f"{'+' if mistake.eval_after > 0 else ''}{mistake.eval_after:.1f}. "
            f"The better move was {mistake.best_move}."
        ),
        
        MistakeType.BLUNDER_WHEN_AHEAD: (
            f"You were winning (+{mistake.eval_before:.1f}) but threw it away. "
            f"When ahead, play safe and simple moves. Don't complicate."
        ),
        
        MistakeType.IGNORED_THREAT: (
            f"Your opponent was threatening {mistake.threat}. "
            f"You didn't stop it. Before each move, ask: what is my opponent trying to do?"
        ),
        
        MistakeType.FAILED_CONVERSION: (
            f"You were ahead but couldn't increase your advantage. "
            f"When winning, look for simple ways to trade pieces and simplify."
        ),
        
        MistakeType.MISSED_WINNING_TACTIC: (
            f"There was a winning move ({mistake.best_move}) but you missed it. "
            f"The position had a tactic worth {mistake.eval_drop:.1f} pawns."
        ),
        
        MistakeType.TIME_PRESSURE_BLUNDER: (
            f"Late-game mistake - possibly due to time pressure. "
            f"Manage your clock better in the opening and middlegame."
        ),
        
        MistakeType.POSITIONAL_DRIFT: (
            f"Small inaccuracy. {mistake.best_move} was slightly better. "
            f"Eval dropped by {mistake.eval_drop:.1f}."
        ),
        
        MistakeType.GOOD_MOVE: (
            f"Good move! You found a reasonable continuation."
        ),
        
        MistakeType.EXCELLENT_MOVE: (
            f"Excellent! You found the best move."
        )
    }
    
    return templates.get(mistake.mistake_type, f"Move analyzed: {mistake.move_played}")


def classify_for_badge(mistakes: List[ClassifiedMistake]) -> Dict[str, int]:
    """
    Aggregate mistakes into badge-relevant categories.
    100% deterministic counting - no LLM.
    """
    counts = {
        "tactical_misses": 0,
        "hanging_pieces": 0,
        "blunders_when_ahead": 0,
        "ignored_threats": 0,
        "time_pressure_errors": 0,
        "positional_errors": 0,
        "good_moves": 0,
        "excellent_moves": 0,
        "total_mistakes": 0
    }
    
    for m in mistakes:
        if m.mistake_type == MistakeType.HANGING_PIECE:
            counts["hanging_pieces"] += 1
            counts["tactical_misses"] += 1
            counts["total_mistakes"] += 1
        elif m.mistake_type == MistakeType.MATERIAL_BLUNDER:
            counts["tactical_misses"] += 1
            counts["total_mistakes"] += 1
        elif m.mistake_type == MistakeType.BLUNDER_WHEN_AHEAD:
            counts["blunders_when_ahead"] += 1
            counts["total_mistakes"] += 1
        elif m.mistake_type == MistakeType.IGNORED_THREAT:
            counts["ignored_threats"] += 1
            counts["total_mistakes"] += 1
        elif m.mistake_type == MistakeType.MISSED_WINNING_TACTIC:
            counts["tactical_misses"] += 1
            counts["total_mistakes"] += 1
        elif m.mistake_type == MistakeType.TIME_PRESSURE_BLUNDER:
            counts["time_pressure_errors"] += 1
            counts["total_mistakes"] += 1
        elif m.mistake_type == MistakeType.POSITIONAL_DRIFT:
            counts["positional_errors"] += 1
            counts["total_mistakes"] += 1
        elif m.mistake_type == MistakeType.GOOD_MOVE:
            counts["good_moves"] += 1
        elif m.mistake_type == MistakeType.EXCELLENT_MOVE:
            counts["excellent_moves"] += 1
    
    return counts


# === TEST ===
if __name__ == "__main__":
    # Test with a position where black has a hanging knight
    fen_before = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    fen_after = "r1bqkb1r/pppp1ppp/2n2n2/4N3/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 0 4"
    
    result = classify_mistake(
        fen_before=fen_before,
        fen_after=fen_after,
        move_played="Nf3",  # Some move
        best_move="Nxe5",
        eval_before=50,  # +0.5
        eval_after=-150,  # -1.5
        user_color="white",
        move_number=4
    )
    
    print(f"Mistake Type: {result.mistake_type.value}")
    print(f"Phase: {result.context.phase.value}")
    print(f"Eval Drop: {result.eval_drop:.1f}")
    print(f"Was Ahead: {result.context.was_ahead}")
    print(f"Template: {get_verbalization_template(result)}")
