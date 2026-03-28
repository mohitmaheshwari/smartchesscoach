"""
Intent Recognition Service - Step 6

Deterministic heuristics for detecting player intent from chess moves.
This approximates how a human coach interprets intention, not engine optimality.

ARCHITECTURE:
    Stockfish → Interpreter → 🆕 Intent Recognition → Position Context → CRS → Narrative

RULES:
- Pure functions only (no DB calls, no async, no LLM)
- 70-75% believable detection is the goal (human coaches aren't 100% accurate either)
- Intent affects PHRASING only, not analysis

8 INTENT TYPES:
    ATTACKING, DEFENDING, DEVELOPING, IMPROVING_PIECE,
    PREVENTING_THREAT, SIMPLIFYING, CREATING_THREAT, POSITIONAL_MANEUVER
"""

import chess
from typing import Dict, Optional, List, Tuple, Set
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# INTENT TYPES
# =============================================================================

class IntentType(str, Enum):
    """Player intent categories - start small, 8 types only"""
    ATTACKING = "ATTACKING"
    DEFENDING = "DEFENDING"
    DEVELOPING = "DEVELOPING"
    IMPROVING_PIECE = "IMPROVING_PIECE"
    PREVENTING_THREAT = "PREVENTING_THREAT"
    SIMPLIFYING = "SIMPLIFYING"
    CREATING_THREAT = "CREATING_THREAT"
    POSITIONAL_MANEUVER = "POSITIONAL_MANEUVER"


class IntentQuality(str, Enum):
    """How good was the intent execution?"""
    GOOD = "good"           # move == best_move
    REASONABLE = "reasonable"  # cp_loss < 60
    PREMATURE = "premature"    # cp_loss < 150
    INCORRECT = "incorrect"    # cp_loss >= 150


# Intent priority order - human coaches prioritize danger and tactics first
INTENT_PRIORITY = [
    IntentType.PREVENTING_THREAT,
    IntentType.ATTACKING,
    IntentType.CREATING_THREAT,
    IntentType.DEFENDING,
    IntentType.SIMPLIFYING,
    IntentType.DEVELOPING,
    IntentType.IMPROVING_PIECE,
    IntentType.POSITIONAL_MANEUVER,
]


# =============================================================================
# INTENT DESCRIPTION TEMPLATES (Deterministic, not generated)
# =============================================================================

INTENT_TEXT = {
    IntentType.ATTACKING: "You tried to start an attack.",
    IntentType.DEFENDING: "You focused on defending your position.",
    IntentType.DEVELOPING: "You aimed to develop your pieces.",
    IntentType.IMPROVING_PIECE: "You tried to improve piece activity.",
    IntentType.PREVENTING_THREAT: "You tried to stop your opponent's idea.",
    IntentType.SIMPLIFYING: "You aimed to simplify the position.",
    IntentType.CREATING_THREAT: "You tried to create pressure.",
    IntentType.POSITIONAL_MANEUVER: "You adjusted your position.",
}

# Extended descriptions for narrative engine (with quality context)
INTENT_QUALITY_TEXT = {
    (IntentType.ATTACKING, IntentQuality.GOOD): "You launched an attack at the right moment.",
    (IntentType.ATTACKING, IntentQuality.REASONABLE): "Your attacking idea was reasonable.",
    (IntentType.ATTACKING, IntentQuality.PREMATURE): "You tried to attack, but the timing was off.",
    (IntentType.ATTACKING, IntentQuality.INCORRECT): "You tried to attack when defense was needed.",
    
    (IntentType.DEFENDING, IntentQuality.GOOD): "You defended correctly.",
    (IntentType.DEFENDING, IntentQuality.REASONABLE): "Your defensive idea made sense.",
    (IntentType.DEFENDING, IntentQuality.PREMATURE): "You defended, but missed a better option.",
    (IntentType.DEFENDING, IntentQuality.INCORRECT): "You tried to defend, but the method was wrong.",
    
    (IntentType.DEVELOPING, IntentQuality.GOOD): "Good development choice.",
    (IntentType.DEVELOPING, IntentQuality.REASONABLE): "Development was reasonable here.",
    (IntentType.DEVELOPING, IntentQuality.PREMATURE): "Development was okay, but timing could be better.",
    (IntentType.DEVELOPING, IntentQuality.INCORRECT): "Development here allowed opponent's idea.",
    
    (IntentType.IMPROVING_PIECE, IntentQuality.GOOD): "You improved your piece to a strong square.",
    (IntentType.IMPROVING_PIECE, IntentQuality.REASONABLE): "The piece improvement made sense.",
    (IntentType.IMPROVING_PIECE, IntentQuality.PREMATURE): "The piece needed a better square first.",
    (IntentType.IMPROVING_PIECE, IntentQuality.INCORRECT): "The piece was fine where it was.",
    
    (IntentType.PREVENTING_THREAT, IntentQuality.GOOD): "You correctly neutralized their threat.",
    (IntentType.PREVENTING_THREAT, IntentQuality.REASONABLE): "You saw the threat and responded.",
    (IntentType.PREVENTING_THREAT, IntentQuality.PREMATURE): "You saw a threat, but there was a better response.",
    (IntentType.PREVENTING_THREAT, IntentQuality.INCORRECT): "You tried to prevent something, but missed the real danger.",
    
    (IntentType.SIMPLIFYING, IntentQuality.GOOD): "You simplified at the right moment.",
    (IntentType.SIMPLIFYING, IntentQuality.REASONABLE): "Simplification was reasonable here.",
    (IntentType.SIMPLIFYING, IntentQuality.PREMATURE): "Simplifying was okay, but you had more.",
    (IntentType.SIMPLIFYING, IntentQuality.INCORRECT): "Simplifying here gave up your advantage.",
    
    (IntentType.CREATING_THREAT, IntentQuality.GOOD): "You created real pressure.",
    (IntentType.CREATING_THREAT, IntentQuality.REASONABLE): "Your threat creation was sensible.",
    (IntentType.CREATING_THREAT, IntentQuality.PREMATURE): "The threat idea was good, but premature.",
    (IntentType.CREATING_THREAT, IntentQuality.INCORRECT): "The threat wasn't real and cost you.",
    
    (IntentType.POSITIONAL_MANEUVER, IntentQuality.GOOD): "Good positional adjustment.",
    (IntentType.POSITIONAL_MANEUVER, IntentQuality.REASONABLE): "The positional idea was sound.",
    (IntentType.POSITIONAL_MANEUVER, IntentQuality.PREMATURE): "The maneuver was okay, but something else was needed.",
    (IntentType.POSITIONAL_MANEUVER, IntentQuality.INCORRECT): "This wasn't the moment for quiet moves.",
}


# =============================================================================
# SHARED UTILITIES
# =============================================================================

# Central squares for piece improvement detection
CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.C4, chess.C5, chess.C6,
    chess.D3, chess.D6,
    chess.E3, chess.E6,
    chess.F3, chess.F4, chess.F5, chess.F6
}

# Starting squares for development detection
STARTING_SQUARES_WHITE = {chess.B1, chess.G1, chess.C1, chess.F1}
STARTING_SQUARES_BLACK = {chess.B8, chess.G8, chess.C8, chess.F8}
STARTING_SQUARES = STARTING_SQUARES_WHITE | STARTING_SQUARES_BLACK


def get_game_phase(board: chess.Board) -> str:
    """
    Determine game phase from piece count.
    Human coaches interpret intent differently by phase.
    
    Returns: "opening", "middlegame", or "endgame"
    """
    piece_count = len(board.piece_map())
    
    if piece_count > 26:
        return "opening"
    elif piece_count > 14:
        return "middlegame"
    else:
        return "endgame"


def get_king_zone(board: chess.Board, color: chess.Color) -> Set[int]:
    """
    Get squares around the king (distance <= 2).
    This approximates human perception of "attack area".
    
    King Zone = king square + 8 surrounding squares + forward ring
    """
    king_sq = board.king(color)
    if king_sq is None:
        return set()
    
    zone = set()
    for sq in chess.SQUARES:
        if chess.square_distance(sq, king_sq) <= 2:
            zone.add(sq)
    
    return zone


def square_value(sq: int) -> int:
    """
    Score a square for piece improvement detection.
    Center = 3, Extended center = 2, Edge = 1
    """
    if sq in CENTER:
        return 3
    elif sq in EXTENDED_CENTER:
        return 2
    else:
        return 1


def get_major_piece_squares(board: chess.Board, color: chess.Color) -> Set[int]:
    """Get squares of major pieces (Q, R) for a color"""
    squares = set()
    for sq, piece in board.piece_map().items():
        if piece.color == color and piece.piece_type in [chess.QUEEN, chess.ROOK]:
            squares.add(sq)
    return squares


# =============================================================================
# INTENT DETECTION FUNCTIONS
# =============================================================================

def detect_attacking_intent(
    board: chess.Board,
    move: chess.Move,
    player_color: chess.Color
) -> Tuple[bool, float]:
    """
    Detect ATTACKING intent.
    
    A move is attacking if:
    - Moves closer to enemy king
    - Gives check
    - Piece enters king zone
    - Queen moves toward enemy king side
    
    Returns: (is_attacking, score)
    """
    enemy_color = not player_color
    enemy_king = board.king(enemy_color)
    
    if enemy_king is None:
        return False, 0.0
    
    attacking_score = 0.0
    enemy_king_zone = get_king_zone(board, enemy_color)
    piece = board.piece_at(move.from_square)
    
    if piece is None:
        return False, 0.0
    
    # Rule A: Moves closer to enemy king
    before_dist = chess.square_distance(move.from_square, enemy_king)
    after_dist = chess.square_distance(move.to_square, enemy_king)
    
    if after_dist < before_dist:
        attacking_score += 1.0
        # Extra point for aggressive pieces
        if piece.piece_type in [chess.QUEEN, chess.ROOK]:
            attacking_score += 0.5
    
    # Rule B: Move gives check
    board.push(move)
    if board.is_check():
        attacking_score += 2.0
    board.pop()
    
    # Rule C: Piece enters king zone
    if move.to_square in enemy_king_zone:
        attacking_score += 2.0
    
    # Rule D: Queen or bishop aims at king diagonal/file
    if piece.piece_type == chess.QUEEN:
        # Queen moving to aggressive file (toward enemy king)
        enemy_king_file = chess.square_file(enemy_king)
        to_file = chess.square_file(move.to_square)
        from_file = chess.square_file(move.from_square)
        
        # Moving toward king's file
        if abs(to_file - enemy_king_file) < abs(from_file - enemy_king_file):
            attacking_score += 1.0
        
        # Queen on aggressive rank (closer to enemy)
        enemy_king_rank = chess.square_rank(enemy_king)
        to_rank = chess.square_rank(move.to_square)
        
        if player_color == chess.WHITE:
            # White attacking - moving up
            if to_rank > 4:  # Ranks 5-7
                attacking_score += 0.5
        else:
            # Black attacking - moving down
            if to_rank < 3:  # Ranks 0-2
                attacking_score += 0.5
    
    # Threshold: score >= 2 (but be more lenient for queens)
    if piece.piece_type == chess.QUEEN and attacking_score >= 1.5:
        return True, attacking_score
    
    return attacking_score >= 2.0, attacking_score


def detect_defending_intent(
    board: chess.Board,
    move: chess.Move,
    player_color: chess.Color
) -> Tuple[bool, float]:
    """
    Detect DEFENDING intent.
    
    A move is defending if:
    - Protects an attacked piece
    - Improves king safety (castling, moving king, adding defender)
    
    Returns: (is_defending, score)
    """
    defending_score = 0.0
    piece = board.piece_at(move.from_square)
    
    if piece is None:
        return False, 0.0
    
    # Rule A: King safety improvement
    if piece.piece_type == chess.KING:
        defending_score += 2.0
        
        # Bonus for castling
        if board.is_castling(move):
            defending_score += 1.0
    
    # Rule B: Check if we're defending an attacked piece
    enemy_color = not player_color
    
    # Find our pieces that are attacked
    for sq, p in board.piece_map().items():
        if p.color == player_color and sq != move.from_square:
            if board.is_attacked_by(enemy_color, sq):
                # Check if our move adds a defender
                board.push(move)
                if board.is_attacked_by(player_color, sq):
                    defending_score += 1.5
                board.pop()
    
    # Rule C: Moving to a safer square when under attack
    if board.is_attacked_by(enemy_color, move.from_square):
        board.push(move)
        if not board.is_attacked_by(enemy_color, move.to_square):
            defending_score += 1.5
        board.pop()
    
    return defending_score >= 2.0, defending_score


def detect_developing_intent(
    board: chess.Board,
    move: chess.Move,
    player_color: chess.Color
) -> Tuple[bool, float]:
    """
    Detect DEVELOPING intent.
    
    Only valid in OPENING phase.
    Minor piece (knight/bishop) moved from starting square.
    
    Returns: (is_developing, score)
    """
    phase = get_game_phase(board)
    
    if phase != "opening":
        return False, 0.0
    
    piece = board.piece_at(move.from_square)
    
    if piece is None:
        return False, 0.0
    
    # Check if minor piece from starting square
    if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
        if move.from_square in STARTING_SQUARES:
            return True, 3.0
    
    # Also count castling as development in opening
    if board.is_castling(move):
        return True, 2.5
    
    return False, 0.0


def detect_improving_piece_intent(
    board: chess.Board,
    move: chess.Move,
    player_color: chess.Color
) -> Tuple[bool, float]:
    """
    Detect IMPROVING_PIECE intent.
    
    Piece moves to a better square (centralization).
    Must NOT be a capture or check.
    
    Returns: (is_improving, score)
    """
    piece = board.piece_at(move.from_square)
    
    if piece is None:
        return False, 0.0
    
    # Must not be capture
    if board.is_capture(move):
        return False, 0.0
    
    # Must not give check
    board.push(move)
    gives_check = board.is_check()
    board.pop()
    
    if gives_check:
        return False, 0.0
    
    # Compare square values
    from_value = square_value(move.from_square)
    to_value = square_value(move.to_square)
    
    if to_value > from_value:
        score = float(to_value - from_value) + 1.0
        return True, score
    
    return False, 0.0


def detect_preventing_threat_intent(
    board: chess.Board,
    move: chess.Move,
    player_color: chess.Color,
    opponent_pv: Optional[List[str]] = None
) -> Tuple[bool, float]:
    """
    Detect PREVENTING_THREAT intent.
    
    Use opponent PV to detect if player's move stops a threat.
    
    Returns: (is_preventing, score)
    """
    if not opponent_pv or len(opponent_pv) == 0:
        return False, 0.0
    
    try:
        # Get opponent's threatened move
        threat_move_uci = opponent_pv[0]
        threat_move = chess.Move.from_uci(threat_move_uci)
        
        # Check if threat exists before our move
        if not board.is_legal(threat_move):
            return False, 0.0
        
        # Evaluate threat severity
        board.push(threat_move)
        threat_is_check = board.is_check()
        threat_is_capture = board.is_capture(threat_move)
        board.pop()
        
        if not (threat_is_check or threat_is_capture):
            return False, 0.0
        
        # Now apply our move and check if threat is neutralized
        board.push(move)
        
        # Check if threat move is still legal and dangerous
        threat_still_exists = False
        if board.is_legal(threat_move):
            board.push(threat_move)
            threat_still_exists = board.is_check() or board.is_capture(threat_move)
            board.pop()
        
        board.pop()
        
        if not threat_still_exists:
            score = 3.0 if threat_is_check else 2.5
            return True, score
        
    except (ValueError, chess.InvalidMoveError):
        pass
    
    return False, 0.0


def detect_simplifying_intent(
    board: chess.Board,
    move: chess.Move,
    player_color: chess.Color,
    eval_before: int
) -> Tuple[bool, float]:
    """
    Detect SIMPLIFYING intent.
    
    Trading pieces while ahead (eval > +100).
    
    Returns: (is_simplifying, score)
    """
    # Must be a capture
    if not board.is_capture(move):
        return False, 0.0
    
    # Must be ahead (from player's perspective)
    if player_color == chess.WHITE:
        player_eval = eval_before
    else:
        player_eval = -eval_before
    
    if player_eval < 100:  # At least +1 pawn advantage
        return False, 0.0
    
    # Check if it's a trade (we capture piece of similar value)
    captured_piece = board.piece_at(move.to_square)
    moving_piece = board.piece_at(move.from_square)
    
    if captured_piece is None or moving_piece is None:
        return False, 0.0
    
    # Piece values for simplification detection
    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0
    }
    
    captured_value = piece_values.get(captured_piece.piece_type, 0)
    moving_value = piece_values.get(moving_piece.piece_type, 0)
    
    # Trade or winning capture while ahead = simplifying
    if captured_value >= moving_value - 1:
        return True, 2.5
    
    return False, 0.0


def detect_creating_threat_intent(
    board: chess.Board,
    move: chess.Move,
    player_color: chess.Color
) -> Tuple[bool, float]:
    """
    Detect CREATING_THREAT intent.
    
    After move, creates new attacks on enemy pieces.
    
    Returns: (is_creating_threat, score)
    """
    enemy_color = not player_color
    
    # Get enemy major piece squares before
    enemy_major_before = get_major_piece_squares(board, enemy_color)
    
    # Check attacks before
    attacks_before = sum(
        1 for sq in enemy_major_before
        if board.is_attacked_by(player_color, sq)
    )
    
    # Apply move
    board.push(move)
    
    # Check for check (strong threat)
    creates_check = board.is_check()
    
    # Check attacks after
    enemy_major_after = get_major_piece_squares(board, enemy_color)
    attacks_after = sum(
        1 for sq in enemy_major_after
        if board.is_attacked_by(player_color, sq)
    )
    
    board.pop()
    
    score = 0.0
    
    if creates_check:
        score += 2.0
    
    if attacks_after > attacks_before:
        score += 1.5 * (attacks_after - attacks_before)
    
    return score >= 2.0, score


# =============================================================================
# MAIN INTENT RECOGNITION FUNCTION
# =============================================================================

@dataclass
class IntentResult:
    """Result of intent recognition for a single move"""
    intent_type: str
    intent_confidence: float
    intent_description: str
    intent_quality: str
    
    # Additional context for narrative engine
    intent_quality_description: str
    all_detected_intents: List[Tuple[str, float]]  # For debugging
    
    def to_dict(self) -> Dict:
        return {
            "intent_type": self.intent_type,
            "intent_confidence": round(self.intent_confidence, 2),
            "intent_description": self.intent_description,
            "intent_quality": self.intent_quality,
            "intent_quality_description": self.intent_quality_description,
        }


def recognize_intent(
    fen_before: str,
    move_uci: str,
    best_move_uci: str,
    eval_before: int,
    eval_after: int,
    player_color_str: str,  # "white" or "black"
    pv_after_best: Optional[List[str]] = None,
    cognitive_gap: Optional[str] = None
) -> IntentResult:
    """
    Main intent recognition function.
    
    Detects the most likely player intent from a chess move.
    Pure function - no DB calls, no async, no LLM.
    
    Args:
        fen_before: FEN before the move
        move_uci: The move played (UCI format)
        best_move_uci: Engine's best move (UCI format)
        eval_before: Centipawn evaluation before move
        eval_after: Centipawn evaluation after move
        player_color_str: "white" or "black"
        pv_after_best: Opponent's PV after best move (for threat detection)
        cognitive_gap: Already detected cognitive gap (optional)
    
    Returns:
        IntentResult with detected intent and quality
    """
    try:
        board = chess.Board(fen_before)
        move = chess.Move.from_uci(move_uci)
        player_color = chess.WHITE if player_color_str.lower() == "white" else chess.BLACK
    except (ValueError, chess.InvalidMoveError):
        # Fallback on parse error
        return IntentResult(
            intent_type=IntentType.POSITIONAL_MANEUVER.value,
            intent_confidence=0.3,
            intent_description=INTENT_TEXT[IntentType.POSITIONAL_MANEUVER],
            intent_quality=IntentQuality.REASONABLE.value,
            intent_quality_description="The positional idea was sound.",
            all_detected_intents=[]
        )
    
    # Run all intent detectors
    detected_intents: List[Tuple[IntentType, float]] = []
    
    # 1. PREVENTING_THREAT (highest priority)
    is_preventing, score = detect_preventing_threat_intent(
        board, move, player_color, pv_after_best
    )
    if is_preventing:
        detected_intents.append((IntentType.PREVENTING_THREAT, score))
    
    # 2. ATTACKING
    is_attacking, score = detect_attacking_intent(board, move, player_color)
    if is_attacking:
        detected_intents.append((IntentType.ATTACKING, score))
    
    # 3. CREATING_THREAT
    is_creating, score = detect_creating_threat_intent(board, move, player_color)
    if is_creating:
        detected_intents.append((IntentType.CREATING_THREAT, score))
    
    # 4. DEFENDING
    is_defending, score = detect_defending_intent(board, move, player_color)
    if is_defending:
        detected_intents.append((IntentType.DEFENDING, score))
    
    # 5. SIMPLIFYING
    is_simplifying, score = detect_simplifying_intent(
        board, move, player_color, eval_before
    )
    if is_simplifying:
        detected_intents.append((IntentType.SIMPLIFYING, score))
    
    # 6. DEVELOPING
    is_developing, score = detect_developing_intent(board, move, player_color)
    if is_developing:
        detected_intents.append((IntentType.DEVELOPING, score))
    
    # 7. IMPROVING_PIECE
    is_improving, score = detect_improving_piece_intent(board, move, player_color)
    if is_improving:
        detected_intents.append((IntentType.IMPROVING_PIECE, score))
    
    # Resolve intent by priority
    if detected_intents:
        # Sort by priority order
        detected_intents.sort(
            key=lambda x: INTENT_PRIORITY.index(x[0])
        )
        chosen_intent, chosen_score = detected_intents[0]
    else:
        # Fallback to POSITIONAL_MANEUVER
        chosen_intent = IntentType.POSITIONAL_MANEUVER
        chosen_score = 1.0
    
    # Calculate confidence (0.0 - 1.0)
    confidence = min(1.0, chosen_score / 4.0)
    
    # Determine intent quality based on centipawn loss
    cp_loss = max(0, eval_before - eval_after) if player_color == chess.WHITE else max(0, -eval_before - (-eval_after))
    
    if move_uci == best_move_uci:
        quality = IntentQuality.GOOD
    elif cp_loss < 60:
        quality = IntentQuality.REASONABLE
    elif cp_loss < 150:
        quality = IntentQuality.PREMATURE
    else:
        quality = IntentQuality.INCORRECT
    
    # Get descriptions
    intent_description = INTENT_TEXT.get(chosen_intent, INTENT_TEXT[IntentType.POSITIONAL_MANEUVER])
    quality_key = (chosen_intent, quality)
    quality_description = INTENT_QUALITY_TEXT.get(
        quality_key,
        f"{intent_description[:-1]}, but the execution could be better."
    )
    
    return IntentResult(
        intent_type=chosen_intent.value,
        intent_confidence=confidence,
        intent_description=intent_description,
        intent_quality=quality.value,
        intent_quality_description=quality_description,
        all_detected_intents=[(i.value, s) for i, s in detected_intents]
    )


# =============================================================================
# BATCH PROCESSING FOR ANALYSIS WORKER
# =============================================================================

def recognize_intents_for_game(
    move_evaluations: List[Dict],
    user_color: str
) -> List[Dict]:
    """
    Process all moves in a game and attach intent recognition.
    
    Args:
        move_evaluations: List of move evaluation dicts from analysis
        user_color: "white" or "black"
    
    Returns:
        Updated move_evaluations with intent fields added
    """
    for i, move_eval in enumerate(move_evaluations):
        # Only process user moves
        if not move_eval.get("is_user_move", False):
            continue
        
        # Get PV for opponent threat detection
        # Look at previous position's engine PV
        opponent_pv = None
        if i > 0:
            prev_eval = move_evaluations[i - 1]
            opponent_pv = prev_eval.get("engine_pv", [])
        
        # Run intent recognition
        intent_result = recognize_intent(
            fen_before=move_eval.get("fen_before", ""),
            move_uci=move_eval.get("move_uci", ""),
            best_move_uci=move_eval.get("engine_best_move", ""),
            eval_before=move_eval.get("score_before", 0),
            eval_after=move_eval.get("score_after", 0),
            player_color_str=user_color,
            pv_after_best=opponent_pv,
            cognitive_gap=move_eval.get("cognitive_gap")
        )
        
        # Attach intent fields to move evaluation
        move_eval["intent_type"] = intent_result.intent_type
        move_eval["intent_confidence"] = intent_result.intent_confidence
        move_eval["intent_quality"] = intent_result.intent_quality
        move_eval["intent_description"] = intent_result.intent_description
        move_eval["intent_quality_description"] = intent_result.intent_quality_description
    
    return move_evaluations
