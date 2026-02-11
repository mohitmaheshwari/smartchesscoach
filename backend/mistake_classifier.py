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
    Find all fork opportunities for a color using efficient bitboard operations.
    
    A fork is when one piece attacks two or more valuable enemy pieces simultaneously.
    We focus on:
    - Knight forks (most common and dangerous)
    - Queen forks
    - Pawn forks (when attacking two pieces)
    
    Returns list of fork opportunities with details, sorted by value.
    """
    forks = []
    opponent = not color
    
    # Valuable pieces worth forking (king=100 for fork purposes since it must move)
    FORK_VALUES = {
        chess.KING: 100,  # King must respond to attack
        chess.QUEEN: 9,
        chess.ROOK: 5,
        chess.BISHOP: 3,
        chess.KNIGHT: 3,
        chess.PAWN: 1
    }
    
    # Get all opponent pieces as a set for quick lookup
    opponent_pieces = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == opponent:
            opponent_pieces.append((sq, piece))
    
    # Check each of our pieces for forking potential
    # Priority: Knights > Queens > Pawns > Others
    piece_types_to_check = [chess.KNIGHT, chess.QUEEN, chess.PAWN, chess.BISHOP, chess.ROOK]
    
    for piece_type in piece_types_to_check:
        for attacker_sq in board.pieces(piece_type, color):
            # Use board.attacks() - returns a SquareSet of attacked squares (bitboard efficient)
            attacks = board.attacks(attacker_sq)
            
            # Find which opponent pieces are under attack
            targets = []
            for target_sq, target_piece in opponent_pieces:
                if target_sq in attacks:
                    targets.append({
                        "square": chess.square_name(target_sq),
                        "piece": chess.piece_name(target_piece.piece_type),
                        "value": FORK_VALUES.get(target_piece.piece_type, 1)
                    })
            
            # It's a fork if attacking 2+ pieces
            if len(targets) >= 2:
                # Calculate total value - must include at least one valuable target
                total_value = sum(t["value"] for t in targets)
                has_valuable_target = any(t["value"] >= 3 for t in targets)  # At least a minor piece
                
                # For knights, lower threshold (knight forks are always tactical)
                # For others, need higher value to be considered a real fork
                min_value = 4 if piece_type == chess.KNIGHT else 6
                
                if has_valuable_target and total_value >= min_value:
                    forks.append({
                        "attacker_square": chess.square_name(attacker_sq),
                        "attacker_piece": chess.piece_name(piece_type),
                        "targets": sorted(targets, key=lambda x: x["value"], reverse=True),
                        "total_value": total_value,
                        "includes_king": any(t["value"] == 100 for t in targets),
                        "includes_queen": any(t["value"] == 9 for t in targets)
                    })
    
    # Sort by: king involvement > queen involvement > total value
    forks.sort(key=lambda x: (x["includes_king"], x["includes_queen"], x["total_value"]), reverse=True)
    return forks


def find_pins(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Find all pins against a color using python-chess's built-in pin detection.
    
    Detects both:
    - Absolute pins (pinned to king - piece cannot move at all without check)
    - Relative pins (pinned to queen/rook - piece shouldn't move or loses material)
    
    Returns list of pins with details.
    """
    pins = []
    opponent = not color
    
    # Find absolute pins (to king) - python-chess has this built-in
    king_sq = board.king(color)
    if king_sq is None:
        return pins
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece or piece.color != color or piece.piece_type == chess.KING:
            continue
        
        # Check if this piece is absolutely pinned (to the king)
        if board.is_pinned(color, square):
            # Get the pin ray to find the pinner
            pin_mask = board.pin(color, square)
            
            # Find the pinner (opponent piece on the pin ray, beyond the pinned piece)
            pinner_info = None
            for pinner_sq in pin_mask:
                pinner = board.piece_at(pinner_sq)
                if pinner and pinner.color == opponent:
                    if pinner.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                        pinner_info = {
                            "pinner_square": chess.square_name(pinner_sq),
                            "pinner_piece": chess.piece_name(pinner.piece_type),
                            "pinner_value": PIECE_VALUES.get(pinner.piece_type, 0)
                        }
                        break
            
            pins.append({
                "pinned_square": chess.square_name(square),
                "pinned_piece": chess.piece_name(piece.piece_type),
                "pinned_value": PIECE_VALUES.get(piece.piece_type, 0),
                "pinned_to": "king",
                "pin_type": "absolute",
                "pinner": pinner_info
            })
    
    # Find relative pins (to queen) - more complex, check if moving piece loses the queen
    queen_sq = None
    for sq in board.pieces(chess.QUEEN, color):
        queen_sq = sq
        break  # Just get first queen
    
    if queen_sq:
        # Check pieces between sliding attackers and our queen
        for attacker_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
            for attacker_sq in board.pieces(attacker_type, opponent):
                # Get the ray between attacker and our queen
                if attacker_type == chess.BISHOP:
                    # Diagonal rays
                    if chess.square_file(attacker_sq) == chess.square_file(queen_sq):
                        continue  # Same file, not diagonal
                    if chess.square_rank(attacker_sq) == chess.square_rank(queen_sq):
                        continue  # Same rank, not diagonal
                    file_diff = abs(chess.square_file(attacker_sq) - chess.square_file(queen_sq))
                    rank_diff = abs(chess.square_rank(attacker_sq) - chess.square_rank(queen_sq))
                    if file_diff != rank_diff:
                        continue  # Not on diagonal
                elif attacker_type == chess.ROOK:
                    # Straight rays
                    if chess.square_file(attacker_sq) != chess.square_file(queen_sq) and \
                       chess.square_rank(attacker_sq) != chess.square_rank(queen_sq):
                        continue  # Not on same file or rank
                
                # Check if there's exactly one of our pieces between attacker and queen
                between = chess.SquareSet.between(attacker_sq, queen_sq)
                our_pieces_between = []
                blocked = False
                
                for sq in between:
                    piece = board.piece_at(sq)
                    if piece:
                        if piece.color == color:
                            our_pieces_between.append((sq, piece))
                        else:
                            blocked = True  # Opponent piece in the way
                            break
                
                if not blocked and len(our_pieces_between) == 1:
                    pinned_sq, pinned_piece = our_pieces_between[0]
                    # Don't duplicate absolute pins
                    if not board.is_pinned(color, pinned_sq):
                        pins.append({
                            "pinned_square": chess.square_name(pinned_sq),
                            "pinned_piece": chess.piece_name(pinned_piece.piece_type),
                            "pinned_value": PIECE_VALUES.get(pinned_piece.piece_type, 0),
                            "pinned_to": "queen",
                            "pin_type": "relative",
                            "pinner": {
                                "pinner_square": chess.square_name(attacker_sq),
                                "pinner_piece": chess.piece_name(attacker_type),
                                "pinner_value": PIECE_VALUES.get(attacker_type, 0)
                            }
                        })
    
    # Sort by: absolute pins first, then by value of pinned piece
    pins.sort(key=lambda x: (x["pin_type"] == "absolute", x["pinned_value"]), reverse=True)
    return pins


def find_skewers(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Find skewer opportunities for a color.
    
    A skewer is like a reverse pin - attacking a valuable piece that must move,
    revealing an attack on a less valuable piece behind it.
    
    Returns list of skewer opportunities.
    """
    skewers = []
    opponent = not color
    
    # Check our sliding pieces for skewer potential
    for attacker_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
        for attacker_sq in board.pieces(attacker_type, color):
            attacks = board.attacks(attacker_sq)
            
            # For each attacked enemy piece, check if there's another behind it
            for target_sq in attacks:
                front_piece = board.piece_at(target_sq)
                if not front_piece or front_piece.color != opponent:
                    continue
                
                # Get squares beyond the target on the same ray
                # Direction from attacker to target
                file_diff = chess.square_file(target_sq) - chess.square_file(attacker_sq)
                rank_diff = chess.square_rank(target_sq) - chess.square_rank(attacker_sq)
                
                # Normalize to get direction
                if file_diff != 0:
                    file_dir = file_diff // abs(file_diff)
                else:
                    file_dir = 0
                if rank_diff != 0:
                    rank_dir = rank_diff // abs(rank_diff)
                else:
                    rank_dir = 0
                
                # Check squares beyond target
                check_file = chess.square_file(target_sq) + file_dir
                check_rank = chess.square_rank(target_sq) + rank_dir
                
                while 0 <= check_file <= 7 and 0 <= check_rank <= 7:
                    behind_sq = chess.square(check_file, check_rank)
                    behind_piece = board.piece_at(behind_sq)
                    
                    if behind_piece:
                        if behind_piece.color == opponent:
                            front_value = PIECE_VALUES.get(front_piece.piece_type, 0)
                            behind_value = PIECE_VALUES.get(behind_piece.piece_type, 0)
                            
                            # It's a skewer if front piece is more valuable (must move)
                            if front_value > behind_value and front_value >= 3:
                                skewers.append({
                                    "attacker_square": chess.square_name(attacker_sq),
                                    "attacker_piece": chess.piece_name(attacker_type),
                                    "front_piece": {
                                        "square": chess.square_name(target_sq),
                                        "piece": chess.piece_name(front_piece.piece_type),
                                        "value": front_value
                                    },
                                    "behind_piece": {
                                        "square": chess.square_name(behind_sq),
                                        "piece": chess.piece_name(behind_piece.piece_type),
                                        "value": behind_value
                                    },
                                    "gain": behind_value  # What we win when front moves
                                })
                        break  # Blocked
                    
                    check_file += file_dir
                    check_rank += rank_dir
    
    skewers.sort(key=lambda x: x["gain"], reverse=True)
    return skewers


def detect_walked_into_fork(board_before: chess.Board, board_after: chess.Board, 
                           user_color: chess.Color) -> Optional[Dict]:
    """
    Detect if user's move walked into a fork.
    
    Compares forks available to opponent before and after the move.
    Only reports NEW forks created by the user's move.
    """
    opponent = not user_color
    
    # Get forks before and after
    forks_before = find_forks(board_before, opponent)
    forks_after = find_forks(board_after, opponent)
    
    if not forks_after:
        return None
    
    # Check if this is a NEW fork (not one that existed before)
    forks_before_squares = {f["attacker_square"] for f in forks_before}
    
    for fork in forks_after:
        if fork["attacker_square"] not in forks_before_squares:
            return fork
        # Also check if same attacker but now attacks MORE valuable pieces
        for old_fork in forks_before:
            if old_fork["attacker_square"] == fork["attacker_square"]:
                if fork["total_value"] > old_fork["total_value"] + 2:
                    return fork
    
    return None


def detect_walked_into_pin(board_before: chess.Board, board_after: chess.Board,
                          user_color: chess.Color) -> Optional[Dict]:
    """
    Detect if user's move created a pin against themselves.
    
    Only reports NEW pins created by the move.
    """
    pins_before = find_pins(board_before, user_color)
    pins_after = find_pins(board_after, user_color)
    
    if not pins_after:
        return None
    
    # Get pinned squares before
    pinned_before = {p["pinned_square"] for p in pins_before}
    
    # Find new pins
    for pin in pins_after:
        if pin["pinned_square"] not in pinned_before:
            return pin
    
    return None


def detect_missed_fork(board_before: chess.Board, best_move: str, 
                       user_color: chess.Color) -> Optional[Dict]:
    """
    Detect if the best move would have created a fork.
    
    Only reports if the best move creates a STRONG fork.
    """
    if not best_move:
        return None
    
    try:
        board_copy = board_before.copy()
        board_copy.push_san(best_move)
        
        # Check for forks after best move
        forks = find_forks(board_copy, user_color)
        if forks:
            # Only report significant forks
            best_fork = forks[0]
            if best_fork["includes_king"] or best_fork["includes_queen"] or best_fork["total_value"] >= 8:
                return best_fork
    except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError):
        pass
    
    return None


def detect_missed_pin(board_before: chess.Board, best_move: str,
                     user_color: chess.Color) -> Optional[Dict]:
    """
    Detect if the best move would have created a pin on opponent.
    
    Only reports significant pins (absolute or pinning valuable piece).
    """
    if not best_move:
        return None
    
    opponent = not user_color
    
    try:
        board_copy = board_before.copy()
        board_copy.push_san(best_move)
        
        # Check for pins on opponent after best move
        pins = find_pins(board_copy, opponent)
        if pins:
            best_pin = pins[0]
            # Only report absolute pins or pins of valuable pieces
            if best_pin["pin_type"] == "absolute" or best_pin["pinned_value"] >= 3:
                return best_pin
    except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError):
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
    
    # Get pattern details for fork/pin messages
    reason = mistake.pattern_details.get("reason", "")
    
    templates = {
        MistakeType.WALKED_INTO_FORK: (
            f"You walked into a fork! {reason}. "
            "Before moving, check what squares your opponent's pieces can reach."
        ),
        
        MistakeType.WALKED_INTO_PIN: (
            f"You created a pin against yourself. {reason}. "
            "Pinned pieces can't move freely - always consider diagonal and file attacks."
        ),
        
        MistakeType.MISSED_FORK: (
            f"You missed a fork! {mistake.best_move} would have attacked multiple pieces at once. "
            "Look for knight moves that attack two pieces - forks are powerful tactics!"
        ),
        
        MistakeType.MISSED_PIN: (
            f"You missed a pin opportunity! {mistake.best_move} would have pinned an opponent's piece. "
            "Pins restrict your opponent's options - look for pieces lined up with the king or queen."
        ),
        
        MistakeType.HANGING_PIECE: (
            f"You left your {mistake.hanging_piece} undefended. "
            "Opponent can capture it for free. "
            "Before moving, always check: is my piece safe?"
        ),
        
        MistakeType.MATERIAL_BLUNDER: (
            f"This move lost material ({mistake.pattern_details.get('material_lost', '?')} points). "
            f"You went from {'+' if mistake.eval_before > 0 else ''}{mistake.eval_before:.1f} to "
            f"{'+' if mistake.eval_after > 0 else ''}{mistake.eval_after:.1f}. "
            f"The better move was {mistake.best_move}."
        ),
        
        MistakeType.BLUNDER_WHEN_AHEAD: (
            f"You were winning (+{mistake.eval_before:.1f}) but threw it away. "
            "When ahead, play safe and simple moves. Don't complicate."
        ),
        
        MistakeType.IGNORED_THREAT: (
            f"Your opponent was threatening {mistake.threat}. "
            "You didn't stop it. Before each move, ask: what is my opponent trying to do?"
        ),
        
        MistakeType.FAILED_CONVERSION: (
            "You were ahead but couldn't increase your advantage. "
            "When winning, look for simple ways to trade pieces and simplify."
        ),
        
        MistakeType.MISSED_WINNING_TACTIC: (
            f"There was a winning move ({mistake.best_move}) but you missed it. "
            f"The position had a tactic worth {mistake.eval_drop:.1f} pawns."
        ),
        
        MistakeType.TIME_PRESSURE_BLUNDER: (
            "Late-game mistake - possibly due to time pressure. "
            "Manage your clock better in the opening and middlegame."
        ),
        
        MistakeType.POSITIONAL_DRIFT: (
            f"Small inaccuracy. {mistake.best_move} was slightly better. "
            f"Eval dropped by {mistake.eval_drop:.1f}."
        ),
        
        MistakeType.GOOD_MOVE: (
            "Good move! You found a reasonable continuation."
        ),
        
        MistakeType.EXCELLENT_MOVE: (
            "Excellent! You found the best move."
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
        "forks_walked_into": 0,
        "pins_walked_into": 0,
        "forks_missed": 0,
        "pins_missed": 0,
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
        elif m.mistake_type == MistakeType.WALKED_INTO_FORK:
            counts["forks_walked_into"] += 1
            counts["tactical_misses"] += 1
            counts["total_mistakes"] += 1
        elif m.mistake_type == MistakeType.WALKED_INTO_PIN:
            counts["pins_walked_into"] += 1
            counts["tactical_misses"] += 1
            counts["total_mistakes"] += 1
        elif m.mistake_type == MistakeType.MISSED_FORK:
            counts["forks_missed"] += 1
            counts["tactical_misses"] += 1
            counts["total_mistakes"] += 1
        elif m.mistake_type == MistakeType.MISSED_PIN:
            counts["pins_missed"] += 1
            counts["tactical_misses"] += 1
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
